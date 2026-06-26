#!/usr/bin/env python3
"""Validate profile structure, canonical tables, plans, and text encoding."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from markdown_tables import read_table
from profile_paths import DATA_DIR, PROFILE, PROFILE_DIR, PROFILE_PLANS_DIR, ROOT
from render_plan import validate_plan
from update_health import TABLES as HEALTH_TABLES
from update_loads import HEADER as LOADS_HEADER


TEXT_SUFFIXES = {".css", ".html", ".json", ".md", ".py", ".txt"}
OPTIONAL_HEALTH_TABLES = {
    "calories.md": ["Datum", "Ruhe-Kalorien", "Aktiv-Kalorien"],
}
REQUIRED_DATA_PATHS = [
    "athlete-profile.md",
    "availability.md",
    "current-state.md",
    "goals.md",
    "races.md",
    "zones.md",
    "health",
    "thresholds",
    "VO2max",
    "activities",
]
MOJIBAKE_MARKERS = (
    chr(0x00C3),
    chr(0x00C2),
    chr(0x00E2) + chr(0x20AC),
    chr(0x00EF) + chr(0x00BF) + chr(0x00BD),
    chr(0xFFFD),
)
PLANNING_SETUP_FILES = [
    "athlete-profile.md",
    "availability.md",
    "current-state.md",
    "goals.md",
    "races.md",
    "thresholds/thresholds_bike.md",
    "thresholds/thresholds_run.md",
    "thresholds/thresholds_swim.md",
    "VO2max/VO2max_bike.md",
    "VO2max/VO2max_run.md",
]
NEGATIVE_PLACEHOLDER_FILES = {
    "athlete-profile.md",
    "goals.md",
    "races.md",
    "thresholds/thresholds_bike.md",
    "thresholds/thresholds_run.md",
    "thresholds/thresholds_swim.md",
    "VO2max/VO2max_bike.md",
    "VO2max/VO2max_run.md",
}
NEGATIVE_PLACEHOLDER_RE = re.compile(
    r"\|\s*-1(?:\s*(?:W|cm|g/h|h|kg|mg/h|ml/h))?\s*\|"
)


def validate_text_files() -> list[str]:
    errors: list[str] = []
    roots = [ROOT / "scripts", ROOT / "plan-format", ROOT / "profiles", ROOT / "tests"]
    files = [ROOT / "AGENTS.md", ROOT / "trainingplan.html"]
    for directory in roots:
        files.extend(
            path
            for path in directory.rglob("*")
            if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES
        )
    for path in files:
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError as exc:
            errors.append(f"Invalid UTF-8 in {path.relative_to(ROOT)}: {exc}")
            continue
        markers = [marker for marker in MOJIBAKE_MARKERS if marker in text]
        if markers:
            errors.append(
                f"Possible mojibake in {path.relative_to(ROOT)}: {', '.join(repr(marker) for marker in markers)}"
            )
    return errors


def validate_profile_structure() -> list[str]:
    errors: list[str] = []
    for relative in REQUIRED_DATA_PATHS:
        path = DATA_DIR / relative
        if not path.exists():
            errors.append(f"Missing active profile path: {path.relative_to(ROOT)}")
    if not PROFILE_PLANS_DIR.is_dir():
        errors.append(f"Missing plans directory: {PROFILE_PLANS_DIR.relative_to(ROOT)}")
    return errors


def validate_health_tables() -> list[str]:
    errors: list[str] = []
    expected = {**HEALTH_TABLES, "loads.md": LOADS_HEADER}
    for name, expected_header in OPTIONAL_HEALTH_TABLES.items():
        if (DATA_DIR / "health" / name).exists():
            expected[name] = expected_header
    for name, expected_header in expected.items():
        path = DATA_DIR / "health" / name
        try:
            header, _ = read_table(path)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if header != expected_header:
            errors.append(
                f"Unexpected header in {path.relative_to(ROOT)}: expected {expected_header}, got {header}"
            )
    return errors


def validate_plans() -> list[str]:
    errors: list[str] = []
    for path in sorted(PROFILE_PLANS_DIR.glob("*.json")):
        try:
            plan = json.loads(path.read_text(encoding="utf-8-sig"))
            validate_plan(plan)
            if path.stem != plan["week"]:
                raise ValueError(f"filename does not match week {plan['week']}")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"Invalid plan {path.relative_to(ROOT)}: {exc}")
    return errors


def validate_planning_readiness(data_dir: Path = DATA_DIR) -> list[str]:
    """Reject explicit setup placeholders before an LLM creates a training plan."""
    errors: list[str] = []
    for relative in PLANNING_SETUP_FILES:
        path = data_dir / relative
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8-sig")
        markers: list[str] = []
        if "DEMO" in text:
            markers.append("DEMO")
        if "1900-01-01" in text:
            markers.append("1900-01-01")
        if relative in NEGATIVE_PLACEHOLDER_FILES and NEGATIVE_PLACEHOLDER_RE.search(text):
            markers.append("-1")
        if markers:
            try:
                display_path = path.relative_to(ROOT)
            except ValueError:
                display_path = path
            errors.append(
                f"Setup placeholders in {display_path}: {', '.join(markers)}"
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--planning-ready",
        action="store_true",
        help="Also reject demo placeholders that must be replaced before planning.",
    )
    args = parser.parse_args()

    checks = [
        validate_text_files,
        validate_profile_structure,
        validate_health_tables,
        validate_plans,
    ]
    if args.planning_ready:
        checks.append(validate_planning_readiness)
    errors = [error for check in checks for error in check()]
    if errors:
        print(f"Repository validation failed for profile {PROFILE!r} at {PROFILE_DIR}:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Repository validation passed for profile {PROFILE!r}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
