#!/usr/bin/env python3
"""Prepare synced context for a two-phase training plan proposal."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

from date_utils import iso_week_id, previous_iso_week
from profile_paths import DATA_DIR, PROFILE, ROOT, load_env_values


CONTEXT_FILES = [
    "current-state.md",
    "athlete-profile.md",
    "goals.md",
    "races.md",
    "availability.md",
    "thresholds/thresholds_bike.md",
    "thresholds/thresholds_run.md",
    "thresholds/thresholds_swim.md",
    "VO2max/VO2max_bike.md",
    "VO2max/VO2max_run.md",
    "health/hrv.md",
    "health/resting_heart_rate.md",
    "health/sleep.md",
    "health/steps.md",
    "health/weight.md",
    "health/loads.md",
    "zones.md",
]


def run_step(name: str, args: list[str]) -> int:
    print(f"\n== {name} ==", flush=True)
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True)
    if result.returncode == 0:
        print(f"{name}: ok", flush=True)
    else:
        print(f"{name}: warnings/errors (exit {result.returncode})", flush=True)
    return result.returncode


def has_intervals_api_key() -> bool:
    env = load_env_values(environment_prefixes=("intervals_icu_", "INTERVALS_ICU_"))
    return bool(env.get("intervals_icu_api_key") or env.get("INTERVALS_ICU_API_KEY"))


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week", help="Target plan ISO week, e.g. 2026-W27.")
    parser.add_argument("--analysis-week", help="ISO week to review before planning.")
    parser.add_argument("--days", type=int, default=30, help="Number of days to sync.")
    parser.add_argument("--newest", default=date.today().isoformat(), help="Newest local date YYYY-MM-DD.")
    parser.add_argument("--dry-run", action="store_true", help="Run sync steps in dry-run mode.")
    parser.add_argument("--skip-sync", action="store_true", help="Only validate and print context checklist.")
    args = parser.parse_args()

    newest = date.fromisoformat(args.newest)
    target_week = args.week or iso_week_id(newest)
    analysis_week = args.analysis_week or previous_iso_week(target_week)
    dry = ["--dry-run"] if args.dry_run else []

    codes = [
        run_step("Planning readiness validation", ["scripts/validate_repo.py", "--planning-ready"])
    ]
    if codes[-1] != 0:
        print("\nPreparation stopped before sync because planning readiness failed.")
        return 1

    if args.skip_sync:
        print("\nSync skipped by --skip-sync.")
    elif (ROOT / "scripts" / "pre_plan_sync.py").exists() and has_intervals_api_key():
        codes.append(
            run_step(
                "Pre-plan sync",
                [
                    "scripts/pre_plan_sync.py",
                    "--days",
                    str(args.days),
                    "--newest",
                    args.newest,
                    *dry,
                ],
            )
        )
    else:
        print("\n== Pre-plan sync ==")
        print("Skipped: no Intervals.icu API key found for the active profile.")
        codes.append(2)

    review_path = DATA_DIR / "activities" / analysis_week / f"review_{analysis_week}.md"
    plan_path = ROOT / "profiles" / PROFILE / "plans" / f"{target_week}.json"

    print("\n== LLM next steps ==")
    print(f"Active profile: {PROFILE}")
    print(f"Target plan week: {target_week}")
    print(f"Analysis week: {analysis_week}")
    print(f"Review path to create/update: {relative(review_path)}")
    print(f"Final plan path, only after explicit approval: {relative(plan_path)}")
    print("Required context files to read:")
    for item in CONTEXT_FILES:
        print(f"- {relative(DATA_DIR / item)}")
    print("Also inspect the newest relevant activity, health, injury, and review logs.")
    print("Update current-state.md and the weekly review before proposing the plan in chat.")
    print("Do not write plan JSON, HTML, or PDF until the user explicitly approves finalization.")

    warning_count = sum(1 for code in codes if code != 0)
    if warning_count:
        print("\nPreparation completed with warnings. LLM plausibility review is required.")
        return 2
    print("\nPreparation completed without script warnings. LLM plausibility review is still required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
