#!/usr/bin/env python3
"""Recalculate the active profile's load history from Activity Markdown TSS values."""

from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path

from date_utils import inclusive_dates
from markdown_tables import read_table, render_table, rows_by_key, write_text_atomic
from profile_paths import DATA_DIR, ROOT


LOADS_PATH = DATA_DIR / "health" / "loads.md"
ACTIVITIES_DIR = DATA_DIR / "activities"
HEADER = ["Datum", "Tages-TSS", "ATL", "CTL", "TSB", "ACR"]
TSS_RE = re.compile(r"^\s*[-*]?\s*TSS:\s*([0-9]+(?:[.,][0-9]+)?|-)\s*$", re.MULTILINE)


def parse_loads(path: Path = LOADS_PATH) -> dict[str, list[str]]:
    header, rows = read_table(path)
    if header and header != HEADER:
        raise ValueError(f"Unexpected loads header in {path}: {header}")
    return rows_by_key(rows)


def activity_tss_by_day(activities_dir: Path = ACTIVITIES_DIR) -> dict[date, float]:
    totals: dict[date, float] = {}
    if not activities_dir.exists():
        return totals
    for path in activities_dir.rglob("*.md"):
        if path.name.startswith("review_"):
            continue
        match_date = re.match(r"(\d{4}-\d{2}-\d{2}) ", path.name)
        if not match_date:
            continue
        text = path.read_text(encoding="utf-8-sig")
        match = TSS_RE.search(text)
        if not match or match.group(1) == "-":
            continue
        value = float(match.group(1).replace(",", "."))
        day = date.fromisoformat(match_date.group(1))
        totals[day] = totals.get(day, 0.0) + value
    return totals


def fmt_number(value: float) -> str:
    if abs(value - round(value)) < 0.05:
        return str(round(value))
    return f"{value:.1f}".rstrip("0").rstrip(".")


def initial_load_seed(start: date, end: date, tss_totals: dict[date, float]) -> float:
    """Use the mean daily TSS of the most recent half of the available period."""
    days = list(inclusive_dates(start, end))
    recent_days = days[len(days) // 2 :]
    return sum(tss_totals.get(day, 0.0) for day in recent_days) / len(recent_days)


def calculate(
    loads_path: Path = LOADS_PATH,
    activities_dir: Path = ACTIVITIES_DIR,
    newest: date | None = None,
) -> dict[str, list[str]]:
    existing = parse_loads(loads_path)
    tss_totals = activity_tss_by_day(activities_dir)
    if not existing and not tss_totals:
        return {}

    start_key = min(existing) if existing else min(day.isoformat() for day in tss_totals)
    start = date.fromisoformat(start_key)
    newest_candidates = [date.fromisoformat(day) for day in existing] + list(tss_totals)
    end = max(newest_candidates + ([newest] if newest else []))

    measured_end = max(tss_totals) if tss_totals else max(date.fromisoformat(day) for day in existing)
    seed = initial_load_seed(start, measured_end, tss_totals)
    atl = seed
    ctl = seed

    rows: dict[str, list[str]] = {}
    for day in inclusive_dates(start, end):
        tss = tss_totals.get(day, 0.0)
        if day != start:
            atl = atl + (tss - atl) / 7
            ctl = ctl + (tss - ctl) / 42
        tsb = ctl - atl
        acr = "-" if round(ctl) == 0 and abs(ctl) < 0.0001 else f"{atl / ctl:.3f}"
        rows[day.isoformat()] = [
            day.isoformat(),
            fmt_number(tss),
            str(round(atl)),
            str(round(ctl)),
            str(round(tsb)),
            acr,
        ]
    return rows


def write_loads(rows: dict[str, list[str]], dry_run: bool, path: Path = LOADS_PATH) -> None:
    ordered = sorted(rows.values(), key=lambda cells: cells[0], reverse=True)
    if dry_run:
        print(f"Would write {path.relative_to(ROOT)} ({len(ordered)} rows)")
        for row in ordered[:10]:
            print(" | ".join(row))
        return
    write_text_atomic(path, render_table(HEADER, ordered))


def main() -> int:
    parser = argparse.ArgumentParser(description="Recalculate load history from Activity Markdown files.")
    parser.add_argument("--newest", help="Newest date YYYY-MM-DD to include as trailing zero-load days if needed.")
    parser.add_argument("--dry-run", action="store_true", help="Report calculated loads without writing.")
    args = parser.parse_args()

    target_newest = date.fromisoformat(args.newest) if args.newest else None
    rows = calculate(newest=target_newest)
    write_loads(rows, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
