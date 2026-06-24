#!/usr/bin/env python3
"""Update canonical health Markdown histories from Intervals.icu wellness data."""

from __future__ import annotations

import argparse
import math
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from intervals_icu_client import IntervalsClient, ROOT, date_range_from_days, load_env, read_csv_rows


HEALTH_DIR = ROOT / "data" / "health"


TABLES = {
    "resting_heart_rate.md": ["Datum", "Ruhepuls / bpm"],
    "sleep.md": ["Datum", "Schlafdauer / hh:mm", "Sleepscore"],
    "steps.md": ["Datum", "Schritte", "7-Tage-Mittel-Schritte"],
    "weight.md": [
        "Datum",
        "Gewicht / kg",
        "7-Tage-Mittel-Gewicht / kg",
        "Körperfettanteil / %",
        "7-Tage-Mittel-Körperfettanteil / %",
    ],
    "hrv.md": [
        "Datum",
        "Tages-RMSSD / ms",
        "7-Tage-RMSSD / ms",
        "90-Tage-RMSSD-Grenze unten / ms",
        "90-Tage-RMSSD-Grenze oben / ms",
    ],
}


def parse_table(path: Path) -> tuple[list[str], dict[str, list[str]]]:
    if not path.exists():
        return TABLES[path.name], {}
    lines = [line.strip() for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines() if line.strip()]
    if len(lines) < 2:
        return TABLES[path.name], {}
    header = [cell.strip() for cell in lines[0].strip("|").split("|")]
    rows: dict[str, list[str]] = {}
    for line in lines[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if cells and cells[0]:
            rows[cells[0]] = cells
    return header, rows


def write_table(path: Path, header: list[str], rows: dict[str, list[str]], dry_run: bool) -> None:
    ordered = sorted(rows.values(), key=lambda cells: cells[0], reverse=True)
    content = [
        "| " + " | ".join(header) + " |",
        "|" + "|".join("-" for _ in header) + "|",
    ]
    content.extend("| " + " | ".join(cells[: len(header)]) + " |" for cells in ordered)
    text = "\n".join(content) + "\n"
    if dry_run:
        print(f"Would write {path.relative_to(ROOT)} ({len(ordered)} rows)")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def date_iter(oldest: date, newest: date) -> list[date]:
    days = []
    current = oldest
    while current <= newest:
        days.append(current)
        current += timedelta(days=1)
    return days


def fmt_int(value: str | None) -> str:
    if value in (None, ""):
        return "-"
    try:
        return str(round(float(value)))
    except ValueError:
        return "-"


def fmt_float(value: str | None, digits: int = 1) -> str:
    if value in (None, ""):
        return "-"
    try:
        return f"{float(value):.{digits}f}".rstrip("0").rstrip(".")
    except ValueError:
        return "-"


def fmt_fixed_float(value: float | None, digits: int) -> str:
    if value is None:
        return "-"
    return f"{value:.{digits}f}"


def fmt_sleep(seconds: str | None) -> str:
    if seconds in (None, ""):
        return "-"
    try:
        total_minutes = round(float(seconds) / 60)
    except ValueError:
        return "-"
    return f"{total_minutes // 60}:{total_minutes % 60:02d}"


def existing_or_missing(rows: dict[str, list[str]], key: str, index: int) -> str:
    existing = rows.get(key)
    if existing and len(existing) > index and existing[index] not in ("", "-"):
        return existing[index]
    return "-"


def number_or_none(value: str | None) -> float | None:
    if value in (None, "", "-"):
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def geomean(values: list[float]) -> float:
    return math.exp(sum(math.log(v) for v in values) / len(values))


def stdevp_logs(values: list[float]) -> float:
    logs = [math.log(v) for v in values]
    mean = sum(logs) / len(logs)
    return math.sqrt(sum((item - mean) ** 2 for item in logs) / len(logs))


def trimmed_weight_mean(values: list[float]) -> float | None:
    if len(values) < 4:
        return None
    if len(values) >= 5:
        values = sorted(values)[1:-1]
    return sum(values) / len(values)


def recalc_hrv(rows: dict[str, list[str]]) -> None:
    daily = {date.fromisoformat(day): number_or_none(cells[1]) for day, cells in rows.items()}
    for day, cells in rows.items():
        current = date.fromisoformat(day)
        window7 = [
            daily.get(current - timedelta(days=offset))
            for offset in range(7)
            if daily.get(current - timedelta(days=offset)) is not None
        ]
        if len(window7) >= 4:
            cells[2] = str(round(geomean(window7)))
        else:
            cells[2] = "-"

        window90 = [
            daily.get(current - timedelta(days=offset))
            for offset in range(90)
            if daily.get(current - timedelta(days=offset)) is not None
        ]
        if len(window90) >= 45:
            gm = geomean(window90)
            sd = stdevp_logs(window90)
            cells[3] = str(round(gm / (math.exp(sd) ** 0.5)))
            cells[4] = str(round(gm * (math.exp(sd) ** 1.5)))
        else:
            cells[3] = "-"
            cells[4] = "-"


def recalc_weight(rows: dict[str, list[str]]) -> None:
    daily = {date.fromisoformat(day): number_or_none(cells[1] if len(cells) > 1 else None) for day, cells in rows.items()}
    bodyfat = {date.fromisoformat(day): number_or_none(cells[3] if len(cells) > 3 else None) for day, cells in rows.items()}
    for day, cells in rows.items():
        current = date.fromisoformat(day)
        while len(cells) < 5:
            cells.append("-")
        weight_window7 = [
            daily.get(current - timedelta(days=offset))
            for offset in range(7)
            if daily.get(current - timedelta(days=offset)) is not None
        ]
        weight_mean = trimmed_weight_mean(weight_window7)
        cells[2] = fmt_fixed_float(weight_mean, 2)
        bodyfat_window7 = [
            bodyfat.get(current - timedelta(days=offset))
            for offset in range(7)
            if bodyfat.get(current - timedelta(days=offset)) is not None
        ]
        bodyfat_mean = trimmed_weight_mean(bodyfat_window7)
        cells[4] = fmt_fixed_float(bodyfat_mean, 2)


def recalc_steps(rows: dict[str, list[str]]) -> None:
    daily = {date.fromisoformat(day): number_or_none(cells[1] if len(cells) > 1 else None) for day, cells in rows.items()}
    for day, cells in rows.items():
        current = date.fromisoformat(day)
        while len(cells) < 3:
            cells.append("-")
        window7 = [
            daily.get(current - timedelta(days=offset))
            for offset in range(7)
            if daily.get(current - timedelta(days=offset)) is not None
        ]
        if len(window7) >= 4:
            cells[2] = str(round(sum(window7) / len(window7)))
        else:
            cells[2] = "-"


def main() -> int:
    parser = argparse.ArgumentParser(description="Update health Markdown histories from Intervals.icu.")
    parser.add_argument("--days", type=int, default=30, help="Number of days to update.")
    parser.add_argument("--newest", default=date.today().isoformat(), help="Newest local date YYYY-MM-DD.")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing.")
    args = parser.parse_args()

    oldest, newest = date_range_from_days(args.days, args.newest)
    env = load_env()
    configured_start = env.get("intervals_icu_health_start") or env.get("INTERVALS_ICU_HEALTH_START")
    if configured_start:
        start_date = date.fromisoformat(configured_start)
        if oldest < start_date:
            oldest = start_date
    client = IntervalsClient.from_env()
    wellness_rows = read_csv_rows(client.wellness_csv(oldest, newest))
    by_date = {row.get("date", ""): row for row in wellness_rows if row.get("date")}
    missing: dict[str, list[str]] = defaultdict(list)
    warnings: list[str] = []

    tables = {name: parse_table(HEALTH_DIR / name) for name in TABLES}
    tables["weight.md"] = (TABLES["weight.md"], tables["weight.md"][1])

    for day in date_iter(oldest, newest):
        key = day.isoformat()
        row = by_date.get(key, {})

        hrv = tables["hrv.md"][1]
        hrv_value = fmt_int(row.get("hrv"))
        if hrv_value == "-":
            hrv_value = existing_or_missing(hrv, key, 1)
            missing["hrv"].append(key)
        hrv[key] = [key, hrv_value, "-", "-", "-"]

        rhr = tables["resting_heart_rate.md"][1]
        rhr_value = fmt_int(row.get("restingHR"))
        if rhr_value == "-":
            rhr_value = existing_or_missing(rhr, key, 1)
            missing["restingHR"].append(key)
        rhr[key] = [key, rhr_value]

        sleep = tables["sleep.md"][1]
        sleep_duration = fmt_sleep(row.get("sleepSecs"))
        sleep_score = fmt_int(row.get("sleepScore"))
        if sleep_duration == "-":
            sleep_duration = existing_or_missing(sleep, key, 1)
            missing["sleepSecs"].append(key)
        if sleep_score == "-":
            sleep_score = existing_or_missing(sleep, key, 2)
            missing["sleepScore"].append(key)
        sleep[key] = [key, sleep_duration, sleep_score]

        steps = tables["steps.md"][1]
        steps_value = fmt_int(row.get("steps"))
        if steps_value == "-":
            steps_value = existing_or_missing(steps, key, 1)
        steps[key] = [key, steps_value, "-"]

        weight = tables["weight.md"][1]
        raw_weight = fmt_float(row.get("weight"), 1)
        raw_bodyfat = fmt_float(row.get("bodyFat"), 1)
        if raw_weight != "-":
            bodyfat_value = raw_bodyfat
            if bodyfat_value == "-":
                bodyfat_value = existing_or_missing(weight, key, 3)
                missing["bodyFat"].append(key)
            weight[key] = [key, raw_weight, "-", bodyfat_value, "-"]
        else:
            missing["weight"].append(key)
            bodyfat_value = existing_or_missing(weight, key, 3)
            if bodyfat_value == "-":
                missing["bodyFat"].append(key)
            weight[key] = [key, "-", "-", bodyfat_value, "-"]

    recalc_hrv(tables["hrv.md"][1])
    recalc_weight(tables["weight.md"][1])
    recalc_steps(tables["steps.md"][1])

    for field, dates in sorted(missing.items()):
        if dates:
            sample = ", ".join(dates[:3])
            extra = "" if len(dates) <= 3 else f", ... ({len(dates)} days total)"
            warnings.append(f"Intervals.icu wellness field {field} missing for {sample}{extra}")

    for name, (header, rows) in tables.items():
        write_table(HEALTH_DIR / name, header, rows, args.dry_run)

    if warnings:
        print("WARNINGS:")
        for warning in warnings:
            print(f"- {warning}")
    return 0 if not warnings else 2


if __name__ == "__main__":
    raise SystemExit(main())
