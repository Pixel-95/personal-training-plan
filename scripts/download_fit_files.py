#!/usr/bin/env python3
"""Download activity FIT files from Intervals.icu into data/activities/YYYY-Www."""

from __future__ import annotations

import argparse
from datetime import date

from intervals_icu_client import (
    IntervalsClient,
    IntervalsError,
    ROOT,
    activity_target_path,
    date_range_from_days,
    looks_like_fit,
)


ACTIVITY_FIELDS = ["id", "start_date_local", "type", "name"]


def download_fit(client: IntervalsClient, activity_id: str) -> tuple[bytes, str, list[str]]:
    warnings: list[str] = []
    try:
        data = client.download_activity_original(activity_id)
        if looks_like_fit(data):
            return data, "original", warnings
        warnings.append(f"{activity_id}: original file is not FIT, using generated FIT fallback")
    except IntervalsError as exc:
        warnings.append(f"{activity_id}: original file unavailable ({exc})")

    data = client.download_activity_fit(activity_id)
    if not looks_like_fit(data):
        warnings.append(f"{activity_id}: generated FIT does not look like a FIT file")
    return data, "generated", warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Download missing FIT files from Intervals.icu.")
    parser.add_argument("--days", type=int, default=30, help="Number of days to inspect.")
    parser.add_argument("--newest", default=date.today().isoformat(), help="Newest local date YYYY-MM-DD.")
    parser.add_argument("--dry-run", action="store_true", help="Report planned downloads without writing.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing FIT files.")
    args = parser.parse_args()

    oldest, newest = date_range_from_days(args.days, args.newest)
    client = IntervalsClient.from_env()
    activities = client.activities(oldest, newest, ACTIVITY_FIELDS)

    warnings: list[str] = []
    downloaded = 0
    planned = 0
    skipped = 0

    for activity in sorted(activities, key=lambda item: str(item.get("start_date_local", ""))):
        activity_id = str(activity.get("id") or "")
        if not activity_id:
            warnings.append(f"Activity without id skipped: {activity}")
            continue
        try:
            target = activity_target_path(activity)
        except ValueError as exc:
            warnings.append(str(exc))
            continue

        if target.exists() and not args.overwrite:
            skipped += 1
            print(f"SKIP existing {target.relative_to(ROOT)}")
            continue

        if args.dry_run:
            action = "OVERWRITE" if target.exists() else "DOWNLOAD"
            print(f"{action} {activity_id} -> {target.relative_to(ROOT)}")
            planned += 1
            continue

        data, source, activity_warnings = download_fit(client, activity_id)
        warnings.extend(activity_warnings)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        downloaded += 1
        print(f"WROTE {target.relative_to(ROOT)} ({source})")

    print(f"Activities inspected: {len(activities)}")
    if args.dry_run:
        print(f"Planned downloads: {planned}")
    print(f"Downloaded: {downloaded}")
    print(f"Skipped existing: {skipped}")
    if warnings:
        print("WARNINGS:")
        for warning in warnings:
            print(f"- {warning}")
    return 0 if not warnings else 2


if __name__ == "__main__":
    raise SystemExit(main())
