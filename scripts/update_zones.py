#!/usr/bin/env python3
"""Recalculate the active profile's absolute training zones."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from markdown_tables import read_table, render_table, write_text_atomic
from profile_paths import DATA_DIR


SWIM_SPEED = {
    "Z5": ("Very fast", 1.03, 1.09),
    "Z4": ("Fast", 0.98, 1.03),
    "Z3": ("Moderate", 0.90, 0.98),
    "Z2": ("Easy", 0.87, 0.90),
}
BIKE = {
    "Z6": ("Anaerobic", 1.10, None, 1.10, None),
    "Z5": ("VO2max", 1.04, 1.10, 1.05, 1.10),
    "Z4": ("Threshold", 0.95, 1.04, 0.90, 1.05),
    "Z3": ("Tempo", 0.82, 0.95, 0.74, 0.90),
    "Z2": ("Endurance", 0.75, 0.82, 0.56, 0.74),
    "Z1": ("Recovery", None, 0.75, None, 0.56),
}
RUN = {
    "Z6": ("Anaerobic", 1.10, None, 1.08, None),
    "Z5": ("VO2max", 1.04, 1.10, 1.03, 1.08),
    "Z4": ("Threshold", 0.95, 1.04, 0.93, 1.03),
    "Z3": ("Tempo", 0.87, 0.95, 0.87, 0.93),
    "Z2": ("Endurance", 0.80, 0.87, 0.80, 0.87),
    "Z1": ("Recovery", None, 0.80, None, 0.80),
}


def latest_values(path: Path) -> list[str]:
    _, rows = read_table(path)
    if not rows:
        raise ValueError(f"No threshold values found in {path}")
    return rows[0]


def pace_seconds(value: str) -> int:
    minutes, seconds = value.split(":", 1)
    return int(minutes) * 60 + int(seconds)


def format_pace(seconds: float | None) -> str:
    if seconds is None:
        return "/"
    rounded = math.floor(seconds + 0.5)
    return f"{rounded // 60}:{rounded % 60:02d}"


def scaled(value: float, factor: float | None) -> str:
    return "/" if factor is None else str(math.floor(value * factor + 0.5))


def build_zones(data_dir: Path = DATA_DIR) -> str:
    css = pace_seconds(latest_values(data_dir / "thresholds" / "thresholds_swim.md")[1])
    ftp = float(latest_values(data_dir / "thresholds" / "thresholds_bike.md")[1])
    run_row = latest_values(data_dir / "thresholds" / "thresholds_run.md")
    run_lthr = float(run_row[1])
    run_pace = pace_seconds(run_row[2])
    bike_lthr = run_lthr - 5

    swim_rows = [
        [zone, name, format_pace(css / lower), format_pace(css / upper)]
        for zone, (name, lower, upper) in SWIM_SPEED.items()
    ]
    bike_rows = [
        [
            zone,
            name,
            scaled(bike_lthr, hr_lower),
            scaled(bike_lthr, hr_upper),
            scaled(ftp, power_lower),
            scaled(ftp, power_upper),
        ]
        for zone, (name, hr_lower, hr_upper, power_lower, power_upper) in BIKE.items()
    ]
    run_rows = [
        [
            zone,
            name,
            scaled(run_lthr, hr_lower),
            scaled(run_lthr, hr_upper),
            format_pace(run_pace / speed_lower) if speed_lower else "/",
            format_pace(run_pace / speed_upper) if speed_upper else "/",
        ]
        for zone, (name, hr_lower, hr_upper, speed_lower, speed_upper) in RUN.items()
    ]

    sections = [
        "# Ausgerechnete Zonen\n",
        "## Swim\n",
        render_table(["Zone", "Zonenname", "Untere Grenze", "Obere Grenze"], swim_rows).rstrip(),
        "\n## Bike\n",
        render_table(
            [
                "Zone",
                "Zonenname",
                "Untere HR-Grenze / bpm",
                "Obere HR-Grenze / bpm",
                "Untere Power-Grenze / W",
                "Obere Power-Grenze / W",
            ],
            bike_rows,
        ).rstrip(),
        "\n## Run\n",
        render_table(
            [
                "Zone",
                "Zonenname",
                "Untere HR-Grenze / bpm",
                "Obere HR-Grenze / bpm",
                "Untere Pace-Grenze / min:sec/km",
                "Obere Pace-Grenze / min:sec/km",
            ],
            run_rows,
        ).rstrip(),
    ]
    return "\n".join(sections) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing.")
    args = parser.parse_args()

    path = DATA_DIR / "zones.md"
    content = build_zones()
    if args.dry_run:
        print(f"WOULD WRITE {path}")
    else:
        write_text_atomic(path, content)
        print(f"WROTE {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
