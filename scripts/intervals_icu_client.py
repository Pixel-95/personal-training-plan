#!/usr/bin/env python3
"""Small shared Intervals.icu client for the training repo scripts."""

from __future__ import annotations

import base64
import csv
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
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
    values: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    values.update({k: v for k, v in os.environ.items() if k.startswith("intervals_icu_")})
    values.update({k: v for k, v in os.environ.items() if k.startswith("INTERVALS_ICU_")})
    return values


def get_api_key(env: dict[str, str]) -> str:
    api_key = env.get("intervals_icu_api_key") or env.get("INTERVALS_ICU_API_KEY")
    if api_key:
        return api_key
    if env.get("intervals_icu_login") == "API_KEY" and env.get("intervals_icu_password"):
        return env["intervals_icu_password"]
    raise IntervalsError(
        "Missing Intervals.icu API key. Add intervals_icu_api_key=<key> to .env."
    )


def get_athlete_id(env: dict[str, str]) -> str:
    return env.get("intervals_icu_athlete_id") or env.get("INTERVALS_ICU_ATHLETE_ID") or "0"


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

    def request_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return json.loads(self.request(path, params).decode("utf-8"))

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


def date_range_from_days(days: int, newest: str | None = None) -> tuple[date, date]:
    newest_date = date.today() if newest is None else date.fromisoformat(newest)
    oldest_date = newest_date.fromordinal(newest_date.toordinal() - max(days, 1) + 1)
    return oldest_date, newest_date


def iso_week_folder(day: date) -> Path:
    year, week, _ = day.isocalendar()
    return ROOT / "data" / "activities" / f"{year}-W{week:02d}"


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
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
