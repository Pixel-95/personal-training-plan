#!/usr/bin/env python3
"""Sync selected Intervals.icu cache data into the active profile.

This script does not download FIT files and does not write latest.md. Use
download_fit_files.py for FIT files and update_health.py for canonical health
Markdown histories.
"""

from __future__ import annotations

import argparse
import json
from datetime import date

from date_utils import date_range_from_days, expand_range_with_overlap
from intervals_icu_client import IntervalsClient, read_csv_rows, write_json
from markdown_tables import write_text_atomic
from profile_paths import DATA_DIR, ROOT


OUT_DIR = DATA_DIR / "health"


ACTIVITY_FIELDS = [
    "id",
    "start_date_local",
    "type",
    "name",
    "moving_time",
    "elapsed_time",
    "distance",
    "icu_training_load",
    "icu_ctl",
    "icu_atl",
    "icu_ftp",
    "lthr",
    "threshold_pace",
    "average_heartrate",
    "max_heartrate",
    "perceived_exertion",
]


def newest_cached_wellness_date() -> date | None:
    path = OUT_DIR / "intervals-wellness.csv"
    if not path.exists():
        return None
    rows = read_csv_rows(path.read_text(encoding="utf-8-sig"))
    dates = [date.fromisoformat(value) for row in rows if (value := row.get("date", ""))]
    return max(dates) if dates else None


def newest_cached_activity_date() -> date | None:
    path = OUT_DIR / "intervals-activities.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, list):
        return None
    dates = [
        date.fromisoformat(str(start)[:10])
        for item in payload
        if isinstance(item, dict) and (start := item.get("start_date_local"))
    ]
    return max(dates) if dates else None


def newest_cached_sync_date() -> date | None:
    candidates = [newest_cached_wellness_date(), newest_cached_activity_date()]
    dates = [candidate for candidate in candidates if candidate is not None]
    return max(dates) if dates else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Intervals.icu raw/cache data.")
    parser.add_argument("--days", type=int, default=30, help="Number of days to sync.")
    parser.add_argument("--newest", default=date.today().isoformat(), help="Newest local date YYYY-MM-DD.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and report without writing files.")
    args = parser.parse_args()

    requested_oldest, newest = date_range_from_days(args.days, args.newest)
    refresh_day = newest_cached_sync_date()
    oldest, newest = expand_range_with_overlap(requested_oldest, newest, refresh_day)

    if refresh_day and refresh_day < requested_oldest:
        print(
            f"Including latest cached Intervals day {refresh_day.isoformat()} for refresh "
            f"before syncing {requested_oldest.isoformat()} to {newest.isoformat()}."
        )

    client = IntervalsClient.from_env()

    wellness_csv = client.wellness_csv(oldest, newest)
    wellness_rows = read_csv_rows(wellness_csv)
    activities = client.activities(oldest, newest, ACTIVITY_FIELDS)
    sport_settings = client.sport_settings()

    if args.dry_run:
        print(f"Would sync Intervals.icu cache data for {oldest} to {newest}")
        print(f"Wellness rows: {len(wellness_rows)}")
        print(f"Activities: {len(activities)}")
        print("Would write: intervals-wellness.csv, intervals-activities.json, intervals-sport-settings.json")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_text_atomic(OUT_DIR / "intervals-wellness.csv", wellness_csv)
    write_json(OUT_DIR / "intervals-activities.json", activities)
    write_json(OUT_DIR / "intervals-sport-settings.json", sport_settings)

    print(f"Synced Intervals.icu cache data to {OUT_DIR.relative_to(ROOT)}")
    print(f"Range: {oldest.isoformat()} to {newest.isoformat()}")
    print("Wrote: intervals-wellness.csv, intervals-activities.json, intervals-sport-settings.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
