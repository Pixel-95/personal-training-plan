#!/usr/bin/env python3
"""Recalculate data/health/loads.md from Activity Markdown TSS values."""

from __future__ import annotations

import argparse
import re
from datetime import date, timedelta
from pathlib import Path

from intervals_icu_client import ROOT


LOADS_PATH = ROOT / "data" / "health" / "loads.md"
ACTIVITIES_DIR = ROOT / "data" / "activities"
HEADER = ["Datum", "Tages-TSS", "ATL", "CTL", "TSB", "ACR"]
TSS_RE = re.compile(r"^\s*[-*]?\s*TSS:\s*([0-9]+(?:[.,][0-9]+)?|-)\s*$", re.MULTILINE)


def parse_loads() -> dict[str, list[str]]:
    if not LOADS_PATH.exists():
        return {}
    rows: dict[str, list[str]] = {}
    for line in LOADS_PATH.read_text(encoding="utf-8-sig", errors="replace").splitlines()[2:]:
        if not line.strip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 6 and cells[0]:
            rows[cells[0]] = cells[:6]
    return rows


def activity_tss_by_day() -> dict[date, float]:
    totals: dict[date, float] = {}
    for path in ACTIVITIES_DIR.rglob("*.md"):
        if path.name.startswith("review_"):
            continue
        match_date = re.match(r"(\d{4}-\d{2}-\d{2}) ", path.name)
        if not match_date:
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
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


def date_iter(oldest: date, newest: date) -> list[date]:
    days = []
    current = oldest
    while current <= newest:
        days.append(current)
        current += timedelta(days=1)
    return days


def calculate() -> dict[str, list[str]]:
    existing = parse_loads()
    tss_totals = activity_tss_by_day()
    if not existing and not tss_totals:
        return {}

    start_key = min(existing) if existing else min(day.isoformat() for day in tss_totals)
    start = date.fromisoformat(start_key)
    newest_candidates = [date.fromisoformat(day) for day in existing] + list(tss_totals)
    newest = max(newest_candidates)

    start_row = existing.get(start_key)
    if start_row and start_row[2] != "-" and start_row[3] != "-":
        atl = float(start_row[2])
        ctl = float(start_row[3])
    else:
        atl = 0.0
        ctl = 0.0

    rows: dict[str, list[str]] = {}
    for day in date_iter(start, newest):
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


def write_loads(rows: dict[str, list[str]], dry_run: bool) -> None:
    ordered = sorted(rows.values(), key=lambda cells: cells[0], reverse=True)
    content = [
        "| " + " | ".join(HEADER) + " |",
        "|" + "|".join("-" for _ in HEADER) + "|",
    ]
    content.extend("| " + " | ".join(row) + " |" for row in ordered)
    if dry_run:
        print(f"Would write {LOADS_PATH.relative_to(ROOT)} ({len(ordered)} rows)")
        for row in ordered[:10]:
            print(" | ".join(row))
        return
    LOADS_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOADS_PATH.write_text("\n".join(content) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Recalculate load history from Activity Markdown files.")
    parser.add_argument("--dry-run", action="store_true", help="Report calculated loads without writing.")
    args = parser.parse_args()

    rows = calculate()
    write_loads(rows, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
