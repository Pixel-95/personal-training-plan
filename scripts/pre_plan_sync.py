#!/usr/bin/env python3
"""Run the full pre-plan data sync pipeline."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_step(name: str, args: list[str]) -> int:
    print(f"\n== {name} ==", flush=True)
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True)
    if result.returncode == 0:
        print(f"{name}: ok", flush=True)
    else:
        print(f"{name}: warnings/errors (exit {result.returncode})", flush=True)
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run pre-plan sync scripts.")
    parser.add_argument("--days", type=int, default=30, help="Number of days to sync.")
    parser.add_argument("--newest", default=date.today().isoformat(), help="Newest local date YYYY-MM-DD.")
    parser.add_argument("--dry-run", action="store_true", help="Run all steps in dry-run mode.")
    args = parser.parse_args()

    common = ["--days", str(args.days), "--newest", args.newest]
    dry = ["--dry-run"] if args.dry_run else []
    steps = [
        ("FIT download", ["scripts/download_fit_files.py", *common, *dry]),
        ("Health update", ["scripts/update_health.py", *common, *dry]),
        ("FIT analysis", ["scripts/analyze_fit_files.py", *dry]),
        ("Load update", ["scripts/update_loads.py", "--newest", args.newest, *dry]),
    ]

    codes = [run_step(name, command) for name, command in steps]
    warning_count = sum(1 for code in codes if code != 0)
    print("\n== Summary ==", flush=True)
    if warning_count:
        print(f"Pipeline completed with {warning_count} warning/error step(s). LLM plausibility review required.")
        return 2
    print("Pipeline completed without script warnings. LLM plausibility review still required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
