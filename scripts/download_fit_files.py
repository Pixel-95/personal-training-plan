#!/usr/bin/env python3
"""Download activity FIT files into the active profile's weekly activity folders."""

from __future__ import annotations

import argparse
import hashlib
from datetime import date
from pathlib import Path

from date_utils import date_range_from_days, expand_range_with_overlap
from intervals_icu_client import (
    IntervalsClient,
    IntervalsError,
    activity_target_path,
    looks_like_fit,
    parse_date,
)
from markdown_tables import write_bytes_atomic
from profile_paths import DATA_DIR, ROOT


ACTIVITY_FIELDS = ["id", "start_date_local", "type", "name"]


def is_multisport_component_duplicate(existing_types: set[str], activity_type: str) -> bool:
    return activity_type == "Transition" or "Transition" in existing_types


def newest_downloaded_fit_date() -> date | None:
    dates: list[date] = []
    for path in (DATA_DIR / "activities").rglob("*.fit"):
        try:
            dates.append(parse_date(path.name))
        except ValueError:
            continue
    return max(dates) if dates else None


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


def fit_content_is_unchanged(path: Path, data: bytes) -> bool:
    return path.exists() and path.read_bytes() == data


def existing_identical_fit(data: bytes, target: Path) -> Path | None:
    """Return an existing FIT with identical bytes, excluding its intended target."""
    digest = hashlib.sha256(data).digest()
    for path in (DATA_DIR / "activities").rglob("*.fit"):
        if path.resolve() == target.resolve():
            continue
        if path.stat().st_size != len(data):
            continue
        if hashlib.sha256(path.read_bytes()).digest() == digest:
            return path
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Download missing FIT files from Intervals.icu.")
    parser.add_argument("--days", type=int, default=30, help="Number of days to inspect.")
    parser.add_argument("--newest", default=date.today().isoformat(), help="Newest local date YYYY-MM-DD.")
    parser.add_argument("--dry-run", action="store_true", help="Report planned downloads without writing.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing FIT files.")
    args = parser.parse_args()

    requested_oldest, newest = date_range_from_days(args.days, args.newest)
    refresh_day = newest_downloaded_fit_date()
    oldest, newest = expand_range_with_overlap(requested_oldest, newest, refresh_day)

    if refresh_day and refresh_day < requested_oldest:
        print(
            f"Including latest local FIT day {refresh_day.isoformat()} for refresh "
            f"before inspecting {requested_oldest.isoformat()} to {newest.isoformat()}."
        )

    client = IntervalsClient.from_env()
    activities = client.activities(oldest, newest, ACTIVITY_FIELDS)

    warnings: list[str] = []
    downloaded = 0
    planned = 0
    skipped = 0
    seen_targets: dict[str, set[str]] = {}

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

        target_key = str(target.resolve())
        if target_key in seen_targets:
            skipped += 1
            activity_type = str(activity.get("type") or "")
            if is_multisport_component_duplicate(seen_targets[target_key], activity_type):
                print(
                    f"SKIP multisport component {activity_id} -> "
                    f"{target.relative_to(ROOT)}"
                )
            else:
                warnings.append(
                    f"{activity_id}: duplicate target skipped after earlier activity mapped to "
                    f"{target.relative_to(ROOT)}"
                )
            seen_targets[target_key].add(activity_type)
            continue
        seen_targets[target_key] = {str(activity.get("type") or "")}

        activity_day = parse_date(str(activity.get("start_date_local", "")))
        should_refresh = refresh_day is not None and activity_day == refresh_day

        if target.exists() and not args.overwrite and not should_refresh:
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
        if fit_content_is_unchanged(target, data):
            skipped += 1
            print(f"SKIP unchanged overlap {target.relative_to(ROOT)}")
            continue
        duplicate = existing_identical_fit(data, target)
        if duplicate:
            skipped += 1
            print(
                f"SKIP identical FIT {activity_id} -> {target.relative_to(ROOT)} "
                f"(already stored as {duplicate.relative_to(ROOT)})"
            )
            continue
        write_bytes_atomic(target, data)
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
