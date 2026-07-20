#!/usr/bin/env python3
"""Analyze FIT files and write same-name Markdown summaries."""

from __future__ import annotations

import argparse
import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import fitdecode

from intervals_icu_client import IntervalsClient, IntervalsError, sanitize_activity_name
from markdown_tables import write_text_atomic
from profile_paths import DATA_DIR, ROOT


ACTIVITIES_DIR = DATA_DIR / "activities"
THRESHOLDS_DIR = DATA_DIR / "thresholds"
VO2MAX_DIR = DATA_DIR / "VO2max"


@dataclass
class FitInfo:
    path: Path
    messages: dict[str, list[dict[str, Any]]]
    session: dict[str, Any]
    laps: list[dict[str, Any]]
    records: list[dict[str, Any]]
    start: datetime | None
    sport: str


def field_dict(message: fitdecode.records.FitDataMessage) -> dict[str, Any]:
    return {field.name: field.value for field in message.fields}


def read_fit(path: Path) -> FitInfo:
    messages: dict[str, list[dict[str, Any]]] = {}
    with fitdecode.FitReader(str(path)) as fit:
        for frame in fit:
            if isinstance(frame, fitdecode.records.FitDataMessage):
                messages.setdefault(frame.name, []).append(field_dict(frame))
    trim_accidental_multisport_finish_restart(messages)
    sessions = messages.get("session") or [{}]
    session = aggregate_multisport_session(sessions) if is_multisport_sessions(sessions) else sessions[0]
    laps = messages.get("lap") or []
    records = messages.get("record") or []
    start = local_activity_start(messages, session.get("start_time"))
    sport = str(session.get("sport") or session.get("sub_sport") or "").lower()
    if not sport:
        sport = infer_sport_from_name(path.name)
    return FitInfo(path, messages, session, laps, records, start, sport)


def trim_accidental_multisport_finish_restart(messages: dict[str, list[dict[str, Any]]]) -> None:
    """Remove a short stationary tail caused by restarting the watch after a race finish."""
    sessions = messages.get("session") or []
    if not is_multisport_sessions(sessions):
        return
    sport_sessions = [session for session in sessions if not is_transition_session(session)]
    if not sport_sessions:
        return
    final_session = sport_sessions[-1]
    final_start = final_session.get("start_time")
    final_duration = value(final_session, "total_timer_time")
    if not isinstance(final_start, datetime) or final_duration in (None, ""):
        return
    final_end = final_start + timedelta(seconds=float(final_duration))

    events = sorted(
        (event for event in messages.get("event", []) if isinstance(event.get("timestamp"), datetime)),
        key=lambda event: event["timestamp"],
    )
    restart: datetime | None = None
    for index, event in enumerate(events[:-1]):
        stop_time = event["timestamp"]
        if not (final_start < stop_time < final_end):
            continue
        if str(event.get("event_type") or "").lower() != "stop_all":
            continue
        next_event = events[index + 1]
        next_time = next_event["timestamp"]
        if (
            str(next_event.get("event_type") or "").lower() == "start"
            and 0 <= (next_time - stop_time).total_seconds() <= 5
        ):
            restart = next_time
            break
    if restart is None:
        return

    final_sport = str(final_session.get("sport") or "").lower()
    final_laps = [
        lap
        for lap in messages.get("lap", [])
        if str(lap.get("sport") or "").lower() == final_sport
        and isinstance(lap.get("start_time"), datetime)
    ]
    trailing_laps = [lap for lap in final_laps if lap["start_time"] >= restart]
    retained_laps = [lap for lap in final_laps if lap["start_time"] < restart]
    trailing_duration = sum(float(value(lap, "total_timer_time") or 0) for lap in trailing_laps)
    trailing_distance = sum(float(value(lap, "total_distance") or 0) for lap in trailing_laps)
    if not retained_laps or trailing_duration < 15 or trailing_distance > 50:
        return

    messages["lap"] = [lap for lap in messages.get("lap", []) if lap not in trailing_laps]
    messages["record"] = [
        record
        for record in messages.get("record", [])
        if not isinstance(record.get("timestamp"), datetime) or record["timestamp"] < restart
    ]
    recompute_session_from_laps(final_session, retained_laps)


def recompute_session_from_laps(session: dict[str, Any], laps: list[dict[str, Any]]) -> None:
    durations = [float(value(lap, "total_timer_time") or 0) for lap in laps]
    timer_time = sum(durations)
    elapsed_time = sum(float(value(lap, "total_elapsed_time") or 0) for lap in laps)
    distance = sum(float(value(lap, "total_distance") or 0) for lap in laps)
    session["total_timer_time"] = timer_time
    session["total_elapsed_time"] = elapsed_time
    session["total_distance"] = distance
    if timer_time > 0:
        session["enhanced_avg_speed"] = distance / timer_time

    for field in ("avg_heart_rate", "avg_power", "avg_cadence", "avg_running_cadence", "avg_step_length", "avg_stance_time", "avg_vertical_oscillation"):
        weighted = [
            (float(lap[field]), duration)
            for lap, duration in zip(laps, durations)
            if lap.get(field) not in (None, "") and duration > 0
        ]
        if weighted:
            session[field] = sum(item * duration for item, duration in weighted) / sum(duration for _, duration in weighted)
    for field in ("max_heart_rate", "max_power"):
        values = [float(lap[field]) for lap in laps if lap.get(field) not in (None, "")]
        if values:
            session[field] = max(values)
    normalized = [
        (float(lap["normalized_power"]), duration)
        for lap, duration in zip(laps, durations)
        if lap.get("normalized_power") not in (None, "") and duration > 0
    ]
    if normalized:
        session["normalized_power"] = (
            sum(power**4 * duration for power, duration in normalized) / sum(duration for _, duration in normalized)
        ) ** 0.25
    for field in ("total_ascent", "total_descent", "total_calories"):
        values = [float(lap[field]) for lap in laps if lap.get(field) not in (None, "")]
        if values:
            session[field] = sum(values)


def local_activity_start(
    messages: dict[str, list[dict[str, Any]]],
    fallback: datetime | None,
) -> datetime | None:
    for activity in messages.get("activity", []):
        local_timestamp = activity.get("local_timestamp")
        if isinstance(local_timestamp, datetime):
            return local_timestamp
    return fallback


def is_transition_session(session: dict[str, Any]) -> bool:
    return str(session.get("sport") or "").lower() == "transition"


