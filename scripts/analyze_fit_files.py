#!/usr/bin/env python3
"""Analyze FIT files and write same-name Markdown summaries."""

from __future__ import annotations

import argparse
import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import fitdecode

from intervals_icu_client import IntervalsClient, IntervalsError, ROOT, sanitize_activity_name


ACTIVITIES_DIR = ROOT / "data" / "activities"
THRESHOLDS_DIR = ROOT / "data" / "thresholds"
VO2MAX_DIR = ROOT / "data" / "VO2max"


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
    session = (messages.get("session") or [{}])[0]
    laps = messages.get("lap") or []
    records = messages.get("record") or []
    start = session.get("start_time")
    sport = str(session.get("sport") or session.get("sub_sport") or "").lower()
    if not sport:
        sport = infer_sport_from_name(path.name)
    return FitInfo(path, messages, session, laps, records, start, sport)


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


def sport_label(sport: str) -> str:
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
    for item in candidates:
        activity_name = normalize_name(str(item.get("name") or ""))
        if fit_name and (fit_name in activity_name or activity_name in fit_name):
            return item
    return candidates[0] if len(candidates) == 1 else None


def get_tss(info: FitInfo, activity: dict[str, Any] | None, warnings: list[str]) -> str:
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
        speed = value(info.session, "enhanced_avg_speed", "avg_speed")
        if not speed:
            return "-"
        return f"{float(speed) / float(avg_hr):.4f}m/s/bpm ({pace_from_speed(speed)} @ {round(float(avg_hr))}bpm)"
    return "-"


def hr_drift(info: FitInfo) -> str:
    name = info.path.stem.lower()
    if not (is_bike(info.sport) or is_run(info.sport)):
        return "-"
    if "basic" not in name and "long" not in name:
        return "-"
    points: list[tuple[datetime, float, float]] = []
    for rec in info.records:
        timestamp = rec.get("timestamp")
        hr = rec.get("heart_rate")
        work = rec.get("power") if is_bike(info.sport) else value(rec, "enhanced_speed", "speed")
        if isinstance(timestamp, datetime) and hr and work and float(hr) > 0 and float(work) > 0:
            points.append((timestamp, float(hr), float(work)))
    if len(points) < 60:
        return "nicht sinnvoll berechenbar"
    points.sort(key=lambda item: item[0])
    midpoint = len(points) // 2
    first, second = points[:midpoint], points[midpoint:]
    ef1 = sum(work for _, _, work in first) / sum(hr for _, hr, _ in first)
    ef2 = sum(work for _, _, work in second) / sum(hr for _, hr, _ in second)
    if ef1 <= 0:
        return "nicht sinnvoll berechenbar"
    drift = (ef1 - ef2) / ef1 * 100
    label = "stabil" if abs(drift) < 3 else "moderat driftend" if abs(drift) < 7 else "deutlich driftend"
    return f"{drift:.1f}% ({label})"


def lap_rows(info: FitInfo) -> tuple[list[str], list[list[str]]]:
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
        header = ["Lap", "Dauer", "Distanz", "Pace", "Avg HR", "Max HR", "Cadence", "Stride", "GCT", "Vert."]
        rows = []
        for idx, lap in enumerate(info.laps[:25], 1):
            rows.append([
                str(idx),
                seconds_to_hms(value(lap, "total_timer_time")),
                meters_to_km(value(lap, "total_distance")),
                pace_from_speed(value(lap, "enhanced_avg_speed", "avg_speed")),
                fmt(value(lap, "avg_heart_rate"), "bpm"),
                fmt(value(lap, "max_heart_rate"), "bpm"),
                fmt(value(lap, "avg_cadence", "avg_running_cadence"), "spm"),
                fmt(value(lap, "avg_step_length"), "mm"),
                fmt(value(lap, "avg_stance_time"), "ms"),
                fmt(value(lap, "avg_vertical_oscillation"), "mm"),
            ])
        return header, rows
    header = ["Lap", "Dauer", "Distanz", "Pace", "Avg HR", "Max HR"]
    rows = []
    for idx, lap in enumerate(info.laps[:25], 1):
        rows.append([
            str(idx),
            seconds_to_hms(value(lap, "total_timer_time")),
            fmt(value(lap, "total_distance"), "m"),
            pace_from_speed(value(lap, "enhanced_avg_speed", "avg_speed"), swim=is_swim(info.sport)),
            fmt(value(lap, "avg_heart_rate"), "bpm"),
            fmt(value(lap, "max_heart_rate"), "bpm"),
        ])
    return header, rows


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
        "## Einordnung",
        "",
        "- Automatisch erzeugte FIT-Auswertung; Plausibilitaet durch das LLM vor Planerzeugung erforderlich.",
    ]
    if activity is None:
        lines.append("- Kein eindeutiges Intervals.icu-Activity-Match gefunden; TSS nutzt FIT-Fallback oder `-`.")
    lines.extend(["", "## Laps", ""])
    header, rows = lap_rows(info)
    lines.extend(markdown_table(header, rows) or ["Keine Lap-Daten verfuegbar."])
    text = "\n".join(lines) + "\n"
    if dry_run:
        print(f"Would write {target.relative_to(ROOT)}")
        return
    target.write_text(text, encoding="utf-8")
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
    lines = [line.strip() for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines() if line.strip()]
    header = [cell.strip() for cell in lines[0].strip("|").split("|")]
    rows = [[cell.strip() for cell in line.strip("|").split("|")] for line in lines[2:] if line.startswith("|")]
    return header, rows


def prepend_if_changed(path: Path, values: list[str], dry_run: bool) -> None:
    header, rows = read_table(path)
    if rows and rows[0][1:] == values[1:]:
        return
    new_rows = [values] + rows
    content = [
        "| " + " | ".join(header) + " |",
        "|" + "|".join("-" for _ in header) + "|",
    ]
    content.extend("| " + " | ".join(row) + " |" for row in new_rows)
    if dry_run:
        print(f"Would update {path.relative_to(ROOT)} with {' | '.join(values)}")
        return
    path.write_text("\n".join(content) + "\n", encoding="utf-8")
    print(f"UPDATED {path.relative_to(ROOT)}")


def threshold_date(info: FitInfo, all_infos: list[FitInfo]) -> str:
    if not info.start:
        return date.today().isoformat()
    same_sport = [
        other
        for other in all_infos
        if other.start and other.start < info.start and other.sport == info.sport
    ]
    if not same_sport:
        return info.start.date().isoformat()
    return max(same_sport, key=lambda item: item.start or datetime.min).start.date().isoformat()


def update_histories(info: FitInfo, all_infos: list[FitInfo], dry_run: bool, warnings: list[str]) -> None:
    if is_bike(info.sport):
        ftp = extract_bike_ftp(info)
        if ftp:
            prepend_if_changed(THRESHOLDS_DIR / "thresholds_bike.md", [threshold_date(info, all_infos), str(ftp)], dry_run)
        else:
            warnings.append(f"{info.path.name}: no Bike FTP threshold found")
    if is_run(info.sport):
        lthr, pace = extract_run_threshold(info)
        if lthr and pace:
            prepend_if_changed(THRESHOLDS_DIR / "thresholds_run.md", [threshold_date(info, all_infos), str(lthr), pace], dry_run)
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
    args = parser.parse_args()

    fit_paths = sorted(ACTIVITIES_DIR.rglob("*.fit"))
    infos = [read_fit(path) for path in fit_paths]
    open_infos = [info for info in infos if needs_analysis(info.path)]
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
