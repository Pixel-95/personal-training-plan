"""Deterministic extraction helpers for heart-rate efficiency analysis."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from statistics import mean, median, stdev
from typing import Any, Iterable


SCHEMA_VERSION = 1
FILTER_VERSION = "v1.5-asymmetric-equilibrium"
WINDOW_SECONDS = 180
WARMUP_MOVING_SECONDS = 600
POST_STOP_MOVING_SECONDS = 180
UPPER_HEART_RATE = 142.5
CONTEXT_SECONDS = 90
MAX_RECORD_GAP_SECONDS = 5
MAX_HR_STANDARD_DEVIATION = 3
MAX_HR_DRIFT_PER_MINUTE = {"lower": 0.75, "upper": 1.0}
MAX_OUTPUT_CV = {"bike": 0.12, "run": 0.03}
MAX_OUTPUT_TRANSITION = {"bike": 0.15, "run": 0.06}


def normalized_sport(value: object) -> str | None:
    sport = str(value or "").lower()
    if sport in {"cycling", "bike", "biking"}:
        return "bike"
    if sport in {"running", "run"}:
        return "run"
    return None


def record_value(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return None


def as_positive(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def grade_adjusted_speed(speed_mps: float, grade: float) -> float:
    grade = min(max(grade, -0.45), 0.45)
    cost_flat = 3.6
    cost_hilly = 155.4 * grade**5 - 30.4 * grade**4 - 43.3 * grade**3 + 46.3 * grade**2 + 19.5 * grade + cost_flat
    return speed_mps * cost_hilly / cost_flat


def component_records(messages: dict[str, list[dict[str, Any]]], sport: str, fallback: str) -> list[dict[str, Any]]:
    """Return records for a sport, including a component of a multisport FIT."""
    records = messages.get("record") or []
    if normalized_sport(fallback) == sport:
        return records
    selected: list[dict[str, Any]] = []
    for session in messages.get("session") or []:
        if normalized_sport(session.get("sport")) != sport:
            continue
        start = session.get("start_time")
        duration = as_positive(session.get("total_timer_time"))
        if not isinstance(start, datetime) or duration is None:
            continue
        end = start + timedelta(seconds=duration + 2)
        selected.extend(
            record for record in records
            if isinstance(record.get("timestamp"), datetime) and start <= record["timestamp"] <= end
        )
    return selected


def valid_samples(records: Iterable[dict[str, Any]], sport: str) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for record in records:
        timestamp = record.get("timestamp")
        hr = as_positive(record.get("heart_rate"))
        output = as_positive(record.get("power")) if sport == "bike" else as_positive(record_value(record, "enhanced_speed", "speed"))
        if not isinstance(timestamp, datetime) or hr is None or output is None:
            continue
        samples.append({
            "timestamp": timestamp,
            "hr": hr,
            "output": output,
            "distance": as_positive(record.get("distance")),
            "altitude": record_value(record, "enhanced_altitude", "altitude"),
            "temperature": record.get("temperature"),
        })
    return sorted(samples, key=lambda sample: sample["timestamp"])


def continuous_segments(samples: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Split valid moving samples at pauses, dropouts and stops."""
    segments: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for sample in samples:
        if current:
            gap = (sample["timestamp"] - current[-1]["timestamp"]).total_seconds()
            if gap <= 0 or gap > MAX_RECORD_GAP_SECONDS:
                segments.append(current)
                current = []
        current.append(sample)
    if current:
        segments.append(current)
    return segments


def coefficient_of_variation(values: list[float]) -> float:
    centre = mean(values)
    return stdev(values) / centre if len(values) > 1 and centre else math.inf


def linear_grade(samples: list[dict[str, Any]]) -> float | None:
    pairs = [
        (sample["distance"], float(sample["altitude"]))
        for sample in samples
        if sample["distance"] is not None and sample["altitude"] not in (None, "")
    ]
    if len(pairs) < 30:
        return None
    distances, altitudes = zip(*pairs)
    if max(distances) - min(distances) < 50:
        return None
    mean_distance = sum(distances) / len(distances)
    mean_altitude = sum(altitudes) / len(altitudes)
    denominator = sum((distance - mean_distance) ** 2 for distance in distances)
    if denominator <= 0:
        return None
    grade = sum((distance - mean_distance) * (altitude - mean_altitude) for distance, altitude in pairs) / denominator
    return grade if abs(grade) <= 0.25 else None