def is_multisport_sessions(sessions: list[dict[str, Any]]) -> bool:
    sports = {
        str(session.get("sport") or "").lower()
        for session in sessions
        if session and not is_transition_session(session)
    }
    return len(sports) > 1


def aggregate_multisport_session(sessions: list[dict[str, Any]]) -> dict[str, Any]:
    start_times = [session.get("start_time") for session in sessions if isinstance(session.get("start_time"), datetime)]
    totals = {
        "total_timer_time": sum(float(value(session, "total_timer_time") or 0) for session in sessions),
        "total_elapsed_time": sum(float(value(session, "total_elapsed_time") or 0) for session in sessions),
        "total_distance": sum(float(value(session, "total_distance") or 0) for session in sessions),
        "total_calories": sum(float(value(session, "total_calories") or 0) for session in sessions),
        "training_load_peak": max((float(value(session, "training_load_peak", "total_training_load") or 0) for session in sessions), default=0),
        "total_training_effect": max((float(value(session, "total_training_effect") or 0) for session in sessions), default=0),
        "total_anaerobic_training_effect": max((float(value(session, "total_anaerobic_training_effect") or 0) for session in sessions), default=0),
    }
    hr_weighted = [
        (float(value(session, "avg_heart_rate") or 0), float(value(session, "total_timer_time") or 0))
        for session in sessions
        if value(session, "avg_heart_rate") not in (None, "") and float(value(session, "total_timer_time") or 0) > 0
    ]
    max_hr_values = [float(value(session, "max_heart_rate") or 0) for session in sessions if value(session, "max_heart_rate") not in (None, "")]
    aggregate = {
        "sport": "multisport",
        "sub_sport": "triathlon",
        "start_time": min(start_times) if start_times else None,
        "avg_heart_rate": round(sum(hr * duration for hr, duration in hr_weighted) / sum(duration for _, duration in hr_weighted)) if hr_weighted else None,
        "max_heart_rate": round(max(max_hr_values)) if max_hr_values else None,
    }
    aggregate.update(totals)
    return aggregate


def infer_sport_from_name(name: str) -> str:
    lower = name.lower()
    if "swim" in lower:
        return "swimming"
    if "run" in lower or "laufen" in lower:
        return "running"
    if "bike" in lower or "ride" in lower or "rad" in lower:
        return "cycling"
    return "unknown"


def is_bike(sport: str) -> bool:
    return sport in {"cycling", "biking", "bike", "ride"}


def is_run(sport: str) -> bool:
    return sport in {"running", "run"}


def is_swim(sport: str) -> bool:
    return sport in {"swimming", "swim"}


def is_multisport(sport: str) -> bool:
    return sport in {"multisport", "triathlon"}


def sport_label(sport: str) -> str:
    if is_multisport(sport):
        return "Triathlon"
    if is_bike(sport):
        return "Radfahren"
    if is_run(sport):
        return "Laufen"
    if is_swim(sport):
        return "Schwimmen"
    return sport or "Unbekannt"


def seconds_to_hms(value: Any) -> str:
    if value in (None, ""):
        return "-"
    seconds = round(float(value))
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def meters_to_km(value: Any) -> str:
    if value in (None, ""):
        return "-"
    return f"{float(value) / 1000:.2f}km"


def pace_from_speed(speed_mps: Any, swim: bool = False) -> str:
    if speed_mps in (None, "", 0):
        return "-"
    speed = float(speed_mps)
    if speed <= 0:
        return "-"
    seconds = (100 if swim else 1000) / speed
    return f"{round(seconds) // 60}:{round(seconds) % 60:02d}/{'100m' if swim else 'km'}"


def pace_from_kmh(kmh: float) -> str:
    seconds = round(3600 / kmh)
    return f"{seconds // 60}:{seconds % 60:02d}"


def calculate_grade_adjusted_running_speed(speed_in_mps: float, elevation_gain_in_m_per_km: float) -> float:
    if not math.isfinite(speed_in_mps) or speed_in_mps <= 0:
        return 0.0
    if not math.isfinite(elevation_gain_in_m_per_km):
        return speed_in_mps
    grade = min(max(elevation_gain_in_m_per_km / 1000, -0.45), 0.45)
    cost_flat = 3.6
    cost_hilly = 155.4 * grade**5 - 30.4 * grade**4 - 43.3 * grade**3 + 46.3 * grade**2 + 19.5 * grade + cost_flat
    return speed_in_mps * cost_hilly / cost_flat


def gain_per_km(distance_m: Any, ascent_m: Any) -> float | None:
    if distance_m in (None, "", 0) or ascent_m in (None, ""):
        return None
    distance = float(distance_m)
    ascent = float(ascent_m)
    if distance <= 0:
        return None
    return ascent / (distance / 1000)


def gap_speed_from_summary(speed_mps: Any, distance_m: Any, ascent_m: Any) -> float | None:
    if speed_mps in (None, "", 0):
        return None
    speed = float(speed_mps)
    if speed <= 0:
        return None
    gain = gain_per_km(distance_m, ascent_m)
    if gain is None:
        return speed
    return calculate_grade_adjusted_running_speed(speed, gain)


def gap_label_from_summary(speed_mps: Any, distance_m: Any, ascent_m: Any) -> str:
    gap_speed = gap_speed_from_summary(speed_mps, distance_m, ascent_m)
    return pace_from_speed(gap_speed) if gap_speed else "-"


def parse_pace_seconds(label: str) -> float | None:
    if not label or label.strip() in {"-", "/"}:
        return None
    match = re.fullmatch(r"(\d+):(\d{2})", label.strip())
    if not match:
        return None
    return int(match.group(1)) * 60 + int(match.group(2))


ZONE_TABLE_CACHE: dict[str, list[dict[str, str]]] = {}


def zone_table(section: str) -> list[dict[str, str]]:
    cached = ZONE_TABLE_CACHE.get(section)
    if cached is not None:
        return cached
    path = DATA_DIR / "zones.md"
    text = path.read_text(encoding="utf-8-sig")
    match = re.search(rf"## {re.escape(section)}\n\n((?:\|.*\n)+)", text)
    if not match:
        ZONE_TABLE_CACHE[section] = []
        return []
    lines = [line.strip() for line in match.group(1).splitlines() if line.strip().startswith("|")]
    header = [cell.strip() for cell in lines[0].strip("|").split("|")]
    rows: list[dict[str, str]] = []
    for line in lines[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) == len(header):
            rows.append(dict(zip(header, cells)))
    ZONE_TABLE_CACHE[section] = rows
    return rows


