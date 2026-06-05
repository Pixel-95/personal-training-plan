#!/usr/bin/env python3
"""Probe which requested Intervals.icu fields are available and populated."""

from __future__ import annotations

import base64
import csv
import json
import os
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
API_BASE = "https://intervals.icu/api/v1"


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip().strip('"').strip("'")
    env.update({k: v for k, v in os.environ.items() if k.startswith("intervals_icu_")})
    return env


def api_key(env: dict[str, str]) -> str:
    key = env.get("intervals_icu_api_key")
    if not key:
        raise SystemExit("Missing intervals_icu_api_key in .env")
    return key


def get(api_key_value: str, path: str, params: dict[str, Any] | None = None, accept: str = "application/json") -> bytes:
    token = base64.b64encode(f"API_KEY:{api_key_value}".encode()).decode("ascii")
    query = "?" + urllib.parse.urlencode(params, doseq=True) if params else ""
    req = urllib.request.Request(
        API_BASE + path + query,
        headers={
            "Authorization": "Basic " + token,
            "Accept": accept,
            "User-Agent": "personal-training-plan/intervals-icu-probe",
        },
    )
    with urllib.request.urlopen(req, timeout=40) as response:
        return response.read()


def load_openapi_spec() -> dict[str, Any]:
    req = urllib.request.Request(API_BASE + "/docs", headers={"User-Agent": "personal-training-plan/intervals-icu-probe"})
    with urllib.request.urlopen(req, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def schema_props(spec: dict[str, Any], schema_name: str) -> set[str]:
    return set(spec["components"]["schemas"][schema_name]["properties"])


def first_value(rows: list[dict[str, Any]], fields: list[str]) -> tuple[str, str] | None:
    for row in sorted(rows, key=lambda x: str(x.get("date") or x.get("start_date_local") or ""), reverse=True):
        for field in fields:
            value = row.get(field)
            if value not in (None, "", [], {}):
                return field, str(value)
    return None


def sport_setting_value(settings: Any, sport_name: str, fields: list[str]) -> tuple[str, str] | None:
    items = settings if isinstance(settings, list) else [settings]
    for item in items:
        types = item.get("types") or []
        if sport_name not in types:
            continue
        for field in fields:
            value = item.get(field)
            if value not in (None, "", [], {}):
                return field, str(value)
    return None


def main() -> int:
    env = load_env()
    key = api_key(env)
    athlete_id = env.get("intervals_icu_athlete_id", "0")
    newest = date.today()
    oldest = newest - timedelta(days=89)

    wellness_csv = get(
        key,
        f"/athlete/{athlete_id}/wellness.csv",
        {"oldest": oldest.isoformat(), "newest": newest.isoformat()},
        accept="text/csv",
    ).decode("utf-8-sig", errors="replace")
    wellness_rows = list(csv.DictReader(wellness_csv.splitlines()))

    activities = json.loads(
        get(
            key,
            f"/athlete/{athlete_id}/activities",
            {"oldest": oldest.isoformat(), "newest": newest.isoformat(), "limit": 50},
        ).decode("utf-8")
    )

    sport_settings = json.loads(get(key, f"/athlete/{athlete_id}/sport-settings").decode("utf-8"))

    spec = load_openapi_spec()
    wellness_schema = schema_props(spec, "Wellness")
    activity_schema = schema_props(spec, "Activity")
    settings_schema = schema_props(spec, "SportSettings")

    checks = [
        ("Nächtliche HRV", "Wellness", ["hrv", "hrvSDNN"], "Garmin/Intervals wellness."),
        ("Ruhepuls", "Wellness", ["restingHR"], "Garmin/Intervals wellness."),
        ("Sleep Score", "Wellness", ["sleepScore"], "Garmin/Intervals wellness."),
        ("Schlafdauer", "Wellness", ["sleepSecs"], "Sekunden; im Report in h:mm umrechnen."),
        ("Morgendliche Body Battery", "Wellness", ["bodyBattery", "body_battery"], "Kein Standardfeld im Intervals-Wellness-Schema gefunden."),
        ("ATL/CTL", "Wellness", ["atl", "ctl"], "Auch als Activity-Felder möglich, wenn berechnet."),
        ("Subjektive RPE", "Activity", ["perceived_exertion", "icu_rpe", "session_rpe"], "Activity-Level; lokale FITs enthalten teils workout_rpe."),
        ("Subjektives Gefühl", "Activity", ["feel"], "Activity-Level; lokale FITs enthalten teils workout_feel."),
        ("Morgen-Gewicht", "Wellness", ["weight"], "Garmin/Intervals wellness."),
        ("Schritte", "Wellness", ["steps"], "Garmin/Intervals wellness."),
        ("Täglicher Kalorienverbrauch", "Wellness", ["kcalBurned", "caloriesBurned", "activeKcal"], "Kein Standardfeld gefunden; kcalConsumed ist Intake, Activity calories ist nicht Tagesverbrauch."),
        ("Kalorienzufuhr", "Wellness", ["kcalConsumed"], "Vorhanden, aber nicht Verbrauch."),
        ("Aktivitätskalorien", "Activity", ["calories"], "Nur pro Aktivität."),
        ("Nächtliche Atemfrequenz", "Wellness", ["respiration"], "Garmin/Intervals wellness."),
        ("VO2max", "Wellness", ["vo2max"], "Garmin/Intervals wellness."),
        ("Bike FTP", "SportSettings:Ride", ["ftp", "indoor_ftp"], "Threshold aus Intervals Sport Settings."),
        ("Bike LTHR", "SportSettings:Ride", ["lthr"], "Threshold aus Intervals Sport Settings."),
        ("Run LTHR", "SportSettings:Run", ["lthr"], "Threshold aus Intervals Sport Settings."),
        ("Run Threshold Pace", "SportSettings:Run", ["threshold_pace"], "m/s in Intervals; in min/km umrechnen."),
        ("Swim Threshold Pace", "SportSettings:Swim", ["threshold_pace"], "m/s in Intervals; in min/100m umrechnen."),
    ]

    print(f"Probe range: {oldest.isoformat()} to {newest.isoformat()}")
    print(f"Wellness rows: {len(wellness_rows)}")
    print(f"Activities: {len(activities)}")
    print()
    print("| Datenpunkt | API-Feld vorhanden | Aktuell Daten vorhanden | Quelle / Hinweis |")
    print("|-|-|-|-|")
    for label, source, fields, note in checks:
        if source == "Wellness":
            present = any(field in wellness_schema or (wellness_rows and field in wellness_rows[0]) for field in fields)
            value = first_value(wellness_rows, fields)
        elif source == "Activity":
            present = any(field in activity_schema for field in fields)
            value = first_value(activities, fields)
        elif source == "SportSettings":
            present = any(field in settings_schema for field in fields)
            flat = sport_settings if isinstance(sport_settings, list) else [sport_settings]
            value = first_value(flat, fields)
        elif source.startswith("SportSettings:"):
            sport_name = source.split(":", 1)[1]
            present = any(field in settings_schema for field in fields)
            value = sport_setting_value(sport_settings, sport_name, fields)
        else:
            present = False
            value = None
        present_text = "ja" if present else "nein"
        value_text = f"ja ({value[0]}={value[1]})" if value else "nein"
        print(f"| {label} | {present_text} | {value_text} | {note} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
