#!/usr/bin/env python3
"""Small shared Intervals.icu client for the training repo scripts."""

from __future__ import annotations

import base64
import csv
import json
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from markdown_tables import write_text_atomic
from profile_paths import DATA_DIR, load_env_values


API_BASE = "https://intervals.icu/api/v1"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


class IntervalsError(RuntimeError):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def load_env() -> dict[str, str]:
    return load_env_values(environment_prefixes=("intervals_icu_", "INTERVALS_ICU_"))


def get_api_key(env: dict[str, str]) -> str:
    api_key = env.get("intervals_icu_api_key") or env.get("INTERVALS_ICU_API_KEY")
    if api_key:
        return api_key
    raise IntervalsError(
        "Missing Intervals.icu API key. Add intervals_icu_api_key=<key> to "
        "profiles/<TRAINING_PROFILE>/.env."
    )


def get_athlete_id(env: dict[str, str]) -> str:
    athlete_id = env.get("intervals_icu_athlete_id") or env.get("INTERVALS_ICU_ATHLETE_ID")
    if athlete_id:
        return athlete_id
    raise IntervalsError(
        "Missing Intervals.icu athlete id. Add intervals_icu_athlete_id=<id> to "
        "profiles/<TRAINING_PROFILE>/.env."
    )


def read_csv_rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(text.splitlines()))


@dataclass
class IntervalsClient:
    api_key: str
    athlete_id: str

    @classmethod
    def from_env(cls) -> "IntervalsClient":
        env = load_env()
        return cls(get_api_key(env), get_athlete_id(env))

    def request(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        accept: str = "application/json",
    ) -> bytes:
        query = ""
        if params:
            query = "?" + urllib.parse.urlencode(params, doseq=True)
        token = base64.b64encode(f"API_KEY:{self.api_key}".encode("utf-8")).decode("ascii")
        req = urllib.request.Request(
            f"{API_BASE}{path}{query}",
            headers={
                "Authorization": f"Basic {token}",
                "Accept": accept,
                "User-Agent": "personal-training-plan",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            body = exc.read(500).decode("utf-8", errors="replace")
            raise IntervalsError(f"HTTP {exc.code} for {path}: {body}", exc.code) from exc
        except urllib.error.URLError as exc:
            raise IntervalsError(f"Network error for {path}: {exc.reason}") from exc

    def request_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        try:
            return json.loads(self.request(path, params).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise IntervalsError(f"Invalid JSON response for {path}: {exc}") from exc

    def wellness_csv(self, oldest: date, newest: date) -> str:
        return self.request(
            f"/athlete/{self.athlete_id}/wellness.csv",
            {"oldest": oldest.isoformat(), "newest": newest.isoformat()},
            accept="text/csv",
        ).decode("utf-8-sig", errors="replace")

    def activities(
        self,
        oldest: date,
        newest: date,
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"oldest": oldest.isoformat(), "newest": newest.isoformat()}
        if fields:
            params["fields"] = fields
        data = self.request_json(f"/athlete/{self.athlete_id}/activities", params)
        return data if isinstance(data, list) else []

    def sport_settings(self) -> Any:
        return self.request_json(f"/athlete/{self.athlete_id}/sport-settings")

    def download_activity_original(self, activity_id: str) -> bytes:
        return self.request(f"/activity/{activity_id}/file", accept="application/octet-stream")

    def download_activity_fit(self, activity_id: str) -> bytes:
        return self.request(
            f"/activity/{activity_id}/fit-file",
            {"power": "true", "hr": "true"},
            accept="application/octet-stream",
        )


def parse_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def iso_week_folder(day: date) -> Path:
    year, week, _ = day.isocalendar()
    return DATA_DIR / "activities" / f"{year}-W{week:02d}"


def sanitize_activity_name(name: str) -> str:
    cleaned = "".join(char for char in name if not is_emoji_char(char))
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", cleaned).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.rstrip(". ")
    return cleaned or "Activity"


def is_emoji_char(char: str) -> bool:
    code = ord(char)
    if char in {"\ufe0f", "\u200d"}:
        return True
    if 0x1F000 <= code <= 0x1FAFF:
        return True
    if 0x2600 <= code <= 0x27BF and unicodedata.category(char) in {"So", "Sk"}:
        return True
    return False


def activity_target_path(activity: dict[str, Any]) -> Path:
    start = activity.get("start_date_local")
    if not start:
        raise ValueError(f"Activity {activity.get('id', '<unknown>')} has no start_date_local")
    day = parse_date(str(start))
    name = sanitize_activity_name(str(activity.get("name") or activity.get("type") or "Activity"))
    return iso_week_folder(day) / f"{day.isoformat()} {name}.fit"


def looks_like_fit(data: bytes) -> bool:
    return len(data) >= 14 and data[8:12] == b".FIT"


def write_json(path: Path, data: Any) -> None:
    write_text_atomic(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