def sport_zone_order(sport: str) -> list[str]:
    if is_swim(sport):
        return ["Z1", "Z2", "Z3", "Z4", "Z5"]
    return ["Z1", "Z2", "Z3", "Z4", "Z5", "Z6"]


def classify_bike_power_zone(power_w: float | None) -> str | None:
    if power_w is None or power_w <= 0:
        return None
    rows = zone_table("Bike")
    for row in rows:
        zone = row.get("Zone", "")
        lower = row.get("Untere Power-Grenze / W", "/")
        upper = row.get("Obere Power-Grenze / W", "/")
        lo = float(lower) if lower not in {"/", "-", ""} else None
        hi = float(upper) if upper not in {"/", "-", ""} else None
        if lo is None and hi is not None and power_w < hi:
            return zone
        if lo is not None and hi is None and power_w >= lo:
            return zone
        if lo is not None and hi is not None and lo <= power_w < hi:
            return zone
    return None


def classify_run_gap_zone(gap_pace_seconds: float | None) -> str | None:
    if gap_pace_seconds is None or gap_pace_seconds <= 0:
        return None
    rows = zone_table("Run")
    for row in rows:
        zone = row.get("Zone", "")
        slower = parse_pace_seconds(row.get("Untere Pace-Grenze / min:sec/km", ""))
        faster = parse_pace_seconds(row.get("Obere Pace-Grenze / min:sec/km", ""))
        if slower is None and faster is not None and gap_pace_seconds > faster:
            return zone
        if slower is not None and faster is None and gap_pace_seconds <= slower:
            return zone
        if slower is not None and faster is not None and faster < gap_pace_seconds <= slower:
            return zone
    return None


def classify_swim_zone(pace_seconds_100m: float | None) -> str | None:
    if pace_seconds_100m is None or pace_seconds_100m <= 0:
        return None
    rows = zone_table("Swim")
    if not rows:
        return None
    z2_slow = parse_pace_seconds(rows[-1].get("Untere Grenze", "")) if rows else None
    if z2_slow is not None and pace_seconds_100m > z2_slow:
        return "Z1"
    for row in rows:
        zone = row.get("Zone", "")
        slower = parse_pace_seconds(row.get("Untere Grenze", ""))
        faster = parse_pace_seconds(row.get("Obere Grenze", ""))
        if slower is not None and faster is not None and faster < pace_seconds_100m <= slower:
            return zone
        if slower is not None and faster is None and pace_seconds_100m <= slower:
            return zone
    return rows[0].get("Zone") if rows else None


def run_gap_record_points(info: FitInfo) -> list[tuple[datetime, float, float]]:
    points: list[tuple[datetime, float, float]] = []
    prev: dict[str, Any] | None = None
    for rec in info.records:
        timestamp = rec.get("timestamp")
        hr = rec.get("heart_rate")
        speed = value(rec, "enhanced_speed", "speed")
        distance = rec.get("distance")
        altitude = value(rec, "enhanced_altitude", "altitude")
        if not (isinstance(timestamp, datetime) and hr and speed and distance not in (None, "")):
            prev = rec
            continue
        gap_speed = float(speed)
        if prev is not None:
            prev_distance = prev.get("distance")
            prev_altitude = value(prev, "enhanced_altitude", "altitude")
            if prev_distance not in (None, "") and prev_altitude not in (None, "") and altitude not in (None, ""):
                delta_distance = float(distance) - float(prev_distance)
                delta_altitude = float(altitude) - float(prev_altitude)
                if delta_distance > 0:
                    gain = delta_altitude / (delta_distance / 1000)
                    gap_speed = calculate_grade_adjusted_running_speed(float(speed), gain)
        if float(hr) > 0 and gap_speed > 0:
            points.append((timestamp, float(hr), gap_speed))
        prev = rec
    return points


def segment_delta_seconds(prev_ts: datetime | None, current_ts: datetime | None) -> float | None:
    if not (isinstance(prev_ts, datetime) and isinstance(current_ts, datetime)):
        return None
    delta = (current_ts - prev_ts).total_seconds()
    if delta <= 0 or delta > 30:
        return None
    return delta


def bike_zone_seconds(info: FitInfo) -> dict[str, float]:
    totals = {zone: 0.0 for zone in sport_zone_order(info.sport)}
    prev: dict[str, Any] | None = None
    for rec in info.records:
        if prev is None:
            prev = rec
            continue
        delta = segment_delta_seconds(prev.get("timestamp"), rec.get("timestamp"))
        power = prev.get("power")
        zone = classify_bike_power_zone(float(power)) if power not in (None, "") else None
        if delta and zone:
            totals[zone] += delta
        prev = rec
    return totals


def run_zone_seconds(info: FitInfo) -> dict[str, float]:
    totals = {zone: 0.0 for zone in sport_zone_order(info.sport)}
    prev: dict[str, Any] | None = None
    for rec in info.records:
        if prev is None:
            prev = rec
            continue
        delta = segment_delta_seconds(prev.get("timestamp"), rec.get("timestamp"))
        if not delta:
            prev = rec
            continue
        prev_speed = value(prev, "enhanced_speed", "speed")
        prev_distance = prev.get("distance")
        current_distance = rec.get("distance")
        prev_altitude = value(prev, "enhanced_altitude", "altitude")
        current_altitude = value(rec, "enhanced_altitude", "altitude")
        gap_speed = float(prev_speed) if prev_speed not in (None, "") else None
        if (
            gap_speed is not None
            and prev_distance not in (None, "")
            and current_distance not in (None, "")
            and prev_altitude not in (None, "")
            and current_altitude not in (None, "")
        ):
            delta_distance = float(current_distance) - float(prev_distance)
            delta_altitude = float(current_altitude) - float(prev_altitude)
            if delta_distance > 0:
                gain = delta_altitude / (delta_distance / 1000)
                gap_speed = calculate_grade_adjusted_running_speed(gap_speed, gain)
        zone = classify_run_gap_zone((1000 / gap_speed) if gap_speed and gap_speed > 0 else None)
        if zone:
            totals[zone] += delta
        prev = rec
    return totals


