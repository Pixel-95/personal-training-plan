#!/usr/bin/env python3
"""Render a weekly training plan JSON into HTML and PDF artifacts."""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from generate_trend_plots import generate as generate_trends
from generate_trend_plots import trend_section_html


ROOT = Path(__file__).resolve().parents[1]
PLANS_DIR = ROOT / "plans"
ACTIVITIES_DIR = ROOT / "data" / "activities"

GERMAN_WEEKDAYS = {
    0: "Mo",
    1: "Di",
    2: "Mi",
    3: "Do",
    4: "Fr",
    5: "Sa",
    6: "So",
}

SPORT_TAGS = {
    "swim": "Swim",
    "bike": "Bike",
    "run": "Run",
    "strength": "Strength",
    "recovery": "Recovery",
    "race": "Race",
}

BROWSER_CANDIDATES = [
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
]


def esc(text: Any) -> str:
    return html.escape(str(text), quote=True)


def parse_day(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def parse_duration_minutes(value: str) -> int:
    text = value.strip().lower()
    if text.endswith("min"):
        return int(text[:-3])
    if text.endswith("h"):
        core = text[:-1]
        if ":" in core:
            hours, minutes = core.split(":", 1)
            return int(hours) * 60 + int(minutes)
        return int(round(float(core) * 60))
    raise ValueError(f"Unsupported duration format: {value}")


def parse_distance_m(value: str) -> int:
    text = value.strip().lower()
    if not text.endswith("m"):
        raise ValueError(f"Unsupported distance format: {value}")
    return int(text[:-1])


def format_hhmm(total_minutes: int) -> str:
    return f"{total_minutes // 60}:{total_minutes % 60:02d}h"


def inline_markdown_to_html(text: str) -> str:
    parts: list[str] = []
    pattern = re.compile(r"`([^`]+)`")
    last = 0
    for match in pattern.finditer(text):
        parts.append(esc(text[last:match.start()]))
        parts.append(f"<code>{esc(match.group(1))}</code>")
        last = match.end()
    parts.append(esc(text[last:]))
    return "".join(parts)


def review_paragraphs(analysis_week: str | None) -> list[str]:
    if not analysis_week:
        return []
    path = ACTIVITIES_DIR / analysis_week / f"review_{analysis_week}.md"
    if not path.exists():
        raise FileNotFoundError(f"Review not found: {path}")
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    text = re.split(r"\n## ", text, maxsplit=1)[0].strip()
    lines = text.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    body = "\n".join(lines).strip()
    if not body:
        return []
    return [block.strip() for block in re.split(r"\n\s*\n", body) if block.strip()]


def summary_from_plan(plan: dict[str, Any]) -> dict[str, str]:
    override = plan.get("summary_override")
    if override:
        return {
            "total": override["total"],
            "swim": override["swim"],
            "bike": override["bike"],
            "run": override["run"],
        }
    total_minutes = 0
    bike_minutes = 0
    run_minutes = 0
    swim_m = 0
    for day in plan["days"]:
        for session in day.get("sessions", []):
            minutes = parse_duration_minutes(session["duration"])
            total_minutes += minutes
            sport = session["sport"]
            if sport == "bike":
                bike_minutes += minutes
            elif sport == "run":
                run_minutes += minutes
            elif sport == "swim":
                swim_m += parse_distance_m(session["amount"])
    return {
        "total": format_hhmm(total_minutes),
        "swim": f"{swim_m}m",
        "bike": format_hhmm(bike_minutes),
        "run": format_hhmm(run_minutes),
    }


def validate_plan(plan: dict[str, Any]) -> None:
    required_top = {"schema_version", "week", "days"}
    missing = required_top - set(plan)
    if missing:
        raise ValueError(f"Missing plan keys: {sorted(missing)}")
    if plan["schema_version"] != 1:
        raise ValueError(f"Unsupported schema_version: {plan['schema_version']}")
    week = plan["week"]
    if not re.fullmatch(r"\d{4}-W\d{2}", week):
        raise ValueError(f"Invalid week format: {week}")
    days = plan["days"]
    if not isinstance(days, list) or not days:
        raise ValueError("days must be a non-empty list")
    seen_dates: set[str] = set()
    for day in days:
        if "date" not in day:
            raise ValueError("Each day needs a date")
        day_str = day["date"]
        if day_str in seen_dates:
            raise ValueError(f"Duplicate day date: {day_str}")
        seen_dates.add(day_str)
        parsed = parse_day(day_str)
        iso_year, iso_week, _ = parsed.isocalendar()
        if f"{iso_year}-W{iso_week:02d}" != week:
            raise ValueError(f"Day {day_str} does not belong to week {week}")
        for session in day.get("sessions", []):
            for key in ("sport", "title", "amount", "duration"):
                if key not in session:
                    raise ValueError(f"Session on {day_str} missing key: {key}")
            parse_duration_minutes(session["duration"])
            if session["sport"] == "swim":
                parse_distance_m(session["amount"])


def render_session(session: dict[str, Any]) -> str:
    sport = session["sport"]
    tag = session.get("tag") or SPORT_TAGS.get(sport, sport.title())
    title = session["title"]
    amount = session["amount"]
    content = session.get("content", [])
    parts = [
        f'          <section class="session {esc(sport)}">',
        f'            <span class="amount">{esc(amount)}</span>',
        f'            <span class="tag">{esc(tag)}</span>',
        f'            <h3>{esc(title)}</h3>',
    ]
    if len(content) == 1:
        parts.append(f'            <p>{inline_markdown_to_html(content[0])}</p>')
    elif len(content) > 1:
        parts.append("            <ul>")
        for item in content:
            parts.append(f'              <li>{inline_markdown_to_html(item)}</li>')
        parts.append("            </ul>")
    parts.append("          </section>")
    return "\n".join(parts)


def render_day(day: dict[str, Any]) -> str:
    current = parse_day(day["date"])
    weekday = GERMAN_WEEKDAYS[current.weekday()]
    sessions = day.get("sessions", [])
    session_html = "\n".join(render_session(session) for session in sessions)
    if session_html:
        session_html = "\n" + session_html + "\n"
    return (
        "      <article class=\"day\">\n"
        "        <div class=\"day-head\">\n"
        f"          <h2 class=\"day-name\">{weekday} <span class=\"date\">{current.isoformat()}</span></h2>\n"
        "        </div>\n"
        f"        <div class=\"sessions\">{session_html}        </div>\n"
        "      </article>"
    )


def build_analysis_section(paragraphs: list[str]) -> str:
    if not paragraphs:
        return ""
    body = "\n".join(f"      <p>{inline_markdown_to_html(paragraph)}</p>" for paragraph in paragraphs)
    return (
        '    <section class="analysis" aria-label="Wochenanalyse und Implikationen">\n'
        "      <h2>Wochenanalyse</h2>\n"
        f"{body}\n"
        "    </section>"
    )


def build_html(plan: dict[str, Any], newest: date, include_trends: bool) -> str:
    summary = summary_from_plan(plan)
    week = plan["week"]
    dates = sorted(parse_day(day["date"]) for day in plan["days"])
    start = dates[0]
    end = dates[-1]
    analysis = build_analysis_section(review_paragraphs(plan.get("analysis_week")))
    days_html = "\n\n".join(render_day(day) for day in sorted(plan["days"], key=lambda item: item["date"]))
    trend_html = trend_section_html(week) if include_trends else ""
    sections = [
        "<!doctype html>",
        '<html lang="de">',
        "<head>",
        '  <meta charset="utf-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1">',
        f"  <title>Trainingsplan {esc(week)}</title>",
        '  <link rel="icon" type="image/png" href="../assets/calendar.png">',
        '  <link rel="stylesheet" href="training-plan.css">',
        "</head>",
        "<body>",
        "  <main>",
        "    <header>",
        "      <div>",
        f"        <h1>Trainingsplan {esc(week)}</h1>",
        "      </div>",
        f'      <p class="eyebrow">{start.isoformat()} bis {end.isoformat()}</p>',
        "    </header>",
        "",
        '    <section class="summary" aria-label="Wochenübersicht">',
        '      <div class="metric"><span>Gesamtumfang</span><strong>' + esc(summary["total"]) + "</strong></div>",
        '      <div class="metric"><span>Swim</span><strong>' + esc(summary["swim"]) + "</strong></div>",
        '      <div class="metric"><span>Bike</span><strong>' + esc(summary["bike"]) + "</strong></div>",
        '      <div class="metric"><span>Run</span><strong>' + esc(summary["run"]) + "</strong></div>",
        "    </section>",
        "",
        '    <section class="week" aria-label="Tagesplan">',
        days_html,
        "    </section>",
    ]
    if analysis:
        sections.extend(["", analysis])
    if trend_html:
        sections.extend(["", trend_html])
    sections.extend(["  </main>", "</body>", "</html>", ""])
    return "\n".join(sections)


def write_html(plan_path: Path, html_text: str) -> Path:
    output = plan_path.with_suffix(".html")
    output.write_text(html_text, encoding="utf-8")
    return output


def detect_browser() -> Path:
    for candidate in BROWSER_CANDIDATES:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("No supported browser found for PDF export.")


def render_pdf(html_path: Path) -> Path:
    browser = detect_browser()
    pdf_path = html_path.with_suffix(".pdf")
    original = html_path.read_text(encoding="utf-8")
    mobile_page_style = (
        "<style>"
        "@media print {"
        "@page { size: 140mm 297mm; margin: 0; }"
        "}"
        "</style>"
    )
    mobile_html = original.replace("</head>", f"  {mobile_page_style}\n</head>", 1)
    mobile_html = re.sub(r"<body(\s*)>", '<body class="pdf-mobile">', mobile_html, count=1)
    temp_path = html_path.with_name(f"{html_path.stem}.__pdf_mobile__.html")
    try:
        temp_path.write_text(mobile_html, encoding="utf-8")
        file_url = temp_path.resolve().as_uri()
        subprocess.run(
            [
                str(browser),
                "--headless=new",
                "--disable-gpu",
                "--print-to-pdf-no-header",
                f"--print-to-pdf={pdf_path}",
                file_url,
            ],
            check=True,
        )
    finally:
        if temp_path.exists():
            temp_path.unlink()
    return pdf_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Render weekly training plan JSON into HTML and PDF.")
    parser.add_argument("--plan", required=True, help="Path to plans/YYYY-Www.json")
    parser.add_argument("--newest", help="Newest date for trend plots, YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--skip-trends", action="store_true", help="Do not regenerate or embed trend plots.")
    parser.add_argument("--pdf", action="store_true", help="Also export PDF from the rendered HTML.")
    args = parser.parse_args()

    plan_path = Path(args.plan)
    if not plan_path.is_absolute():
        plan_path = ROOT / plan_path

    newest = parse_day(args.newest) if args.newest else date.today()
    if newest is None:
        raise SystemExit("--newest must use YYYY-MM-DD")

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    validate_plan(plan)

    warnings: list[str] = []
    include_trends = not args.skip_trends
    if include_trends:
        warnings = generate_trends(plan["week"], newest)

    html_text = build_html(plan, newest, include_trends)
    html_path = write_html(plan_path, html_text)
    print(f"Rendered HTML: {html_path}")

    if warnings:
        print("Trend warnings:")
        for warning in warnings:
            print(f"- {warning}")

    if args.pdf:
        pdf_path = render_pdf(html_path)
        print(f"Rendered PDF: {pdf_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
