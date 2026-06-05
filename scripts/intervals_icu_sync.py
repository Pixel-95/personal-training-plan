#!/usr/bin/env python3
"""Sync selected Intervals.icu data into this training repo.

Requires `.env` with:
  intervals_icu_api_key=<personal Intervals.icu API key>

Optional:
  intervals_icu_athlete_id=0
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
OUT_DIR = ROOT / "data" / "health"
API_BASE = "https://intervals.icu/api/v1"


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    values.update({k: v for k, v in os.environ.items() if k.startswith("intervals_icu_")})
    return values


def get_api_key(env: dict[str, str]) -> str:
    api_key = env.get("intervals_icu_api_key") or env.get("INTERVALS_ICU_API_KEY")
    if api_key:
        return api_key

    # Backward-compatible fallback only if the user explicitly configured API_KEY auth.
    if env.get("intervals_icu_login") == "API_KEY" and env.get("intervals_icu_password"):
        return env["intervals_icu_password"]

    raise SystemExit(
        "Missing Intervals.icu API key. Add `intervals_icu_api_key=<key>` to `.env`. "
        "Generate it in Intervals.icu: Settings -> Developer Settings -> API key."
    )


def request(api_key: str, path: str, params: dict[str, Any] | None = None, accept: str = "application/json") -> bytes:
    query = ""
    if params:
        query = "?" + urllib.parse.urlencode(params, doseq=True)
    token = base64.b64encode(f"API_KEY:{api_key}".encode("utf-8")).decode("ascii")
    req = urllib.request.Request(
        f"{API_BASE}{path}{query}",
        headers={
            "Authorization": f"Basic {token}",
            "Accept": accept,
            "User-Agent": "personal-training-plan/intervals-icu-sync",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=40) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read(300).decode("utf-8", errors="replace")
        raise SystemExit(f"Intervals.icu request failed: HTTP {exc.code} for {path}: {body}") from exc


def request_json(api_key: str, path: str, params: dict[str, Any] | None = None) -> Any:
    return json.loads(request(api_key, path, params).decode("utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_csv_rows(text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(text.splitlines())
    return list(reader)


def latest_non_empty(row: dict[str, str], keys: list[str]) -> list[str]:
    parts = []
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            parts.append(f"{key}: {value}")
    return parts


def build_summary(
    newest: str,
    wellness_rows: list[dict[str, str]],
    activities: list[dict[str, Any]],
    sport_settings: Any,
) -> str:
    lines = [
        "# Intervals.icu Latest",
        "",
        f"Updated: {date.today().isoformat()}",
        f"Newest synced date: {newest}",
        "",
    ]

    if wellness_rows:
        row = wellness_rows[-1]
        lines.extend(["## Latest Wellness", ""])
        fields = [
            "id",
            "ctl",
            "atl",
            "rampRate",
            "weight",
            "restingHR",
            "hrv",
            "hrvSDNN",
            "sleepSecs",
            "sleepScore",
            "avgSleepingHR",
            "readiness",
            "steps",
            "respiration",
            "vo2max",
            "kcalConsumed",
        ]
        for item in latest_non_empty(row, fields):
            lines.append(f"- {item}")
        lines.append("")

    if activities:
        lines.extend(["## Latest Activities", ""])
        for activity in sorted(activities, key=lambda a: a.get("start_date_local", ""))[-7:]:
            date_local = str(activity.get("start_date_local", ""))[:10]
            name = activity.get("name") or activity.get("type") or "Activity"
            load = activity.get("icu_training_load")
            ctl = activity.get("icu_ctl")
            atl = activity.get("icu_atl")
            bits = [str(name)]
            if load is not None:
                bits.append(f"load {load}")
            if ctl is not None:
                bits.append(f"CTL {ctl}")
            if atl is not None:
                bits.append(f"ATL {atl}")
            lines.append(f"- {date_local}: " + ", ".join(bits))
        lines.append("")

    if sport_settings:
        lines.extend(["## Sport Settings Snapshot", ""])
        settings = sport_settings if isinstance(sport_settings, list) else [sport_settings]
        for item in settings:
            types = ",".join(item.get("types", [])) if isinstance(item, dict) else ""
            if not types:
                continue
            values = []
            for key in ["ftp", "indoor_ftp", "lthr", "threshold_pace"]:
                value = item.get(key)
                if value not in (None, ""):
                    values.append(f"{key}: {value}")
            if values:
                lines.append(f"- {types}: " + ", ".join(values))
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync selected Intervals.icu data into data/health.")
    parser.add_argument("--days", type=int, default=30, help="Number of days to sync.")
    parser.add_argument("--newest", default=date.today().isoformat(), help="Newest local date YYYY-MM-DD.")
    args = parser.parse_args()

    env = load_env()
    api_key = get_api_key(env)
    athlete_id = env.get("intervals_icu_athlete_id", "0")
    newest = date.fromisoformat(args.newest)
    oldest = newest - timedelta(days=max(args.days, 1) - 1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    wellness_csv = request(
        api_key,
        f"/athlete/{athlete_id}/wellness.csv",
        {"oldest": oldest.isoformat(), "newest": newest.isoformat()},
        accept="text/csv",
    ).decode("utf-8-sig", errors="replace")
    (OUT_DIR / "intervals-wellness.csv").write_text(wellness_csv, encoding="utf-8")
    wellness_rows = read_csv_rows(wellness_csv)

    activity_fields = [
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
    activities = request_json(
        api_key,
        f"/athlete/{athlete_id}/activities",
        {
            "oldest": oldest.isoformat(),
            "newest": newest.isoformat(),
            "fields": activity_fields,
        },
    )
    write_json(OUT_DIR / "intervals-activities.json", activities)

    sport_settings = request_json(api_key, f"/athlete/{athlete_id}/sport-settings")
    write_json(OUT_DIR / "intervals-sport-settings.json", sport_settings)

    latest = build_summary(newest.isoformat(), wellness_rows, activities, sport_settings)
    (OUT_DIR / "latest.md").write_text(latest, encoding="utf-8")

    print(f"Synced Intervals.icu data to {OUT_DIR.relative_to(ROOT)}")
    print(f"Range: {oldest.isoformat()} to {newest.isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