def swim_zone_distance(info: FitInfo) -> dict[str, float]:
    totals = {zone: 0.0 for zone in sport_zone_order(info.sport)}
    pool_length = value(info.session, "pool_length")
    if pool_length not in (None, "", 0) and info.messages.get("length"):
        for length in info.messages.get("length", []):
            if str(length.get("length_type") or "").lower() != "active":
                continue
            speed = value(length, "avg_speed")
            if speed in (None, "", 0):
                continue
            pace_seconds = 100 / float(speed)
            zone = classify_swim_zone(pace_seconds)
            if zone:
                totals[zone] += float(pool_length)
        return totals
    for lap in info.laps:
        distance = value(lap, "total_distance")
        speed = value(lap, "enhanced_avg_speed", "avg_speed")
        if distance in (None, "", 0) or speed in (None, "", 0):
            continue
        pace_seconds = 100 / float(speed)
        zone = classify_swim_zone(pace_seconds)
        if zone:
            totals[zone] += float(distance)
    return totals


def zone_distribution(info: FitInfo) -> dict[str, float]:
    if is_multisport(info.sport):
        return {}
    if is_bike(info.sport):
        return bike_zone_seconds(info)
    if is_run(info.sport):
        return run_zone_seconds(info)
    if is_swim(info.sport):
        return swim_zone_distance(info)
    return {}


def format_zone_value(info: FitInfo, value_seconds_or_meters: float) -> str:
    if is_swim(info.sport):
        return fmt(round(value_seconds_or_meters), "m")
    return seconds_to_hms(value_seconds_or_meters)


