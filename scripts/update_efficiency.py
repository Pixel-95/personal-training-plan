#!/usr/bin/env python3
"""Estimate weekly bike and run output at fixed heart rates from efficiency JSON files."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import least_squares

from date_utils import monday_of_iso_week
from markdown_tables import read_table, render_table, write_text_atomic
from profile_paths import DATA_DIR


TARGETS = (130, 155)
LOCAL_BAND_BPM = 10
MAX_EXTRAPOLATION_BPM = 5
EXTRAPOLATION_WEIGHT = 0.5
BOOTSTRAP_SAMPLES = 1000
HEADER = [
    "ISO-Woche", "Sport", "Datenstand", "90-Tage-Fenster",
    "Wert @130 bpm", "95%-Untergrenze @130 bpm", "95%-Obergrenze @130 bpm",
    "Wert @155 bpm", "95%-Untergrenze @155 bpm", "95%-Obergrenze @155 bpm",
    "Einheit", "Punkte", "Aktivitäten", "Fit-Güte R²", "Status",
]


def activity_count(points: list[dict[str, Any]]) -> int:
    return len({point["activity"] for point in points})


def history_path() -> Path:
    return DATA_DIR / "efficiency" / "efficiency_history.md"


def pace_label(speed_mps: float) -> str:
    seconds = round(1000 / speed_mps)
    return f"{seconds // 60}:{seconds % 60:02d}"


def parse_pace(value: str) -> float | None:
    try:
        minutes, seconds = value.split(":", 1)
        total = int(minutes) * 60 + int(seconds)
        return 1000 / total if total > 0 else None
    except (AttributeError, ValueError):
        return None


def load_points(window_start: date, window_end: date) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {"bike": [], "run": []}
    for path in (DATA_DIR / "activities").rglob("*.efficiency.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            activity_date = date.fromisoformat(str(payload["start_time"])[:10])
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            continue
        if not window_start <= activity_date <= window_end:
            continue
        activity_id = str(path.relative_to(DATA_DIR / "activities")).replace("\\", "/")
        for sport, data in (payload.get("sports") or {}).items():
            if sport not in result:
                continue
            for point in data.get("points") or []:
                output = point.get("power_w") if sport == "bike" else point.get("gap_speed_mps")
                hr = point.get("heart_rate_bpm")
                if isinstance(hr, (int, float)) and isinstance(output, (int, float)) and hr > 0 and output > 0:
                    result[sport].append({"hr": float(hr), "output": float(output), "activity": activity_id, **point})
    return result


def activity_balanced(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for point in points:
        groups[(point["activity"], int(point["hr"] // 5) * 5)].append(point)
    balanced: list[dict[str, Any]] = []
    for group in groups.values():
        for point in group:
            balanced.append({**point, "weight": point.get("support_weight", 1.0) / len(group)})
    return balanced


def local_target_points(points: list[dict[str, Any]], target: int) -> list[dict[str, Any]]:
    """Select nearby activity points, permitting only short one-sided extrapolation."""
    by_activity: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for point in points:
        if abs(point["hr"] - target) <= LOCAL_BAND_BPM:
            by_activity[point["activity"]].append(point)
    selected: list[dict[str, Any]] = []
    for activity_points in by_activity.values():
        hrs = [point["hr"] for point in activity_points]
        if min(hrs) <= target <= max(hrs):
            support_weight = 1.0
        elif min(abs(hr - target) for hr in hrs) <= MAX_EXTRAPOLATION_BPM:
            support_weight = EXTRAPOLATION_WEIGHT
        else:
            continue
        selected.extend({**point, "support_weight": support_weight} for point in activity_points)
    return activity_balanced(selected)


def has_minimum_support(points: list[dict[str, Any]], *, robust: bool) -> bool:
    required_points, required_activities = (12, 4) if robust else (10, 3)
    return len(points) >= required_points and activity_count(points) >= required_activities


def fit(points: list[dict[str, Any]], *, minimum_points: int = 10) -> tuple[float, float, float] | None:
    if len(points) < minimum_points or activity_count(points) < 3:
        return None
    x = np.array([point["hr"] for point in points], dtype=float)
    y = np.array([point["output"] for point in points], dtype=float)
    weights = np.sqrt(np.array([point["weight"] for point in points], dtype=float))
    # A bootstrap resample can contain valid points at only one HR value. It
    # cannot identify a slope and must not be treated as a fitted sample.
    if np.ptp(x) < 0.5:
        return None
    result = least_squares(
        lambda params: (params[0] * x + params[1] - y) * weights,
        np.polyfit(x, y, 1),
        loss="huber",
        f_scale=max(np.std(y), 1.0),
    )
    slope, intercept = result.x
    predicted = slope * x + intercept
    average = np.average(y, weights=weights)
    total = np.sum(weights * (y - average) ** 2)
    r_squared = 1 - np.sum(weights * (y - predicted) ** 2) / total if total else 0.0
    return float(slope), float(intercept), float(r_squared)


def bootstrap_interval(points: list[dict[str, Any]], target: int) -> tuple[float, float] | None:
    activities: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for point in points:
        activities[point["activity"]].append(point)
    names = sorted(activities)
    if len(names) < 3:
        return None
    generator = np.random.default_rng(20260731 + target)
    estimates: list[float] = []
    for _ in range(BOOTSTRAP_SAMPLES):
        resampled: list[dict[str, Any]] = []
        for number, original_name in enumerate(generator.choice(names, size=len(names), replace=True)):
            resampled.extend({**point, "activity": f"{original_name}#{number}"} for point in activities[original_name])
        model = fit(activity_balanced(resampled), minimum_points=3)
        if model:
            estimate = model[0] * target + model[1]
            if estimate > 0 and math.isfinite(estimate):
                estimates.append(estimate)
    if len(estimates) < BOOTSTRAP_SAMPLES * .9:
        return None
    lower, upper = np.percentile(estimates, [2.5, 97.5])
    return float(lower), float(upper)


def calculate(points: list[dict[str, Any]]) -> dict[str, Any]:
    balanced_points = activity_balanced(points)
    values: dict[int, float | None] = {target: None for target in TARGETS}
    intervals: dict[int, tuple[float, float] | None] = {target: None for target in TARGETS}
    models: dict[int, tuple[float, float, float] | None] = {}
    local_sets: dict[int, list[dict[str, Any]]] = {}
    for target in TARGETS:
        local = local_target_points(points, target)
        local_sets[target] = local
        model = fit(local)
        models[target] = model
        if model:
            estimate = model[0] * target + model[1]
            if estimate > 0 and math.isfinite(estimate):
                values[target] = estimate
                intervals[target] = bootstrap_interval(local, target)
    has_values = all(value is not None for value in values.values())
    robust = has_values and all(has_minimum_support(local_sets[target], robust=True) for target in TARGETS)
    status = "robust" if robust else ("vorläufig" if any(value is not None for value in values.values()) else "nicht ausreichend abgedeckt")
    r_squared_values = [model[2] for model in models.values() if model is not None]
    return {"points": balanced_points, "local_sets": local_sets, "values": values, "intervals": intervals, "models": models, "r_squared": float(np.mean(r_squared_values)) if r_squared_values else None, "status": status}


def history_row(week: str, sport: str, as_of: date, start: date, result: dict[str, Any]) -> list[str]:
    formatted: list[str] = []
    for target in TARGETS:
        value = result["values"][target]
        interval = result["intervals"][target]
        if sport == "bike":
            formatted.extend([f"{value:.1f}" if value else "-", f"{interval[0]:.1f}" if interval else "-", f"{interval[1]:.1f}" if interval else "-"])
        else:
            formatted.extend([pace_label(value) if value else "-", pace_label(interval[0]) if interval else "-", pace_label(interval[1]) if interval else "-"])
    points = result["points"]
    return [week, sport, as_of.isoformat(), f"{start.isoformat()} bis {as_of.isoformat()}", *formatted, "W" if sport == "bike" else "min:sec/km", str(len(points)), str(activity_count(points)), f"{result['r_squared']:.3f}" if result["r_squared"] is not None else "-", result["status"]]


def upsert(rows: list[list[str]], new_rows: list[list[str]]) -> list[list[str]]:
    replacements = {(row[0], row[1]): row for row in new_rows}
    return sorted([*replacements.values(), *(row for row in rows if (row[0], row[1]) not in replacements)], key=lambda row: (row[0], row[1]), reverse=True)


def update(week: str, *, dry_run: bool = False) -> tuple[list[list[str]], dict[str, dict[str, Any]]]:
    week_start = monday_of_iso_week(week)
    if week_start > date.today():
        raise ValueError(f"Analysis week {week} has not started yet")
    as_of = min(week_start + timedelta(days=6), date.today())
    window_start = as_of - timedelta(days=89)
    results = {sport: calculate(sport_points) for sport, sport_points in load_points(window_start, as_of).items()}
    header, rows = read_table(history_path())
    if header and header != HEADER:
        rows = []
    updated = upsert(rows, [history_row(week, sport, as_of, window_start, result) for sport, result in results.items()])
    if not dry_run:
        write_text_atomic(history_path(), render_table(HEADER, updated))
    return updated, results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week", required=True, help="Analysis ISO week, e.g. 2026-W31.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    _, results = update(args.week, dry_run=args.dry_run)
    print(f"{'Would write' if args.dry_run else 'WROTE'} {history_path()}")
    for sport, result in results.items():
        print(f"{sport}: {result['status']}, {len(result['points'])} weighted points")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