def linear_slope_per_minute(samples: list[dict[str, Any]], field: str) -> float:
    """Return a least-squares trend per minute for evenly or unevenly sampled records."""
    start = samples[0]["timestamp"]
    minutes = [(sample["timestamp"] - start).total_seconds() / 60 for sample in samples]
    values = [float(sample[field]) for sample in samples]
    mean_time = sum(minutes) / len(minutes)
    mean_value = sum(values) / len(values)
    denominator = sum((minute - mean_time) ** 2 for minute in minutes)
    if denominator <= 0:
        return 0.0
    return sum((minute - mean_time) * (value - mean_value) for minute, value in zip(minutes, values)) / denominator


def window_point(
    samples: list[dict[str, Any]],
    sport: str,
    preceding: list[dict[str, Any]],
    following: list[dict[str, Any]],
) -> dict[str, Any] | None:
    hrs = [sample["hr"] for sample in samples]
    outputs = [sample["output"] for sample in samples]
    if stdev(hrs) > MAX_HR_STANDARD_DEVIATION:
        return None
    upper_intensity = median(hrs) >= UPPER_HEART_RATE
    max_hr_drift = MAX_HR_DRIFT_PER_MINUTE["upper" if upper_intensity else "lower"]
    if abs(linear_slope_per_minute(samples, "hr")) > max_hr_drift:
        return None
    if not upper_intensity:
        equilibrium = [*preceding, *samples, *following]
        if (
            len(equilibrium) < 2
            or (equilibrium[-1]["timestamp"] - equilibrium[0]["timestamp"]).total_seconds() < 350
            or abs(linear_slope_per_minute(equilibrium, "hr")) > MAX_HR_DRIFT_PER_MINUTE["lower"]
        ):
            return None
    if coefficient_of_variation(outputs) > MAX_OUTPUT_CV[sport]:
        return None
    adjacent_sections = (preceding,) if upper_intensity else (preceding, following)
    for adjacent in adjacent_sections:
        if len(adjacent) < 60:
            continue
        adjacent_output = mean(sample["output"] for sample in adjacent)
        change = abs(mean(outputs) - adjacent_output) / adjacent_output if adjacent_output else math.inf
        if change > MAX_OUTPUT_TRANSITION[sport]:
            return None
    point: dict[str, Any] = {
        "timestamp": samples[0]["timestamp"].isoformat(),
        "duration_s": WINDOW_SECONDS,
        "heart_rate_bpm": round(median(hrs), 2),
        "temperature_c": median([float(sample["temperature"]) for sample in samples if sample["temperature"] not in (None, "")]) if any(sample["temperature"] not in (None, "") for sample in samples) else None,
    }
    if sport == "bike":
        point["power_w"] = round(median(outputs), 2)
        return point
    grade = linear_grade(samples)
    gap_speed = median(outputs) if grade is None else grade_adjusted_speed(median(outputs), grade)
    point["gap_speed_mps"] = round(gap_speed, 4)
    point["gap_method"] = "grade_adjusted" if grade is not None else "pace_fallback"
    return point


def extract_points(records: Iterable[dict[str, Any]], sport: str) -> list[dict[str, Any]]:
    """Return stable, non-overlapping 180-second points after warm-up and pauses."""
    points: list[dict[str, Any]] = []
    moving_before = 0.0
    for segment in continuous_segments(valid_samples(records, sport)):
        if len(segment) < 2:
            continue
        segment_duration = (segment[-1]["timestamp"] - segment[0]["timestamp"]).total_seconds()
        offset_seconds = 0
        while True:
            start = segment[0]["timestamp"] + timedelta(seconds=offset_seconds)
            index = next((position for position, sample in enumerate(segment) if sample["timestamp"] >= start), len(segment))
            if index == len(segment):
                break
            end = start + timedelta(seconds=WINDOW_SECONDS)
            window = [sample for sample in segment[index:] if sample["timestamp"] < end]
            if not window or (window[-1]["timestamp"] - start).total_seconds() < WINDOW_SECONDS - 1:
                break
            elapsed_in_segment = (start - segment[0]["timestamp"]).total_seconds()
            if moving_before + elapsed_in_segment >= WARMUP_MOVING_SECONDS and elapsed_in_segment >= POST_STOP_MOVING_SECONDS:
                preceding_start = start - timedelta(seconds=CONTEXT_SECONDS)
                preceding = [sample for sample in segment if preceding_start <= sample["timestamp"] < start]
                following_end = end + timedelta(seconds=CONTEXT_SECONDS)
                following = [sample for sample in segment if end <= sample["timestamp"] < following_end]
                point = window_point(window, sport, preceding, following)
                is_upper = point is not None and point["heart_rate_bpm"] >= UPPER_HEART_RATE
                if point is not None and (is_upper or offset_seconds % WINDOW_SECONDS == 0):
                    points.append(point)
            offset_seconds += 90
        moving_before += max(segment_duration, 0)
    return points