def value(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        item = data.get(key)
        if item not in (None, ""):
            return item
    return None


def fmt(value_item: Any, suffix: str = "", digits: int = 0) -> str:
    if value_item in (None, ""):
        return "-"
    if isinstance(value_item, float):
        text = f"{value_item:.{digits}f}" if digits else str(round(value_item))
        text = text.rstrip("0").rstrip(".") if "." in text else text
    else:
        text = str(value_item)
    return f"{text}{suffix}"


def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", sanitize_activity_name(name).lower()).strip()


def intervals_type_for_sport(sport: str) -> str:
    if is_multisport(sport):
        return ""
    if is_bike(sport):
        return "Ride"
    if is_run(sport):
        return "Run"
    if is_swim(sport):
        return "Swim"
    return ""


def load_intervals_activities(infos: list[FitInfo]) -> tuple[list[dict[str, Any]], list[str]]:
    dated = [info.start.date() for info in infos if info.start]
    if not dated:
        return [], ["No FIT start dates available for Intervals.icu matching"]
    oldest, newest = min(dated), max(dated)
    fields = [
        "id",
        "start_date_local",
        "type",
        "name",
        "icu_training_load",
        "hr_load",
        "average_heartrate",
        "max_heartrate",
    ]
    try:
        return IntervalsClient.from_env().activities(oldest, newest, fields), []
    except IntervalsError as exc:
        return [], [f"Intervals.icu activities unavailable for TSS matching: {exc}"]


def match_activity(info: FitInfo, activities: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not info.start:
        return None
    day = info.start.date().isoformat()
    target_type = intervals_type_for_sport(info.sport)
    candidates = [
        item
        for item in activities
        if str(item.get("start_date_local", ""))[:10] == day
        and (not target_type or item.get("type") == target_type)
    ]
    if not candidates:
        return None
    fit_name = normalize_name(info.path.stem[11:] if re.match(r"\d{4}-\d{2}-\d{2} ", info.path.stem) else info.path.stem)
    if is_multisport(info.sport):
        named = [
            item
            for item in candidates
            if fit_name
            and (
                fit_name in normalize_name(str(item.get("name") or ""))
                or normalize_name(str(item.get("name") or "")) in fit_name
            )
        ]
        matches = named or candidates
        names = {normalize_name(str(item.get("name") or "")) for item in matches}
        if len(names) == 1:
            combined = dict(matches[0])
            for field in ("icu_training_load", "hr_load"):
                values = [float(item[field]) for item in matches if item.get(field) not in (None, "")]
                if values:
                    combined[field] = sum(values)
            return combined
        return None
    for item in candidates:
        activity_name = normalize_name(str(item.get("name") or ""))
        if fit_name and (fit_name in activity_name or activity_name in fit_name):
            return item
    return candidates[0] if len(candidates) == 1 else None


def get_tss(info: FitInfo, activity: dict[str, Any] | None, warnings: list[str]) -> str:
    if is_multisport(info.sport):
        if activity and activity.get("icu_training_load") not in (None, ""):
            return fmt(activity.get("icu_training_load"), digits=1)
        fallback_values = [
            float(value(session, "training_load_peak", "total_training_load") or 0)
            for session in info.messages.get("session", [])
        ]
        fallback = max(fallback_values, default=0)
        if fallback > 0:
            return fmt(fallback, digits=1)
        if activity and activity.get("hr_load") not in (None, ""):
            return fmt(activity.get("hr_load"), digits=1)
        warnings.append(f"{info.path.name}: no reliable multisport TSS/load source found")
        return "-"
    non_tri_sport = not (is_swim(info.sport) or is_bike(info.sport) or is_run(info.sport))
    if non_tri_sport and activity and activity.get("hr_load") not in (None, ""):
        return fmt(activity.get("hr_load"), digits=1)
    if non_tri_sport and activity and activity.get("icu_training_load") not in (None, ""):
        warnings.append(f"{info.path.name}: non swim/bike/run activity has no hr_load; using icu_training_load")
        return fmt(activity.get("icu_training_load"), digits=1)
    if activity and activity.get("icu_training_load") not in (None, ""):
        return fmt(activity.get("icu_training_load"), digits=1)
    fallback = value(info.session, "training_load_peak", "total_training_load")
    if fallback not in (None, ""):
        return fmt(fallback, digits=1)
    if activity and activity.get("hr_load") not in (None, ""):
        return fmt(activity.get("hr_load"), digits=1)
    fit_tss = value(info.session, "training_stress_score")
    if fit_tss not in (None, ""):
        return fmt(fit_tss, digits=1)
    warnings.append(f"{info.path.name}: no reliable TSS/load source found")
    return "-"


def efficiency(info: FitInfo) -> str:
    avg_hr = value(info.session, "avg_heart_rate", "avg_hr")
    if not avg_hr:
        return "-"
    if is_bike(info.sport):
        power = value(info.session, "avg_power", "normalized_power")
        return "-" if not power else f"{float(power) / float(avg_hr):.2f}W/bpm"
    if is_run(info.sport):
        gap_speed = gap_speed_from_summary(
            value(info.session, "enhanced_avg_speed", "avg_speed"),
            value(info.session, "total_distance"),
            value(info.session, "total_ascent"),
        )
        if not gap_speed:
            return "-"
        return f"{float(gap_speed) / float(avg_hr):.4f}m/s/bpm ({pace_from_speed(gap_speed)} GAP @ {round(float(avg_hr))}bpm)"
    return "-"


def hr_drift(info: FitInfo) -> str:
    name = info.path.stem.lower()
    if not (is_bike(info.sport) or is_run(info.sport)):
        return "-"
    if "basic" not in name and "long" not in name:
        return "-"
    points: list[tuple[datetime, float, float]] = []
    if is_bike(info.sport):
        for rec in info.records:
            timestamp = rec.get("timestamp")
            hr = rec.get("heart_rate")
            work = rec.get("power")
            if isinstance(timestamp, datetime) and hr and work and float(hr) > 0 and float(work) > 0:
                points.append((timestamp, float(hr), float(work)))
    else:
        points = run_gap_record_points(info)
    return hr_drift_from_points(points)


def hr_drift_from_points(points: list[tuple[datetime, float, float]]) -> str:
    if len(points) < 60:
        return "nicht sinnvoll berechenbar"
    points.sort(key=lambda item: item[0])
    duration = (points[-1][0] - points[0][0]).total_seconds()
    if duration <= 0:
        return "nicht sinnvoll berechenbar"
    start = points[0][0] + timedelta(seconds=duration * 0.1)
    end = points[0][0] + timedelta(seconds=duration * 0.9)
    comparable = [point for point in points if start <= point[0] <= end]
    if len(comparable) < 60:
        return "nicht sinnvoll berechenbar"
    median_hr = sorted(hr for _, hr, _ in comparable)[len(comparable) // 2]
    minimum_plausible_hr = max(60.0, median_hr * 0.65)
    comparable = [point for point in comparable if point[1] >= minimum_plausible_hr]
    if len(comparable) < 60:
        return "nicht sinnvoll berechenbar"
    midpoint = len(comparable) // 2
    first, second = comparable[:midpoint], comparable[midpoint:]
    work1 = sum(work for _, _, work in first) / len(first)
    work2 = sum(work for _, _, work in second) / len(second)
    if work1 <= 0 or abs(work2 - work1) / work1 > 0.15:
        return "nicht sinnvoll berechenbar"
    ef1 = sum(work for _, _, work in first) / sum(hr for _, hr, _ in first)
    ef2 = sum(work for _, _, work in second) / sum(hr for _, hr, _ in second)
    if ef1 <= 0:
        return "nicht sinnvoll berechenbar"
    drift = (ef1 - ef2) / ef1 * 100
    label = "stabil" if abs(drift) < 3 else "moderat driftend" if abs(drift) < 7 else "deutlich driftend"
    return f"{drift:.1f}% ({label})"


def lap_rows(info: FitInfo) -> tuple[list[str], list[list[str]]]:
    if is_multisport(info.sport):
        header = ["Segment", "Dauer", "Distanz", "Pace/Speed", "Avg HR", "Max HR", "Avg Power", "NP"]
        rows = []
        for session in info.messages.get("session", []):
            sport = str(session.get("sport") or "").lower()
            speed = value(session, "enhanced_avg_speed", "avg_speed")
            if is_swim(sport):
                pace_or_speed = pace_from_speed(speed, swim=True)
            elif is_run(sport):
                pace_or_speed = gap_label_from_summary(speed, value(session, "total_distance"), value(session, "total_ascent"))
            elif is_bike(sport):
                pace_or_speed = f"{float(speed) * 3.6:.1f}km/h" if speed not in (None, "", 0) else "-"
            else:
                pace_or_speed = pace_from_speed(speed) if speed not in (None, "", 0) else "-"
            rows.append([
                sport_label(sport),
                seconds_to_hms(value(session, "total_timer_time")),
                meters_to_km(value(session, "total_distance")),
                pace_or_speed,
                fmt(value(session, "avg_heart_rate"), "bpm"),
                fmt(value(session, "max_heart_rate"), "bpm"),
                fmt(value(session, "avg_power"), "W"),
                fmt(value(session, "normalized_power"), "W"),
            ])
        return header, rows
    if is_bike(info.sport):
        header = ["Lap", "Dauer", "Distanz", "Avg Power", "NP", "Avg HR", "Max HR", "Cadence", "L/R Balance", "Torque Eff."]
        rows = []
        for idx, lap in enumerate(info.laps[:25], 1):
            rows.append([
                str(idx),
                seconds_to_hms(value(lap, "total_timer_time")),
                meters_to_km(value(lap, "total_distance")),
                fmt(value(lap, "avg_power"), "W"),
                fmt(value(lap, "normalized_power"), "W"),
                fmt(value(lap, "avg_heart_rate"), "bpm"),
                fmt(value(lap, "max_heart_rate"), "bpm"),
                fmt(value(lap, "avg_cadence"), "rpm"),
                fmt(value(lap, "avg_left_right_balance")),
                torque_efficiency(lap),
            ])
        return header, rows
    if is_run(info.sport):
        header = ["Lap", "Dauer", "Distanz", "GAP", "Avg HR", "Max HR", "Cadence", "Stride", "GCT", "Vert."]
        rows = []
        for idx, lap in enumerate(info.laps[:25], 1):
            rows.append([
                str(idx),
                seconds_to_hms(value(lap, "total_timer_time")),
                meters_to_km(value(lap, "total_distance")),
                gap_label_from_summary(
                    value(lap, "enhanced_avg_speed", "avg_speed"),
                    value(lap, "total_distance"),
                    value(lap, "total_ascent"),
                ),
                fmt(value(lap, "avg_heart_rate"), "bpm"),
                fmt(value(lap, "max_heart_rate"), "bpm"),
                fmt(value(lap, "avg_cadence", "avg_running_cadence"), "spm"),
                fmt(value(lap, "avg_step_length"), "mm"),
                fmt(value(lap, "avg_stance_time"), "ms"),
                fmt(value(lap, "avg_vertical_oscillation"), "mm"),
            ])
        return header, rows
    header = ["Lap", "Dauer", "Distanz", "Pace", "Avg HR", "Max HR", "Zone"]
    rows = []
    for idx, lap in enumerate(info.laps[:25], 1):
        pace_value = value(lap, "enhanced_avg_speed", "avg_speed")
        pace_label = pace_from_speed(pace_value, swim=is_swim(info.sport))
        zone = "-"
        if is_swim(info.sport):
            pace_seconds = 100 / float(pace_value) if pace_value not in (None, "", 0) else None
            zone = classify_swim_zone(pace_seconds) or "-"
        rows.append([
            str(idx),
            seconds_to_hms(value(lap, "total_timer_time")),
            fmt(value(lap, "total_distance"), "m"),
            pace_label,
            fmt(value(lap, "avg_heart_rate"), "bpm"),
            fmt(value(lap, "max_heart_rate"), "bpm"),
            zone,
        ])
    return header, rows


def zone_table_lines(info: FitInfo) -> list[str]:
    if is_multisport(info.sport):
        lines: list[str] = []
        for session in info.messages.get("session", []):
            sport = str(session.get("sport") or "").lower()
            if not (is_swim(sport) or is_bike(sport) or is_run(sport)):
                continue
            segment_info = segment_info_for_session(info, session)
            lines.extend([f"### {sport_label(sport)}", ""])
            lines.extend(zone_table_lines(segment_info))
            lines.append("")
        return lines[:-1] if lines else ["Keine Zonendaten verfügbar."]
    totals = zone_distribution(info)
    if not totals:
        return ["Keine Zonendaten verfügbar."]
    header = ["Zone", "Distanz"] if is_swim(info.sport) else ["Zone", "Zeit"]
    rows = []
    for zone in sport_zone_order(info.sport):
        value_item = totals.get(zone, 0.0)
        if is_swim(info.sport):
            rows.append([zone, format_zone_value(info, value_item)])
        else:
            rows.append([zone, format_zone_value(info, value_item)])
    return markdown_table(header, rows)


def segment_info_for_session(info: FitInfo, session: dict[str, Any]) -> FitInfo:
    start = session.get("start_time")
    duration = value(session, "total_timer_time")
    end = start + timedelta(seconds=float(duration)) if isinstance(start, datetime) and duration not in (None, "") else None

    def in_segment(item: dict[str, Any]) -> bool:
        timestamp = item.get("start_time") or item.get("timestamp")
        return isinstance(timestamp, datetime) and isinstance(start, datetime) and isinstance(end, datetime) and start <= timestamp < end

    return FitInfo(
        path=info.path,
        messages=info.messages,
        session=session,
        laps=[lap for lap in info.laps if in_segment(lap)],
        records=[record for record in info.records if in_segment(record)],
        start=start if isinstance(start, datetime) else None,
        sport=str(session.get("sport") or "").lower(),
    )


def torque_efficiency(lap: dict[str, Any]) -> str:
    left = value(lap, "avg_left_torque_effectiveness")
    right = value(lap, "avg_right_torque_effectiveness")
    if left in (None, "") and right in (None, ""):
        return "-"
    return f"{fmt(left, '%')}/{fmt(right, '%')}"


def markdown_table(header: list[str], rows: list[list[str]]) -> list[str]:
    if not rows:
        return []
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("-" for _ in header) + "|"]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return lines


def summarize(info: FitInfo, tss: str) -> list[str]:
    session = info.session
    if is_multisport(info.sport):
        lines = [
            f"- Sport: {sport_label(info.sport)}",
            f"- Start: {info.start.isoformat(sep=' ') if info.start else '-'}",
            f"- Dauer: {seconds_to_hms(value(session, 'total_timer_time'))}",
            f"- Verstrichene Zeit: {seconds_to_hms(value(session, 'total_elapsed_time'))}",
            f"- Distanz: {meters_to_km(value(session, 'total_distance'))}",
            f"- Kalorien: {fmt(value(session, 'total_calories'), 'kcal')}",
            f"- Avg HR: {fmt(value(session, 'avg_heart_rate'), 'bpm')}",
            f"- Max HR: {fmt(value(session, 'max_heart_rate'), 'bpm')}",
            f"- TSS: {tss}",
            f"- Aerobic Training Effect: {fmt(value(session, 'total_training_effect'), digits=1)}",
            f"- Anaerobic Training Effect: {fmt(value(session, 'total_anaerobic_training_effect'), digits=1)}",
        ]
        for segment in info.messages.get("session", []):
            segment_info = segment_info_for_session(info, segment)
            lines.append(
                f"- {sport_label(segment_info.sport)}: {seconds_to_hms(value(segment, 'total_timer_time'))}, "
                f"{meters_to_km(value(segment, 'total_distance'))}, "
                f"{fmt(value(segment, 'avg_heart_rate'), 'bpm')} avg HR"
            )
        return lines
    swim = is_swim(info.sport)
    lines = [
        f"- Sport: {sport_label(info.sport)}",
        f"- Start: {info.start.isoformat(sep=' ') if info.start else '-'}",
        f"- Dauer: {seconds_to_hms(value(session, 'total_timer_time'))}",
        f"- Verstrichene Zeit: {seconds_to_hms(value(session, 'total_elapsed_time'))}",
        f"- Distanz: {fmt(value(session, 'total_distance'), 'm')}",
        f"- Kalorien: {fmt(value(session, 'total_calories'), 'kcal')}",
    ]
    if is_bike(info.sport):
        lines.extend([
            f"- Avg Power: {fmt(value(session, 'avg_power'), 'W')}",
            f"- Normalized Power: {fmt(value(session, 'normalized_power'), 'W')}",
            f"- Max Power: {fmt(value(session, 'max_power'), 'W')}",
        ])
    if is_run(info.sport) or is_swim(info.sport):
        if is_run(info.sport):
            lines.append(f"- Avg GAP: {gap_label_from_summary(value(session, 'enhanced_avg_speed', 'avg_speed'), value(session, 'total_distance'), value(session, 'total_ascent'))}")
        else:
            lines.append(f"- Avg Pace: {pace_from_speed(value(session, 'enhanced_avg_speed', 'avg_speed'), swim=swim)}")
    lines.extend([
        f"- Avg HR: {fmt(value(session, 'avg_heart_rate'), 'bpm')}",
        f"- Max HR: {fmt(value(session, 'max_heart_rate'), 'bpm')}",
        f"- TSS: {tss}",
        f"- Aerobic Training Effect: {fmt(value(session, 'total_training_effect'), digits=1)}",
        f"- Anaerobic Training Effect: {fmt(value(session, 'total_anaerobic_training_effect'), digits=1)}",
        f"- Effizienz: {efficiency(info)}",
        f"- HR-Drift: {hr_drift(info)}",
    ])
    return lines


def report(info: FitInfo, tss: str, activity: dict[str, Any] | None) -> str:
    session = info.session
    duration = seconds_to_hms(value(session, "total_timer_time"))
    avg_hr = fmt(value(session, "avg_heart_rate"), "bpm")
    max_hr = fmt(value(session, "max_heart_rate"), "bpm")
    aerobic = fmt(value(session, "total_training_effect"), digits=1)
    anaerobic = fmt(value(session, "total_anaerobic_training_effect"), digits=1)
    if is_multisport(info.sport):
        sentences = [
            f"Die Einheit war ein Triathlon über {duration} mit {avg_hr} im Schnitt und {max_hr} maximal.",
            f"Mit TSS {tss} und Training Effect aerob {aerobic}/anaerob {anaerobic} war der Wettkampfreiz hoch und planungsrelevant.",
            "Die Segmente werden getrennt bewertet, weil Schwimmen, Radfahren, Wechsel und Laufen unterschiedliche Belastungsmarker haben.",
            "Für die Planung sind vor allem die Radleistung, der anschließende Laufverlauf und die Wechselzeiten relevant.",
        ]
    elif is_bike(info.sport):
        avg_power = fmt(value(session, "avg_power"), "W")
        np_power = fmt(value(session, "normalized_power"), "W")
        sentences = [
            f"Die Einheit war eine Bike-Einheit über {duration} mit {avg_power} im Schnitt und {np_power} NP.",
            f"Mit TSS {tss}, {avg_hr} im Schnitt und {max_hr} maximal war der Reiz insgesamt gut einzuordnen.",
            f"Der Training Effect lag aerob bei {aerobic} und anaerob bei {anaerobic}.",
            "Für die Planung ist besonders relevant, ob die Leistung stabil zu Herzfrequenz und Kontext passt.",
        ]
    elif is_run(info.sport):
        gap = gap_label_from_summary(
            value(session, "enhanced_avg_speed", "avg_speed"),
            value(session, "total_distance"),
            value(session, "total_ascent"),
        )
        sentences = [
            f"Die Einheit war ein Lauf über {duration} mit einem durchschnittlichen GAP von {gap}.",
            f"Mit TSS {tss}, {avg_hr} im Schnitt und {max_hr} maximal war der Reiz insgesamt gut einzuordnen.",
            f"Der Training Effect lag aerob bei {aerobic} und anaerob bei {anaerobic}.",
            "Für die Planung ist besonders relevant, ob GAP, Herzfrequenz, Pausen und mögliche Beschwerden zusammenpassen.",
        ]
    elif is_swim(info.sport):
        pace = pace_from_speed(value(session, "enhanced_avg_speed", "avg_speed"), swim=True)
        distance = fmt(value(session, "total_distance"), "m")
        sentences = [
            f"Die Einheit war eine Schwimmeinheit über {distance} mit einer durchschnittlichen Pace von {pace}.",
            f"Mit TSS {tss} und Training Effect aerob {aerobic}/anaerob {anaerobic} war der Reiz insgesamt gut einzuordnen.",
            "Für die Planung ist besonders relevant, ob Umfang, Pace und Set-Struktur zum geplanten Swim-Typ passen.",
            "Herzfrequenzdaten im Schwimmen werden nur ergänzend bewertet, weil sie je nach Sensor und Wasserlage weniger stabil sein können.",
        ]
    else:
        sentences = [
            f"Die Einheit dauerte {duration} und wurde als {sport_label(info.sport)} erkannt.",
            f"Mit TSS {tss}, {avg_hr} im Schnitt und {max_hr} maximal war der Reiz insgesamt gut einzuordnen.",
            f"Der Training Effect lag aerob bei {aerobic} und anaerob bei {anaerobic}.",
            "Für die Planung wird diese Einheit vor allem als zusätzlicher Belastungskontext berücksichtigt.",
        ]
    drift = hr_drift(info)
    if drift not in {"-", "nicht sinnvoll berechenbar"}:
        sentences.append(f"Die HR-Drift lag bei {drift} und hilft bei der Einordnung der aeroben Stabilität.")
    elif is_bike(info.sport) or is_run(info.sport):
        sentences.append("Eine belastbare HR-Drift war aus dieser Datei nicht sinnvoll ableitbar.")
    if activity is None:
        sentences.append("Kein eindeutiges Intervals.icu-Match wurde gefunden, daher sollte der TSS-Wert besonders plausibilisiert werden.")
    else:
        sentences.append("Die Einheit sollte zusammen mit subjektivem Feedback und dem Wochenkontext für die weitere Planung bewertet werden.")
    if tss == "-":
        sentences.append("Für die Load-Steuerung ist die Einheit nur eingeschränkt nutzbar, bis eine belastbare TSS-Quelle verfügbar ist.")
    else:
        sentences.append("Für die Load-Steuerung kann der TSS-Wert genutzt werden, sollte aber bei auffälliger Dauer oder Intensität gegengeprüft werden.")
    return " ".join(sentences[:6])


def write_summary(info: FitInfo, activity: dict[str, Any] | None, dry_run: bool, warnings: list[str]) -> None:
    tss = get_tss(info, activity, warnings)
    target = info.path.with_suffix(".md")
    lines = [
        f"# {info.path.stem}",
        "",
        f"Quelle: `{info.path.name}`",
        f"Auswertung: {date.today().isoformat()}",
        "",
        "## Kurzfassung",
        "",
        *summarize(info, tss),
        "",
        "## Bericht",
        "",
        report(info, tss, activity),
        "",
        "## Einordnung",
        "",
        "- Automatisch erzeugte FIT-Auswertung; Plausibilität durch das LLM vor Planerzeugung erforderlich.",
    ]
    if activity is None:
        lines.append("- Kein eindeutiges Intervals.icu-Activity-Match gefunden; TSS nutzt FIT-Fallback oder `-`.")
    lines.extend(["", "## Zonen", ""])
    lines.extend(zone_table_lines(info))
    lines.extend(["", "## Segmente" if is_multisport(info.sport) else "## Laps", ""])
    header, rows = lap_rows(info)
    lines.extend(markdown_table(header, rows) or ["Keine Lap-Daten verfügbar."])
    text = "\n".join(lines) + "\n"
    if dry_run:
        print(f"Would write {target.relative_to(ROOT)}")
        return
    write_text_atomic(target, text)
    print(f"WROTE {target.relative_to(ROOT)}")


def extract_bike_ftp(info: FitInfo) -> int | None:
    ftp = value(info.session, "threshold_power")
    if ftp:
        return round(float(ftp))
    for tiz in info.messages.get("time_in_zone", []):
        ftp = value(tiz, "functional_threshold_power")
        if ftp:
            return round(float(ftp))
    return None


def extract_run_threshold(info: FitInfo) -> tuple[int | None, str | None]:
    lthr = None
    ltspeed = None
    for msg in info.messages.get("unknown_79", []) + info.messages.get("user_metrics", []):
        lthr = lthr or value(msg, "unknown_11", "lthr")
        ltspeed = ltspeed or value(msg, "unknown_13", "ltspeed")
    for msg in info.messages.get("zones_target", []) + info.messages.get("time_in_zone", []):
        lthr = lthr or value(msg, "threshold_heart_rate")
    for msg in info.messages.get("user_profile", []):
        ltspeed = ltspeed or value(msg, "unknown_37", "ltspeed")
    pace = None
    if ltspeed:
        raw = float(ltspeed)
        kmh = raw / 10 if raw > 100 else raw
        if kmh > 0:
            pace = pace_from_kmh(kmh)
    return (round(float(lthr)) if lthr else None, pace)


def extract_vo2max(info: FitInfo) -> float | None:
    for msg in info.messages.get("unknown_140", []) + info.messages.get("activity_metrics", []):
        raw = value(msg, "unknown_7", "vo2_max")
        if raw and float(raw) > 0:
            return float(raw) / 18724.571428571428
    for msg in info.messages.get("unknown_79", []) + info.messages.get("user_metrics", []):
        raw = value(msg, "unknown_0", "vo2_max")
        if raw and float(raw) > 0:
            return float(raw) / 292.57142857142856
    return None


def read_table(path: Path) -> tuple[list[str], list[list[str]]]:
    lines = [
        line.strip()
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    header = [cell.strip() for cell in lines[0].strip("|").split("|")]
    rows = [[cell.strip() for cell in line.strip("|").split("|")] for line in lines[2:] if line.startswith("|")]
    return header, rows


def prepend_if_changed(path: Path, values: list[str], dry_run: bool) -> None:
    header, rows = read_table(path)
    if any(row == values for row in rows):
        return
    new_rows = normalize_history_rows(rows + [values])
    if new_rows == rows:
        return
    content = [
        "| " + " | ".join(header) + " |",
        "|" + "|".join("-" for _ in header) + "|",
    ]
    content.extend("| " + " | ".join(row) + " |" for row in new_rows)
    if dry_run:
        print(f"Would update {path.relative_to(ROOT)} with {' | '.join(values)}")
        return
    write_text_atomic(path, "\n".join(content) + "\n")
    print(f"UPDATED {path.relative_to(ROOT)}")


def normalize_history_rows(rows: list[list[str]]) -> list[list[str]]:
    def row_date(row: list[str]) -> str:
        return row[0] if row else ""

    unique: list[list[str]] = []
    for row in rows:
        if row not in unique:
            unique.append(row)
    ascending = sorted(unique, key=row_date)
    changed: list[list[str]] = []
    last_values: list[str] | None = None
    for row in ascending:
        current_values = row[1:]
        if current_values == last_values:
            continue
        changed.append(row)
        last_values = current_values
    return sorted(changed, key=row_date, reverse=True)


def threshold_date(info: FitInfo, all_infos: list[FitInfo]) -> str | None:
    if not info.start:
        return None
    same_sport = [
        other
        for other in all_infos
        if other.start and other.start < info.start and other.sport == info.sport
    ]
    if not same_sport:
        return None
    return max(same_sport, key=lambda item: item.start or datetime.min).start.date().isoformat()


def update_histories(info: FitInfo, all_infos: list[FitInfo], dry_run: bool, warnings: list[str]) -> None:
    if is_bike(info.sport):
        ftp = extract_bike_ftp(info)
        dated_to = threshold_date(info, all_infos)
        if ftp and dated_to:
            prepend_if_changed(THRESHOLDS_DIR / "thresholds_bike.md", [dated_to, str(ftp)], dry_run)
        elif ftp and not dated_to:
            warnings.append(f"{info.path.name}: Bike FTP found but not written because no previous Bike FIT exists for correct threshold dating")
        else:
            warnings.append(f"{info.path.name}: no Bike FTP threshold found")
    if is_run(info.sport):
        lthr, pace = extract_run_threshold(info)
        dated_to = threshold_date(info, all_infos)
        if lthr and pace and dated_to:
            prepend_if_changed(THRESHOLDS_DIR / "thresholds_run.md", [dated_to, str(lthr), pace], dry_run)
        elif lthr and pace and not dated_to:
            warnings.append(f"{info.path.name}: Run threshold found but not written because no previous Run FIT exists for correct threshold dating")
        else:
            warnings.append(f"{info.path.name}: no complete Run threshold found")
    if is_bike(info.sport) or is_run(info.sport):
        vo2 = extract_vo2max(info)
        if vo2:
            path = VO2MAX_DIR / ("VO2max_bike.md" if is_bike(info.sport) else "VO2max_run.md")
            day = info.start.date().isoformat() if info.start else date.today().isoformat()
            prepend_if_changed(path, [day, f"{vo2:.1f}".rstrip("0").rstrip(".")], dry_run)
        else:
            warnings.append(f"{info.path.name}: no VO2max found")


def needs_analysis(path: Path) -> bool:
    md = path.with_suffix(".md")
    return not md.exists() or path.stat().st_mtime > md.stat().st_mtime


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze FIT files into Markdown summaries.")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing.")
    parser.add_argument("--force", action="store_true", help="Recreate all Activity Markdown summaries, even when they are not older than the FIT file.")
    args = parser.parse_args()

    fit_paths = sorted(ACTIVITIES_DIR.rglob("*.fit"))
    infos = [read_fit(path) for path in fit_paths]
    open_infos = infos if args.force else [info for info in infos if needs_analysis(info.path)]
    activities, warnings = load_intervals_activities(open_infos or infos)

    print(f"FIT files: {len(fit_paths)}")
    print(f"Open FIT files: {len(open_infos)}")
    for info in open_infos:
        activity = match_activity(info, activities)
        if activity is None:
            warnings.append(f"{info.path.name}: no unique Intervals.icu match")
        write_summary(info, activity, args.dry_run, warnings)
        update_histories(info, infos, args.dry_run, warnings)

    if warnings:
        print("WARNINGS:")
        for warning in warnings:
            print(f"- {warning}")
    return 0 if not warnings else 2


if __name__ == "__main__":
    raise SystemExit(main())
