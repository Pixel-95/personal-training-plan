#!/usr/bin/env python3
"""Resolve active training profile paths from local environment files."""

from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
PROFILES_DIR = ROOT / "profiles"


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_env_values(*, environment_prefixes: tuple[str, ...] = ()) -> dict[str, str]:
    """Load root and active profile .env values, then overlay process variables."""
    values = parse_env_file(ENV_PATH)
    allowed_keys = {"TRAINING_PROFILE"}

    for key, value in os.environ.items():
        if key in allowed_keys:
            values[key] = value

    profile = values.get("TRAINING_PROFILE", "").strip()
    if profile and not any(part in profile for part in ("/", "\\", "..")):
        values.update(parse_env_file(PROFILES_DIR / profile / ".env"))

    for key, value in os.environ.items():
        if any(key.startswith(prefix) for prefix in environment_prefixes):
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


require_profile()
