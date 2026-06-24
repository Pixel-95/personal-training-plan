#!/usr/bin/env python3
"""Resolve active training profile paths from the repository .env file."""

from __future__ import annotations

import json
import os
from pathlib import Path

from markdown_tables import write_text_atomic


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
PROFILES_DIR = ROOT / "profiles"
BROWSER_PROFILE_PATH = ROOT / "active-profile.js"


def load_env_values(*, environment_prefixes: tuple[str, ...] = ()) -> dict[str, str]:
    """Load .env values and optionally overlay matching process variables."""
    values: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    allowed_keys = {"TRAINING_PROFILE"}
    for key, value in os.environ.items():
        if key in allowed_keys or any(key.startswith(prefix) for prefix in environment_prefixes):
            values[key] = value
    return values


def active_profile() -> str:
    profile = load_env_values().get("TRAINING_PROFILE", "").strip()
    if not profile:
        raise RuntimeError("TRAINING_PROFILE must be set in .env.")
    if any(part in profile for part in ("/", "\\", "..")):
        raise RuntimeError(f"Invalid TRAINING_PROFILE value: {profile!r}")
    return profile


PROFILE = active_profile()
PROFILE_DIR = PROFILES_DIR / PROFILE
DATA_DIR = PROFILE_DIR / "data"
PROFILE_PLANS_DIR = PROFILE_DIR / "plans"


def require_profile() -> None:
    if not PROFILE_DIR.exists():
        raise RuntimeError(
            f"Training profile {PROFILE!r} does not exist at {PROFILE_DIR}. "
            "Set TRAINING_PROFILE in .env or create the profile folder."
        )


def write_browser_profile_config() -> None:
    profile_json = json.dumps(PROFILE, ensure_ascii=False)
    write_text_atomic(BROWSER_PROFILE_PATH, f"window.TRAINING_PROFILE = {profile_json};\n")


require_profile()
write_browser_profile_config()
