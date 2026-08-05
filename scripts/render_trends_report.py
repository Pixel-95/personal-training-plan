#!/usr/bin/env python3
"""Render a plots-only HTML/PDF report for an ISO week without creating a training plan."""

from __future__ import annotations

import argparse
from datetime import date

from date_utils import monday_of_iso_week
from generate_trend_plots import generate, trend_section_html
from markdown_tables import write_text_atomic
from profile_paths import PROFILE_PLANS_DIR
from render_plan import render_pdf


def build_html(week: str, newest: date) -> str:
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="de">',
            "<head>",
            '  <meta charset="utf-8">',
            '  <meta name="viewport" content="width=device-width, initial-scale=1">',
            f"  <title>Trainingsdaten {week}</title>",
            '  <link rel="stylesheet" href="../../../plan-format/training-plan.css">',
            "</head>",
            "<body>",
            "  <main>",
            "    <header>",
            f"      <h1>Trainingsdaten {week}</h1>",
            f'      <p class="eyebrow">Datenstand {newest.isoformat()}</p>',
            "    </header>",
            "",
            trend_section_html(week),
            "  </main>",
            "</body>",
            "</html>",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week", required=True, help="ISO week, e.g. 2026-W32.")
    parser.add_argument("--newest", required=True, help="Last available data date, YYYY-MM-DD.")
    parser.add_argument("--pdf", action="store_true", help="Also export a PDF.")
    args = parser.parse_args()

    monday_of_iso_week(args.week)
    newest = date.fromisoformat(args.newest)
    warnings = generate(args.week, newest)
    output = PROFILE_PLANS_DIR / f"{args.week}-trends.html"
    write_text_atomic(output, build_html(args.week, newest))
    print(f"Rendered HTML: {output}")
    if args.pdf:
        print(f"Rendered PDF: {render_pdf(output)}")
    if warnings:
        print("Trend warnings:")
        for warning in warnings:
            print(f"- {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
