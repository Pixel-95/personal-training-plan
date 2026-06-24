#!/usr/bin/env python3
"""Generate static SVG trend plots for the weekly training plan."""

from __future__ import annotations

import argparse
import html
import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from markdown_tables import read_table as read_markdown_table
from markdown_tables import rows_as_dicts, write_text_atomic
from profile_paths import DATA_DIR, PROFILE_PLANS_DIR, ROOT


PLAN_DIR = PROFILE_PLANS_DIR
TREND_DIR = PLAN_DIR / "assets"

W = 1180
H = 540
LEFT = 70
RIGHT = 118
TOP = 74
BOTTOM = 54

COLORS = {
    "ink": "#1d252d",
    "muted": "#66717d",
    "grid": "#e8ecf1",
    "axis": "#cfd6df",
    "paper": "#ffffff",
    "plot": "#fbfcfd",
    "hrv_daily": "#a8b0ba",
    "hrv_trend_good": "#287c71",
    "hrv_trend_bad": "#d9822b",
    "hrv_band": "#dcefe9",
    "rhr": "#b64b3a",
    "sleep": "#7aa6d8",
    "sleep_score": "#6f5aa7",
    "steps": "#8a98a8",
    "weight": "#b9c3cf",
    "weight_trend": "#1d252d",
    "body_fat": "#c9534f",
    "body_fat_trend": "#9f2f25",
    "run": "#b64b3a",
    "tss": "#d4dae2",
    "load_band": "#dcefe9",
    "atl": "#b64b3a",
    "ctl": "#287c71",
    "tsb": "#2f6fa3",
    "acr": "#6f5aa7",
    "swim": "#2f6fa3",
    "bike": "#287c71",
    "run_pace": "#9f2f25",
    "vo2_run": "#b64b3a",
}


RIGHT_COMPACT = 34
RIGHT_LOAD = 64
RIGHT_LABELS = 118
ACTIVE_RIGHT = RIGHT_LABELS


def set_canvas(width: int, height: int, left: int, right: int, top: int, bottom: int, active_right: int) -> tuple[int, int, int, int, int, int, int]:
    global W, H, LEFT, RIGHT, TOP, BOTTOM, ACTIVE_RIGHT
    previous = (W, H, LEFT, RIGHT, TOP, BOTTOM, ACTIVE_RIGHT)
    W = width
    H = height
    LEFT = left
    RIGHT = right
    TOP = top
    BOTTOM = bottom
    ACTIVE_RIGHT = active_right
    return previous


def restore_canvas(previous: tuple[int, int, int, int, int, int, int]) -> None:
    global W, H, LEFT, RIGHT, TOP, BOTTOM, ACTIVE_RIGHT
    W, H, LEFT, RIGHT, TOP, BOTTOM, ACTIVE_RIGHT = previous


@dataclass(frozen=True)
class Point:
    day: date
    value: float
    label: str = ""


@dataclass
class WeeklyStats:
    week: str
    monday: date
    duration_s: dict[str, float]
    tss: dict[str, float]
    long_session_s: dict[str, float]
    zones: dict[str, dict[str, float]]


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def read_table(path: Path) -> list[dict[str, str]]:
    header, rows = read_markdown_table(path)
    return [row for row in rows_as_dicts(header, rows) if row.get("Datum")]


def parse_day(value: str) -> date | None:
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    text = value.strip().replace(",", ".")
    if not text or text in {"-", "/"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_hhmm(value: str | None) -> float | None:
    if value is None or value.strip() in {"", "-", "/"}:
        return None
    match = re.fullmatch(r"(\d+):(\d{2})", value.strip())
    if not match:
        return None
    return int(match.group(1)) + int(match.group(2)) / 60


def parse_pace_seconds(value: str | None) -> float | None:
    if value is None or value.strip() in {"", "-", "/"}:
        return None
    match = re.fullmatch(r"(\d+):(\d{2})", value.strip())
    if not match:
        return None
    return int(match.group(1)) * 60 + int(match.group(2))


def pace_label(seconds: float) -> str:
    rounded = int(round(seconds))
    return f"{rounded // 60}:{rounded % 60:02d}"


def parse_duration_seconds(value: str | None) -> float | None:
    if value is None or value.strip() in {"", "-", "/"}:
        return None
    parts = value.strip().split(":")
    try:
        if len(parts) == 2:
            minutes, seconds = (int(parts[0]), int(parts[1]))
            return minutes * 60 + seconds
        if len(parts) == 3:
            hours, minutes, seconds = (int(parts[0]), int(parts[1]), int(parts[2]))
            return hours * 3600 + minutes * 60 + seconds
    except ValueError:
        return None
    return None


def hours_label_from_seconds(seconds: float) -> str:
    rounded_minutes = round(seconds / 60)
    return f"{rounded_minutes // 60}:{rounded_minutes % 60:02d}h"


def zone_amount_label(sport: str, raw_value: float) -> str:
    if sport == "swim":
        return f"{raw_value:.0f}m"
    return hours_label_from_seconds(raw_value)


def number_label(value: float, unit: str = "", digits: int = 0) -> str:
    if digits == 0:
        text = f"{value:.0f}"
    else:
        text = f"{value:.{digits}f}".rstrip("0").rstrip(".")
    return f"{text}{unit}"


def points_from_table(path: Path, col: str, parser=parse_float) -> list[Point]:
    points: list[Point] = []
    for row in read_table(path):
        day = parse_day(row.get("Datum", ""))
        value = parser(row.get(col))
        if day is None or value is None or not math.isfinite(value):
            continue
        points.append(Point(day, value, row.get(col, "")))
    return sorted(points, key=lambda p: p.day)


def points_from_first_available(path: Path, cols: list[str], parser=parse_float) -> list[Point]:
    for col in cols:
        points = points_from_table(path, col, parser)
        if points:
            return points
    return []


def parse_activity_summary(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8-sig")
    summary: dict[str, str] = {}
    for match in re.finditer(r"^- ([^:\n]+): (.+)$", text, re.MULTILINE):
        summary[match.group(1).strip()] = match.group(2).strip()
    return summary


def markdown_section_table(text: str, section_title: str) -> tuple[list[str], list[dict[str, str]]]:
    match = re.search(rf"## {re.escape(section_title)}\n\n((?:\|.*\n)+)", text)
    if not match:
        return [], []
    lines = [line.strip() for line in match.group(1).splitlines() if line.strip().startswith("|")]
    if len(lines) < 2:
        return [], []
    header = [cell.strip() for cell in lines[0].strip("|").split("|")]
    rows: list[dict[str, str]] = []
    for line in lines[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) == len(header):
            rows.append(dict(zip(header, cells)))
    return header, rows


def window(points: list[Point], start: date, end: date) -> list[Point]:
    return [p for p in points if start <= p.day <= end]


def parse_week_id(week: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d{4})-W(\d{2})", week)
    if not match:
        raise ValueError(f"Invalid ISO week: {week}")
    return int(match.group(1)), int(match.group(2))


def monday_of_week(week: str) -> date:
    year, iso_week = parse_week_id(week)
    return date.fromisocalendar(year, iso_week, 1)


def previous_week(week: str) -> str:
    monday = monday_of_week(week)
    prev = monday - timedelta(days=7)
    year, iso_week, _ = prev.isocalendar()
    return f"{year}-W{iso_week:02d}"


def trailing_weeks(week: str, count: int) -> list[str]:
    monday = monday_of_week(week)
    weeks: list[str] = []
    for offset in range(count - 1, -1, -1):
        current = monday - timedelta(days=7 * offset)
        year, iso_week, _ = current.isocalendar()
        weeks.append(f"{year}-W{iso_week:02d}")
    return weeks


def activity_md_paths(week: str) -> list[Path]:
    folder = DATA_DIR / "activities" / week
    if not folder.exists():
        return []
    return sorted(path for path in folder.glob("*.md") if not path.name.startswith("review_"))


def sport_key(label: str) -> str | None:
    normalized = label.strip().lower()
    if normalized == "schwimmen":
        return "swim"
    if normalized == "radfahren":
        return "bike"
    if normalized == "laufen":
        return "run"
    return None


def parse_zone_amount(value: str) -> float:
    if value in {"", "-", "/"}:
        return 0.0
    if value.endswith("m"):
        return float(value[:-1])
    parsed = parse_duration_seconds(value)
    return parsed or 0.0


def week_activity_stats(week: str) -> WeeklyStats:
    monday = monday_of_week(week)
    duration_s = {"swim": 0.0, "bike": 0.0, "run": 0.0}
    tss = {"swim": 0.0, "bike": 0.0, "run": 0.0}
    long_session_s = {"bike": 0.0, "run": 0.0}
    zones = {
        "swim": {zone: 0.0 for zone in ["Z1", "Z2", "Z3", "Z4", "Z5"]},
        "bike": {zone: 0.0 for zone in ["Z1", "Z2", "Z3", "Z4", "Z5", "Z6"]},
        "run": {zone: 0.0 for zone in ["Z1", "Z2", "Z3", "Z4", "Z5", "Z6"]},
    }
    for path in activity_md_paths(week):
        text = path.read_text(encoding="utf-8-sig")
        summary = parse_activity_summary(path)
        sport = sport_key(summary.get("Sport", ""))
        if sport is None:
            continue
        duration = parse_duration_seconds(summary.get("Dauer"))
        if duration is not None:
            duration_s[sport] += duration
            if sport in long_session_s:
                long_session_s[sport] = max(long_session_s[sport], duration)
        tss_value = parse_float(summary.get("TSS"))
        if tss_value is not None:
            tss[sport] += tss_value
        header, rows = markdown_section_table(text, "Zonen")
        if header and rows:
            value_key = "Distanz" if sport == "swim" else "Zeit"
            for row in rows:
                zone = row.get("Zone")
                if zone in zones[sport]:
                    zones[sport][zone] += parse_zone_amount(row.get(value_key, ""))
    return WeeklyStats(week=week, monday=monday, duration_s=duration_s, tss=tss, long_session_s=long_session_s, zones=zones)


def weekly_stats_series(week: str, count: int = 12) -> list[WeeklyStats]:
    return [week_activity_stats(item) for item in trailing_weeks(week, count)]


def update_review_stats_block(stats: WeeklyStats) -> None:
    review_path = DATA_DIR / "activities" / stats.week / f"review_{stats.week}.md"
    if not review_path.exists():
        return
    table = "\n".join(
        [
            "## Wochenstatistik",
            "",
            "| Kennzahl | Swim | Bike | Run |",
            "|-|-|-|-|",
            f"| Dauer | {hours_label_from_seconds(stats.duration_s['swim'])} | {hours_label_from_seconds(stats.duration_s['bike'])} | {hours_label_from_seconds(stats.duration_s['run'])} |",
            f"| TSS | {number_label(stats.tss['swim'], digits=1)} | {number_label(stats.tss['bike'], digits=1)} | {number_label(stats.tss['run'], digits=1)} |",
        ]
    )
    text = review_path.read_text(encoding="utf-8-sig").rstrip() + "\n"
    pattern = re.compile(r"\n## Wochenstatistik\n[\s\S]*?(?=\n## |\Z)")
    if pattern.search(text):
        text = pattern.sub("\n" + table + "\n", text)
    else:
        text = text + "\n\n" + table + "\n"
    write_text_atomic(review_path, text)


def update_review_stats_blocks(series: list[WeeklyStats]) -> None:
    for stats in series:
        update_review_stats_block(stats)


def x_for(day: date, start: date, end: date) -> float:
    span = max((end - start).days, 1)
    return LEFT + ((day - start).days / span) * (W - LEFT - ACTIVE_RIGHT)


def domain(values: list[float], include_zero: bool = False, fixed: tuple[float, float] | None = None) -> tuple[float, float]:
    if fixed is not None:
        return fixed
    clean = [v for v in values if math.isfinite(v)]
    if include_zero:
        clean.append(0)
    if not clean:
        return 0, 1
    lo = min(clean)
    hi = max(clean)
    if math.isclose(lo, hi):
        pad = max(abs(lo) * 0.03, 1)
    else:
        pad = (hi - lo) * 0.12
    return lo - pad, hi + pad


def y_for(value: float, lo: float, hi: float) -> float:
    if math.isclose(lo, hi):
        return (TOP + H - BOTTOM) / 2
    return H - BOTTOM - ((value - lo) / (hi - lo)) * (H - TOP - BOTTOM)


def svg_open(title: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(title)}">',
        f'<rect x="0" y="0" width="{W}" height="{H}" rx="18" fill="{COLORS["paper"]}"/>',
        f'<rect x="{LEFT}" y="{TOP}" width="{W - LEFT - ACTIVE_RIGHT}" height="{H - TOP - BOTTOM}" rx="10" fill="{COLORS["plot"]}" stroke="{COLORS["grid"]}"/>',
        f'<text x="24" y="34" fill="{COLORS["ink"]}" font-size="24" font-weight="700" font-family="Inter, system-ui, sans-serif">{esc(title)}</text>',
    ]


def svg_close() -> str:
    return "</svg>\n"


def add_grid(
    parts: list[str],
    start: date,
    end: date,
    y_lo: float,
    y_hi: float,
    left_label: str = "",
    right_label: str = "",
    show_y_labels: bool = True,
    show_x_grid: bool = True,
) -> None:
    for i in range(5):
        y = TOP + i * (H - TOP - BOTTOM) / 4
        parts.append(f'<line x1="{LEFT}" y1="{y:.1f}" x2="{W - ACTIVE_RIGHT}" y2="{y:.1f}" stroke="{COLORS["grid"]}" stroke-width="1"/>')
    if show_x_grid:
        tick_count = 5
        for i in range(tick_count):
            day = start + timedelta(days=round(i * (end - start).days / (tick_count - 1)))
            x = x_for(day, start, end)
            parts.append(f'<line x1="{x:.1f}" y1="{TOP}" x2="{x:.1f}" y2="{H - BOTTOM}" stroke="{COLORS["grid"]}" stroke-width="1"/>')
            parts.append(f'<text x="{x:.1f}" y="{H - 20}" text-anchor="middle" fill="{COLORS["muted"]}" font-size="13" font-family="Inter, system-ui, sans-serif">{day.strftime("%d.%m.")}</text>')
    if show_y_labels:
        parts.append(f'<text x="{LEFT - 12}" y="{TOP + 5}" text-anchor="end" fill="{COLORS["muted"]}" font-size="13" font-family="Inter, system-ui, sans-serif">{esc(left_label or f"{y_hi:.0f}")}</text>')
        parts.append(f'<text x="{LEFT - 12}" y="{H - BOTTOM}" text-anchor="end" fill="{COLORS["muted"]}" font-size="13" font-family="Inter, system-ui, sans-serif">{esc(f"{y_lo:.0f}")}</text>')
    if right_label and show_y_labels:
        parts.append(f'<text x="{W - ACTIVE_RIGHT + 12}" y="{TOP + 5}" fill="{COLORS["muted"]}" font-size="13" font-family="Inter, system-ui, sans-serif">{esc(right_label)}</text>')


def add_no_data(parts: list[str]) -> None:
    parts.append(f'<text x="{W / 2}" y="{H / 2}" text-anchor="middle" fill="{COLORS["muted"]}" font-size="18" font-family="Inter, system-ui, sans-serif">Keine Daten im Zeitraum</text>')


def add_line(
    parts: list[str],
    points: list[Point],
    start: date,
    end: date,
    lo: float,
    hi: float,
    color: str,
    width: float = 3,
    dashed: bool = False,
    draw_points: bool = True,
) -> None:
    if len(points) == 1:
        x = x_for(points[0].day, start, end)
        y = y_for(points[0].value, lo, hi)
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5.2" fill="{color}"/>')
        return
    if not points:
        return
    coords = " ".join(f'{x_for(p.day, start, end):.1f},{y_for(p.value, lo, hi):.1f}' for p in points)
    dash = ' stroke-dasharray="7 6"' if dashed else ""
    parts.append(f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"{dash}/>')
    if draw_points:
        for p in points:
            x = x_for(p.day, start, end)
            y = y_for(p.value, lo, hi)
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.8" fill="{color}" stroke="{COLORS["paper"]}" stroke-width="1.6"/>')


def add_points(parts: list[str], points: list[Point], start: date, end: date, lo: float, hi: float, color: str, radius: float = 2.8, opacity: float = 1.0) -> None:
    for p in points:
        x = x_for(p.day, start, end)
        y = y_for(p.value, lo, hi)
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="{color}" opacity="{opacity}"/>')


def add_colored_line_by_day(
    parts: list[str],
    points: list[Point],
    start: date,
    end: date,
    lo: float,
    hi: float,
    color_by_day: dict[date, str],
    default_color: str,
    width: float = 3,
) -> None:
    if not points:
        return
    if len(points) == 1:
        color = color_by_day.get(points[0].day, default_color)
        x = x_for(points[0].day, start, end)
        y = y_for(points[0].value, lo, hi)
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5.2" fill="{color}"/>')
        return
    for prev, current in zip(points, points[1:]):
        color = color_by_day.get(current.day, default_color)
        x1 = x_for(prev.day, start, end)
        y1 = y_for(prev.value, lo, hi)
        x2 = x_for(current.day, start, end)
        y2 = y_for(current.value, lo, hi)
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="{width}" stroke-linecap="round"/>')
    for p in points:
        color = color_by_day.get(p.day, default_color)
        x = x_for(p.day, start, end)
        y = y_for(p.value, lo, hi)
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.8" fill="{color}" stroke="{COLORS["paper"]}" stroke-width="1.6"/>')


def add_bars(
    parts: list[str],
    points: list[Point],
    start: date,
    end: date,
    lo: float,
    hi: float,
    color: str,
    baseline: float | None = None,
    width_factor: float = 0.72,
    max_width: float = 13,
) -> None:
    days = max((end - start).days + 1, 1)
    bar_w = max(1.5, min(max_width, (W - LEFT - RIGHT) / days * width_factor))
    base = baseline if baseline is not None else max(0, lo)
    base_y = y_for(base, lo, hi)
    for p in points:
        x = x_for(p.day, start, end) - bar_w / 2
        y = y_for(p.value, lo, hi)
        height = abs(base_y - y)
        top = min(base_y, y)
        parts.append(f'<rect x="{x:.1f}" y="{top:.1f}" width="{bar_w:.1f}" height="{max(height, 1):.1f}" rx="2.2" fill="{color}"/>')


def add_stacked_bars(
    parts: list[str],
    lower_points: list[Point],
    upper_points: list[Point],
    start: date,
    end: date,
    lo: float,
    hi: float,
    lower_color: str,
    upper_color: str,
    baseline: float = 0,
    width_factor: float = 0.72,
    max_width: float = 13,
) -> None:
    days = max((end - start).days + 1, 1)
    bar_w = max(1.5, min(max_width, (W - LEFT - RIGHT) / days * width_factor))
    base_y = y_for(baseline, lo, hi)
    lower_by_day = {p.day: p.value for p in lower_points}
    upper_by_day = {p.day: p.value for p in upper_points}
    all_days = sorted(set(lower_by_day) | set(upper_by_day))
    for day in all_days:
        lower_value = lower_by_day.get(day, 0.0)
        upper_value = upper_by_day.get(day, 0.0)
        x = x_for(day, start, end) - bar_w / 2
        if lower_value > baseline:
            lower_y = y_for(lower_value, lo, hi)
            lower_h = abs(base_y - lower_y)
            lower_top = min(base_y, lower_y)
            parts.append(f'<rect x="{x:.1f}" y="{lower_top:.1f}" width="{bar_w:.1f}" height="{max(lower_h, 1):.1f}" rx="2.2" fill="{lower_color}"/>')
        total_value = lower_value + upper_value
        if total_value > lower_value:
            upper_top_y = y_for(total_value, lo, hi)
            lower_top_y = y_for(lower_value, lo, hi)
            upper_h = abs(lower_top_y - upper_top_y)
            upper_top = min(lower_top_y, upper_top_y)
            parts.append(f'<rect x="{x:.1f}" y="{upper_top:.1f}" width="{bar_w:.1f}" height="{max(upper_h, 1):.1f}" rx="2.2" fill="{upper_color}"/>')


def add_legend(parts: list[str], items: list[tuple[str, str]], y: int = 32) -> None:
    x = W - 24
    for label, color in reversed(items):
        text_width = len(label) * 6.8
        icon_text_gap = 16
        label_gap = 40
        width = text_width + icon_text_gap + label_gap
        parts.append(f'<text x="{x}" y="{y}" text-anchor="end" fill="{COLORS["muted"]}" font-size="14" font-weight="650" font-family="Inter, system-ui, sans-serif">{esc(label)}</text>')
        parts.append(f'<circle cx="{x - text_width - icon_text_gap:.1f}" cy="{y - 4}" r="4.5" fill="{color}"/>')
        x -= width


def add_latest_label(parts: list[str], y: float, label: str, color: str, dy: float = 0) -> None:
    safe_y = min(max(y + dy, TOP + 18), H - BOTTOM - 8)
    parts.append(f'<text x="{W - ACTIVE_RIGHT + 14}" y="{safe_y:.1f}" fill="{color}" font-size="15" font-weight="800" font-family="Inter, system-ui, sans-serif">{esc(label)}</text>')


def add_band(parts: list[str], lower: list[Point], upper: list[Point], start: date, end: date, lo: float, hi: float, color: str, opacity: float = 0.7) -> None:
    lower_by_day = {p.day: p for p in lower}
    days = [p.day for p in upper if p.day in lower_by_day]
    if not days:
        return
    upper_points = [(x_for(p.day, start, end), y_for(p.value, lo, hi)) for p in upper if p.day in lower_by_day]
    lower_points = [(x_for(d, start, end), y_for(lower_by_day[d].value, lo, hi)) for d in reversed(days)]
    polygon = " ".join(f"{x:.1f},{y:.1f}" for x, y in upper_points + lower_points)
    parts.append(f'<polygon points="{polygon}" fill="{color}" opacity="{opacity}"/>')


def add_horizontal_zone(parts: list[str], lower_value: float, upper_value: float, lo: float, hi: float, color: str, label: str, opacity: float = 0.5) -> None:
    lower = max(min(lower_value, upper_value), lo)
    upper = min(max(lower_value, upper_value), hi)
    if upper <= lower:
        return
    y_upper = y_for(upper, lo, hi)
    y_lower = y_for(lower, lo, hi)
    parts.append(
        f'<rect x="{LEFT}" y="{y_upper:.1f}" width="{W - LEFT - ACTIVE_RIGHT}" '
        f'height="{max(y_lower - y_upper, 1):.1f}" fill="{color}" opacity="{opacity}"/>'
    )
    label_y = y_upper + 18
    parts.append(
        f'<text x="{LEFT + 12}" y="{label_y:.1f}" fill="{COLORS["muted"]}" font-size="12" '
        f'font-weight="650" font-family="Inter, system-ui, sans-serif">{esc(label)}</text>'
    )


def write_svg(path: Path, parts: list[str]) -> None:
    write_text_atomic(path, "\n".join(parts) + "\n" + svg_close() + "\n")


def render_single_line(path: Path, title: str, points: list[Point], start: date, end: date, color: str, unit: str = "", include_zero: bool = False) -> str | None:
    pts = window(points, start, end)
    lo, hi = domain([p.value for p in pts], include_zero=include_zero)
    parts = svg_open(title)
    add_grid(parts, start, end, lo, hi, left_label=f"{hi:.0f}{unit}")
    if pts:
        add_line(parts, pts, start, end, lo, hi, color)
    else:
        add_no_data(parts)
    write_svg(path, parts)
    return None if pts else f"{title}: keine Daten im Zeitraum."


def render_hrv(path: Path, newest: date) -> list[str]:
    global ACTIVE_RIGHT
    ACTIVE_RIGHT = RIGHT_COMPACT
    start = newest - timedelta(days=89)
    rows = read_table(DATA_DIR / "health" / "hrv.md")
    daily: list[Point] = []
    mean7: list[Point] = []
    lower: list[Point] = []
    upper: list[Point] = []
    for row in rows:
        day = parse_day(row.get("Datum", ""))
        if day is None or not start <= day <= newest:
            continue
        for col, target in [
            ("Tages-RMSSD / ms", daily),
            ("7-Tage-RMSSD / ms", mean7),
            ("90-Tage-RMSSD-Grenze unten / ms", lower),
            ("90-Tage-RMSSD-Grenze oben / ms", upper),
        ]:
            value = parse_float(row.get(col))
            if value is not None:
                target.append(Point(day, value, row.get(col, "")))
    values = [p.value for p in daily + mean7 + lower + upper]
    lo, hi = domain(values)
    parts = svg_open("HRV")
    add_grid(parts, start, newest, lo, hi, left_label=f"{hi:.0f}ms")
    add_band(parts, lower, upper, start, newest, lo, hi, COLORS["hrv_band"], opacity=0.85)
    add_line(parts, daily, start, newest, lo, hi, COLORS["hrv_daily"], width=1.1, draw_points=False)
    add_points(parts, daily, start, newest, lo, hi, COLORS["hrv_daily"], radius=2.4, opacity=0.7)
    lower_by_day = {p.day: p.value for p in lower}
    upper_by_day = {p.day: p.value for p in upper}
    colors_by_day = {
        p.day: COLORS["hrv_trend_good"]
        if p.day in lower_by_day and p.day in upper_by_day and lower_by_day[p.day] <= p.value <= upper_by_day[p.day]
        else COLORS["hrv_trend_bad"]
        for p in mean7
    }
    add_colored_line_by_day(parts, mean7, start, newest, lo, hi, colors_by_day, COLORS["hrv_trend_bad"], width=3.4)
    add_legend(parts, [("Tages-RMSSD", COLORS["hrv_daily"]), ("7-Tage im Korridor", COLORS["hrv_trend_good"]), ("7-Tage außerhalb", COLORS["hrv_trend_bad"]), ("Korridor", COLORS["hrv_band"])])
    write_svg(path, parts)
    return [] if daily else ["HRV: keine Daten im Zeitraum."]


def render_weight(path: Path, newest: date) -> list[str]:
    global ACTIVE_RIGHT
    ACTIVE_RIGHT = RIGHT_LABELS
    start = newest - timedelta(days=89)
    table = DATA_DIR / "health" / "weight.md"
    daily = window(points_from_table(table, "Gewicht / kg"), start, newest)
    trend = window(points_from_table(table, "7-Tage-Mittel-Gewicht / kg"), start, newest)
    bodyfat_daily = window(points_from_table(table, "Körperfettanteil / %"), start, newest)
    bodyfat_trend = window(points_from_table(table, "7-Tage-Mittel-Körperfettanteil / %"), start, newest)
    weight_lo, weight_hi = domain([p.value for p in daily + trend])
    bodyfat_lo, bodyfat_hi = domain([p.value for p in bodyfat_daily + bodyfat_trend])
    parts = svg_open("Gewicht")
    parts.extend([
        "<defs>",
        '  <linearGradient id="weightBarFade" x1="0" y1="0" x2="0" y2="1">',
        f'    <stop offset="0%" stop-color="{COLORS["weight"]}" stop-opacity="0.78"/>',
        f'    <stop offset="100%" stop-color="{COLORS["weight"]}" stop-opacity="0.18"/>',
        "  </linearGradient>",
        "</defs>",
    ])
    add_grid(parts, start, newest, weight_lo, weight_hi, show_y_labels=False)
    plot_top = TOP
    plot_bottom = H - BOTTOM
    plot_height = plot_bottom - plot_top
    weight_top = plot_top
    weight_bottom = plot_top + plot_height * 0.48
    fat_top = plot_top + plot_height * 0.50
    fat_bottom = plot_bottom
    parts.append(f'<text x="{LEFT - 12}" y="{TOP + 5}" text-anchor="end" fill="{COLORS["muted"]}" font-size="13" font-family="Inter, system-ui, sans-serif">{weight_hi:.1f}kg</text>')
    parts.append(f'<text x="{LEFT - 12}" y="{weight_bottom:.1f}" text-anchor="end" fill="{COLORS["muted"]}" font-size="13" font-family="Inter, system-ui, sans-serif">{weight_lo:.1f}kg</text>')
    parts.append(f'<text x="{LEFT - 12}" y="{fat_top + 5:.1f}" text-anchor="end" fill="{COLORS["muted"]}" font-size="13" font-family="Inter, system-ui, sans-serif">{bodyfat_hi:.1f}%</text>')
    parts.append(f'<text x="{LEFT - 12}" y="{fat_bottom:.1f}" text-anchor="end" fill="{COLORS["muted"]}" font-size="13" font-family="Inter, system-ui, sans-serif">{bodyfat_lo:.1f}%</text>')
    parts.append(f'<line x1="{LEFT}" y1="{fat_top:.1f}" x2="{W - ACTIVE_RIGHT}" y2="{fat_top:.1f}" stroke="{COLORS["grid"]}" stroke-width="1" stroke-dasharray="6 8"/>')

    def scaled_y(value: float, lo: float, hi: float, top: float, bottom: float) -> float:
        if math.isclose(lo, hi):
            return (top + bottom) / 2
        return bottom - ((value - lo) / (hi - lo)) * (bottom - top)

    def add_scaled_bars(points: list[Point], lo: float, hi: float, top: float, bottom: float, fill: str, baseline_y: float, opacity: float = 1.0, width_factor: float = 0.7, max_width: float = 10) -> None:
        days = max((newest - start).days + 1, 1)
        bar_w = max(1.2, min(max_width, (W - LEFT - RIGHT) / days * width_factor))
        for p in points:
            x = x_for(p.day, start, newest) - bar_w / 2
            y = scaled_y(p.value, lo, hi, top, bottom)
            height = abs(baseline_y - y)
            rect_top = min(baseline_y, y)
            parts.append(f'<rect x="{x:.1f}" y="{rect_top:.1f}" width="{bar_w:.1f}" height="{max(height, 1):.1f}" rx="1.8" fill="{fill}" opacity="{opacity}"/>')

    def add_scaled_line(points: list[Point], lo: float, hi: float, top: float, bottom: float, color: str, width: float = 3.0) -> None:
        if not points:
            return
        if len(points) == 1:
            x = x_for(points[0].day, start, newest)
            y = scaled_y(points[0].value, lo, hi, top, bottom)
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5.2" fill="{color}"/>')
            return
        coords = " ".join(f'{x_for(p.day, start, newest):.1f},{scaled_y(p.value, lo, hi, top, bottom):.1f}' for p in points)
        parts.append(f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>')
        for p in points:
            x = x_for(p.day, start, newest)
            y = scaled_y(p.value, lo, hi, top, bottom)
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.2" fill="{color}" stroke="{COLORS["paper"]}" stroke-width="1.6"/>')

    add_scaled_bars(daily, weight_lo, weight_hi, weight_top, weight_bottom, "url(#weightBarFade)", fat_bottom, opacity=1.0, width_factor=0.72, max_width=10)
    add_scaled_bars(bodyfat_daily, bodyfat_lo, bodyfat_hi, fat_top, fat_bottom, "#ff4f55", fat_bottom, opacity=0.82, width_factor=0.45, max_width=7)
    add_scaled_line(trend, weight_lo, weight_hi, weight_top, weight_bottom, COLORS["weight_trend"], width=4.2)
    add_scaled_line(bodyfat_trend, bodyfat_lo, bodyfat_hi, fat_top, fat_bottom, COLORS["body_fat_trend"], width=4.2)
    add_legend(parts, [("7-Tage-Mittel Gewicht", COLORS["weight_trend"]), ("7-Tage-Mittel Körperfett", COLORS["body_fat_trend"])])
    if trend:
        add_latest_label(parts, scaled_y(trend[-1].value, weight_lo, weight_hi, weight_top, weight_bottom), number_label(trend[-1].value, "kg", 2), COLORS["weight_trend"])
    if bodyfat_trend:
        add_latest_label(parts, scaled_y(bodyfat_trend[-1].value, bodyfat_lo, bodyfat_hi, fat_top, fat_bottom), number_label(bodyfat_trend[-1].value, "%", 2), COLORS["body_fat_trend"], dy=20)
    if not daily:
        add_no_data(parts)
    write_svg(path, parts)
    return [] if daily else ["Gewicht: keine Daten im Zeitraum."]


def render_steps(path: Path, newest: date) -> list[str]:
    global ACTIVE_RIGHT
    ACTIVE_RIGHT = RIGHT_COMPACT
    start = newest - timedelta(days=89)
    daily = window(points_from_table(DATA_DIR / "health" / "steps.md", "Schritte"), start, newest)
    trend = window(points_from_table(DATA_DIR / "health" / "steps.md", "7-Tage-Mittel-Schritte"), start, newest)
    _, hi = domain([p.value for p in daily + trend], include_zero=True)
    lo = 0
    parts = svg_open("Schritte")
    add_grid(parts, start, newest, lo, hi, left_label=f"{hi:.0f}")
    add_bars(parts, daily, start, newest, lo, hi, COLORS["steps"], baseline=0)
    add_line(parts, trend, start, newest, lo, hi, COLORS["ink"], width=3)
    add_legend(parts, [("Tageswert", COLORS["steps"]), ("7-Tage-Mittel", COLORS["ink"])])
    if not daily:
        add_no_data(parts)
    write_svg(path, parts)
    return [] if daily else ["Schritte: keine Daten im Zeitraum."]


def add_stacked_vertical_bars(
    parts: list[str],
    x_positions: list[float],
    stacks: list[list[tuple[float, str]]],
    lo: float,
    hi: float,
    bar_width: float,
    baseline: float = 0,
) -> None:
    base_y = y_for(baseline, lo, hi)
    for x, stack in zip(x_positions, stacks):
        cumulative = baseline
        for value_item, color in stack:
            if value_item <= 0:
                continue
            next_value = cumulative + value_item
            y_top = y_for(next_value, lo, hi)
            y_bottom = y_for(cumulative, lo, hi)
            parts.append(
                f'<rect x="{x - bar_width / 2:.1f}" y="{min(y_top, y_bottom):.1f}" width="{bar_width:.1f}" '
                f'height="{max(abs(y_bottom - y_top), 1):.1f}" rx="2.2" fill="{color}"/>'
            )
            cumulative = next_value


def zone_shades(base: str) -> dict[str, str]:
    palettes = {
        "swim": {"Z1": "#dfeaf7", "Z2": "#b9d3ef", "Z3": "#86b6e1", "Z4": "#4f90cb", "Z5": "#2f6fa3"},
        "bike": {"Z1": "#dcefe9", "Z2": "#b8dfd7", "Z3": "#83c5b8", "Z4": "#55a998", "Z5": "#287c71", "Z6": "#15564f"},
        "run": {"Z1": "#f6dfdb", "Z2": "#efc1b8", "Z3": "#e59c8f", "Z4": "#d97766", "Z5": "#b64b3a", "Z6": "#8e2f22"},
    }
    return palettes[base]


def add_week_x_labels(parts: list[str], weeks: list[str], start_x: float, plot_w: float, y: float) -> list[float]:
    if not weeks:
        return []
    step = plot_w / max(len(weeks), 1)
    positions = [start_x + step * (idx + 0.5) for idx in range(len(weeks))]
    for idx, (week, x) in enumerate(zip(weeks, positions)):
        parts.append(f'<line x1="{x:.1f}" y1="{TOP}" x2="{x:.1f}" y2="{H - BOTTOM}" stroke="{COLORS["grid"]}" stroke-width="1"/>')
        if idx % 2 == 0 or idx == len(weeks) - 1:
            parts.append(f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" fill="{COLORS["muted"]}" font-size="12" font-family="Inter, system-ui, sans-serif">{esc(week[-3:])}</text>')
    return positions


def render_weekly_duration(path: Path, current_week: str) -> list[str]:
    global ACTIVE_RIGHT
    ACTIVE_RIGHT = RIGHT_COMPACT
    history_week = previous_week(current_week)
    series = weekly_stats_series(history_week, 12)
    update_review_stats_blocks(series)
    weeks = [item.week for item in series]
    swim = [item.duration_s["swim"] / 3600 for item in series]
    bike = [item.duration_s["bike"] / 3600 for item in series]
    run = [item.duration_s["run"] / 3600 for item in series]
    totals = [a + b + c for a, b, c in zip(swim, bike, run)]
    lo, hi = 0, max(max(totals, default=0.0) * 1.15, 1.0)
    parts = svg_open("Wochenumfang")
    add_grid(parts, monday_of_week(weeks[0]), monday_of_week(weeks[-1]), lo, hi, left_label=f"{hi:.1f}h", show_y_labels=True, show_x_grid=False)
    positions = add_week_x_labels(parts, weeks, LEFT, W - LEFT - ACTIVE_RIGHT, H - 20)
    stacks = [
        [(swim[idx], COLORS["swim"]), (bike[idx], COLORS["bike"]), (run[idx], COLORS["run"])]
        for idx in range(len(weeks))
    ]
    add_stacked_vertical_bars(parts, positions, stacks, lo, hi, bar_width=max(10, (W - LEFT - ACTIVE_RIGHT) / max(len(weeks), 1) * 0.55))
    add_legend(parts, [("Swim", COLORS["swim"]), ("Bike", COLORS["bike"]), ("Run", COLORS["run"])])
    if not any(totals):
        add_no_data(parts)
    write_svg(path, parts)
    return [] if any(totals) else ["Wochenumfang: keine Daten im Zeitraum."]


def render_weekly_tss(path: Path, current_week: str) -> list[str]:
    global ACTIVE_RIGHT
    ACTIVE_RIGHT = RIGHT_COMPACT
    history_week = previous_week(current_week)
    series = weekly_stats_series(history_week, 12)
    weeks = [item.week for item in series]
    swim = [item.tss["swim"] for item in series]
    bike = [item.tss["bike"] for item in series]
    run = [item.tss["run"] for item in series]
    totals = [a + b + c for a, b, c in zip(swim, bike, run)]
    lo, hi = 0, max(max(totals, default=0.0) * 1.15, 50.0)
    parts = svg_open("Wochen-TSS")
    add_grid(parts, monday_of_week(weeks[0]), monday_of_week(weeks[-1]), lo, hi, left_label=f"{hi:.0f}", show_y_labels=True, show_x_grid=False)
    positions = add_week_x_labels(parts, weeks, LEFT, W - LEFT - ACTIVE_RIGHT, H - 20)
    stacks = [
        [(swim[idx], COLORS["swim"]), (bike[idx], COLORS["bike"]), (run[idx], COLORS["run"])]
        for idx in range(len(weeks))
    ]
    add_stacked_vertical_bars(parts, positions, stacks, lo, hi, bar_width=max(10, (W - LEFT - ACTIVE_RIGHT) / max(len(weeks), 1) * 0.55))
    add_legend(parts, [("Swim", COLORS["swim"]), ("Bike", COLORS["bike"]), ("Run", COLORS["run"])])
    if not any(totals):
        add_no_data(parts)
    write_svg(path, parts)
    return [] if any(totals) else ["Wochen-TSS: keine Daten im Zeitraum."]


def render_weekly_zones(path: Path, current_week: str) -> list[str]:
    previous = previous_week(current_week)
    stats = week_activity_stats(previous)
    width = 1600
    height = 540
    panel_gap = 36
    left = 54
    top = 76
    bottom = 58
    inner_w = (width - left * 2 - panel_gap * 2) / 3
    panel_titles = [("Swim nach Pace", "swim", "m"), ("Bike nach Power", "bike", "min"), ("Run nach GAP", "run", "min")]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="Zeit in Zonen der Vorwoche">',
        f'<rect x="0" y="0" width="{width}" height="{height}" rx="18" fill="{COLORS["paper"]}"/>',
        f'<text x="24" y="34" fill="{COLORS["ink"]}" font-size="24" font-weight="700" font-family="Inter, system-ui, sans-serif">Zeit in Zonen Vorwoche ({esc(previous)})</text>',
    ]
    has_data = False
    for panel_idx, (title, sport, unit) in enumerate(panel_titles):
        panel_x = left + panel_idx * (inner_w + panel_gap)
        panel_y = top
        panel_h = height - top - bottom
        parts.append(f'<rect x="{panel_x:.1f}" y="{panel_y:.1f}" width="{inner_w:.1f}" height="{panel_h:.1f}" rx="10" fill="{COLORS["plot"]}" stroke="{COLORS["grid"]}"/>')
        parts.append(f'<text x="{panel_x + 10:.1f}" y="{panel_y - 14:.1f}" fill="{COLORS["ink"]}" font-size="18" font-weight="700" font-family="Inter, system-ui, sans-serif">{title}</text>')
        zones = list(stats.zones[sport].keys())
        values = list(stats.zones[sport].values())
        total_value = sum(values)
        chart_values = [value_item / 60 if sport in {"bike", "run"} else value_item for value_item in values]
        has_data = has_data or any(chart_values)
        lo = 0
        hi = max(max(chart_values, default=0.0) * 1.18, 1.0)
        for i in range(5):
            y = panel_y + i * panel_h / 4
            parts.append(f'<line x1="{panel_x:.1f}" y1="{y:.1f}" x2="{panel_x + inner_w:.1f}" y2="{y:.1f}" stroke="{COLORS["grid"]}" stroke-width="1"/>')
        parts.append(f'<text x="{panel_x - 8:.1f}" y="{panel_y + 5:.1f}" text-anchor="end" fill="{COLORS["muted"]}" font-size="12" font-family="Inter, system-ui, sans-serif">{hi:.0f}{unit}</text>')
        parts.append(f'<text x="{panel_x - 8:.1f}" y="{panel_y + panel_h:.1f}" text-anchor="end" fill="{COLORS["muted"]}" font-size="12" font-family="Inter, system-ui, sans-serif">0</text>')
        shades = zone_shades(sport)
        bar_w = inner_w / max(len(zones), 1) * 0.55
        for idx, zone in enumerate(zones):
            x = panel_x + inner_w / len(zones) * (idx + 0.5)
            raw_value = values[idx]
            value_item = chart_values[idx]
            bar_h = 0 if hi <= 0 else (value_item / hi) * panel_h
            y = panel_y + panel_h - bar_h
            parts.append(f'<rect x="{x - bar_w / 2:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{max(bar_h, 1):.1f}" rx="3" fill="{shades.get(zone, COLORS["muted"])}"/>')
            if raw_value > 0:
                percent = raw_value / total_value * 100 if total_value > 0 else 0
                label_y = max(panel_y + 16, y - 18)
                parts.append(f'<text x="{x:.1f}" y="{label_y:.1f}" text-anchor="middle" fill="{COLORS["ink"]}" font-size="11" font-weight="700" font-family="Inter, system-ui, sans-serif">{esc(zone_amount_label(sport, raw_value))}</text>')
                parts.append(f'<text x="{x:.1f}" y="{label_y + 13:.1f}" text-anchor="middle" fill="{COLORS["muted"]}" font-size="10.5" font-weight="650" font-family="Inter, system-ui, sans-serif">{percent:.0f}%</text>')
            parts.append(f'<text x="{x:.1f}" y="{panel_y + panel_h + 22:.1f}" text-anchor="middle" fill="{COLORS["muted"]}" font-size="12" font-family="Inter, system-ui, sans-serif">{zone}</text>')
    if not has_data:
        parts.append(f'<text x="{width / 2:.1f}" y="{height / 2:.1f}" text-anchor="middle" fill="{COLORS["muted"]}" font-size="18" font-family="Inter, system-ui, sans-serif">Keine Zonendaten in der Vorwoche</text>')
    write_svg(path, parts)
    return [] if has_data else [f"Zonenverteilung: keine Daten für {previous}."]


def render_long_sessions(path: Path, current_week: str) -> list[str]:
    previous_canvas = set_canvas(width=560, height=590, left=58, right=70, top=74, bottom=54, active_right=RIGHT_LOAD)
    try:
        history_week = previous_week(current_week)
        series = weekly_stats_series(history_week, 12)
        weeks = [item.week for item in series]
        bike_values = [item.long_session_s["bike"] / 3600 for item in series]
        run_values = [item.long_session_s["run"] / 3600 for item in series]
        bike_hi = max(max(bike_values, default=0.0) * 1.15, 1.0)
        run_hi = max(max(run_values, default=0.0) * 1.15, 1.0)
        parts = svg_open("Long Sessions")
        add_grid(parts, monday_of_week(weeks[0]), monday_of_week(weeks[-1]), 0, bike_hi, left_label=f"{bike_hi:.1f}h", right_label=f"{run_hi:.1f}h", show_x_grid=False)
        positions = add_week_x_labels(parts, weeks, LEFT, W - LEFT - ACTIVE_RIGHT, H - 20)
        bike_points = [Point(monday_of_week(week), value_item) for week, value_item in zip(weeks, bike_values) if value_item > 0]
        run_points = [Point(monday_of_week(week), value_item) for week, value_item in zip(weeks, run_values) if value_item > 0]
        if bike_points:
            add_line(parts, bike_points, monday_of_week(weeks[0]), monday_of_week(weeks[-1]), 0, bike_hi, COLORS["bike"], width=3)
        if run_points:
            coords = " ".join(f'{x_for(p.day, monday_of_week(weeks[0]), monday_of_week(weeks[-1])):.1f},{y_for(p.value, 0, run_hi):.1f}' for p in run_points)
            parts.append(f'<polyline points="{coords}" fill="none" stroke="{COLORS["run"]}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>')
            for p in run_points:
                x = x_for(p.day, monday_of_week(weeks[0]), monday_of_week(weeks[-1]))
                y = y_for(p.value, 0, run_hi)
                parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.8" fill="{COLORS["run"]}" stroke="{COLORS["paper"]}" stroke-width="1.6"/>')
        add_legend(parts, [("Bike", COLORS["bike"]), ("Run", COLORS["run"])])
        if bike_points:
            add_latest_label(parts, y_for(bike_points[-1].value, 0, bike_hi), hours_label_from_seconds(bike_points[-1].value * 3600), COLORS["bike"])
        if run_points:
            add_latest_label(parts, y_for(run_points[-1].value, 0, run_hi), hours_label_from_seconds(run_points[-1].value * 3600), COLORS["run"], dy=18)
        if not bike_points and not run_points:
            add_no_data(parts)
        write_svg(path, parts)
        return [] if bike_points or run_points else ["Long Sessions: keine Daten im Zeitraum."]
    finally:
        restore_canvas(previous_canvas)


def render_readiness_sleep(path: Path, newest: date) -> list[str]:
    global ACTIVE_RIGHT
    ACTIVE_RIGHT = RIGHT_COMPACT
    start = newest - timedelta(days=89)
    duration = window(points_from_table(DATA_DIR / "health" / "sleep.md", "Schlafdauer / hh:mm", parse_hhmm), start, newest)
    score = window(points_from_table(DATA_DIR / "health" / "sleep.md", "Sleepscore"), start, newest)
    rhr = window(points_from_table(DATA_DIR / "health" / "resting_heart_rate.md", "Ruhepuls / bpm"), start, newest)
    _, sleep_hi = domain([p.value for p in duration], include_zero=True)
    sleep_lo = 0
    score_lo, score_hi = 0, 100
    rhr_values = [p.value for p in rhr]
    if rhr_values:
        rhr_min = min(rhr_values)
        rhr_max = max(rhr_values)
        pad = max((rhr_max - rhr_min) * 0.2, 1)
        rhr_lo = rhr_min - pad
        rhr_hi = rhr_lo + 3.3 * (rhr_max - rhr_lo)
    else:
        rhr_lo, rhr_hi = 0, 1
    parts = svg_open("Schlaf + Ruhepuls")
    parts.append(
        f'<defs><linearGradient id="sleep-duration-gradient" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{COLORS["sleep"]}" stop-opacity="0.95"/>'
        f'<stop offset="100%" stop-color="{COLORS["sleep"]}" stop-opacity="0.2"/>'
        f'</linearGradient></defs>'
    )
    add_grid(parts, start, newest, sleep_lo, sleep_hi, left_label=f"{sleep_hi:.1f}h", right_label="100Score")
    add_bars(parts, duration, start, newest, sleep_lo, sleep_hi, "url(#sleep-duration-gradient)", baseline=0)
    add_line(parts, score, start, newest, score_lo, score_hi, COLORS["sleep_score"], width=3)
    add_line(parts, rhr, start, newest, rhr_lo, rhr_hi, COLORS["rhr"], width=3)
    add_legend(parts, [("Schlafdauer", COLORS["sleep"]), ("Sleepscore", COLORS["sleep_score"]), ("Ruhepuls", COLORS["rhr"])])
    if not duration and not score and not rhr:
        add_no_data(parts)
    write_svg(path, parts)
    return [] if duration or score or rhr else ["Schlaf/Ruhepuls: keine Daten im Zeitraum."]


def render_loads(out_dir: Path, newest: date) -> list[str]:
    global ACTIVE_RIGHT
    ACTIVE_RIGHT = RIGHT_LOAD
    start = newest - timedelta(days=89)
    table = DATA_DIR / "health" / "loads.md"
    tss = window(points_from_table(table, "Tages-TSS"), start, newest)
    atl = window(points_from_table(table, "ATL"), start, newest)
    ctl = window(points_from_table(table, "CTL"), start, newest)
    ctl_lower = [Point(p.day, p.value * 0.8) for p in ctl]
    ctl_upper = [Point(p.day, p.value * 1.4) for p in ctl]
    _, hi = domain([p.value for p in tss + atl + ctl + ctl_lower + ctl_upper], include_zero=True)
    lo = 0
    parts = svg_open("Load")
    add_grid(parts, start, newest, lo, hi, left_label=f"{hi:.0f}")
    add_band(parts, ctl_lower, ctl_upper, start, newest, lo, hi, COLORS["load_band"], opacity=0.75)
    add_bars(parts, tss, start, newest, lo, hi, COLORS["tss"], baseline=0, width_factor=0.18, max_width=3)
    add_line(parts, atl, start, newest, lo, hi, COLORS["atl"], width=3)
    add_line(parts, ctl, start, newest, lo, hi, COLORS["ctl"], width=3)
    add_legend(parts, [("TSS", COLORS["tss"]), ("ATL", COLORS["atl"]), ("CTL", COLORS["ctl"]), ("80-140%CTL", COLORS["load_band"])])
    if atl:
        add_latest_label(parts, y_for(atl[-1].value, lo, hi), number_label(atl[-1].value), COLORS["atl"])
    if ctl:
        add_latest_label(parts, y_for(ctl[-1].value, lo, hi), number_label(ctl[-1].value), COLORS["ctl"], dy=20)
    if not tss and not atl and not ctl:
        add_no_data(parts)
    write_svg(out_dir / "load_atl_ctl.svg", parts)

    tsb = window(points_from_table(table, "TSB"), start, newest)
    tsb_plot = [Point(p.day, -p.value, p.label) for p in tsb]
    tsb_zone_values = [-35, -25, -10, 10, 25, 30, 35]
    tsb_lo, tsb_hi = domain([p.value for p in tsb_plot] + tsb_zone_values, include_zero=True)
    parts = svg_open("Balance")
    add_grid(parts, start, newest, tsb_lo, tsb_hi, left_label=f"{tsb_hi:.0f}TSB")
    add_horizontal_zone(parts, 30, tsb_hi, tsb_lo, tsb_hi, "#f7d9d6", "Risiko < -30", opacity=0.42)
    add_horizontal_zone(parts, 10, 30, tsb_lo, tsb_hi, "#dcefe9", "Formaufbau -10 bis -30", opacity=0.7)
    add_horizontal_zone(parts, -10, 10, tsb_lo, tsb_hi, "#dfe4ea", "neutral -10 bis +10", opacity=0.82)
    add_horizontal_zone(parts, -25, -10, tsb_lo, tsb_hi, "#f5f6f8", "Race Ready +10 bis +25", opacity=0.82)
    add_horizontal_zone(parts, tsb_lo, -25, tsb_lo, tsb_hi, "#f7e3cf", "Fitnessverlust > +25", opacity=0.5)
    zero_y = y_for(0, tsb_lo, tsb_hi)
    parts.append(f'<line x1="{LEFT}" y1="{zero_y:.1f}" x2="{W - ACTIVE_RIGHT}" y2="{zero_y:.1f}" stroke="{COLORS["axis"]}" stroke-width="1.4"/>')
    add_line(parts, tsb_plot, start, newest, tsb_lo, tsb_hi, COLORS["ink"], width=3)
    add_legend(parts, [("TSB invertiert", COLORS["ink"])])
    if tsb:
        add_latest_label(parts, y_for(-tsb[-1].value, tsb_lo, tsb_hi), number_label(tsb[-1].value), COLORS["ink"])
    if not tsb:
        add_no_data(parts)
    write_svg(out_dir / "load_tsb.svg", parts)
    warnings: list[str] = []
    if not tss and not atl and not ctl:
        warnings.append("Load: keine Daten im Zeitraum.")
    return warnings


def render_thresholds(path: Path, newest: date) -> list[str]:
    global ACTIVE_RIGHT
    ACTIVE_RIGHT = RIGHT_LABELS
    start = newest - timedelta(days=364)
    series = [
        ("Swim CSS", COLORS["swim"], window(points_from_table(DATA_DIR / "thresholds" / "thresholds_swim.md", "CSS / min:sec/100m", parse_pace_seconds), start, newest), True, "/100m"),
        ("Bike FTP", COLORS["bike"], window(points_from_table(DATA_DIR / "thresholds" / "thresholds_bike.md", "FTP / W"), start, newest), False, "W"),
        ("Run LT", COLORS["run_pace"], window(points_from_table(DATA_DIR / "thresholds" / "thresholds_run.md", "LT / min:sec/km", parse_pace_seconds), start, newest), True, "/km"),
    ]
    parts = svg_open("Thresholds")
    add_grid(parts, start, newest, 0, 1, show_y_labels=False)
    add_legend(parts, [(name, color) for name, color, *_ in series])
    warnings: list[str] = []
    used_any = False
    for index, (name, color, pts, invert, unit) in enumerate(series):
        if not pts:
            warnings.append(f"{name}: keine Daten im 12-Monats-Zeitraum.")
            continue
        used_any = True
        plot_pts = [Point(p.day, -p.value if invert else p.value, p.label) for p in pts]
        lo, hi = domain([p.value for p in plot_pts])
        add_line(parts, plot_pts, start, newest, lo, hi, color, width=3)
        latest = pts[-1]
        ly = y_for(-latest.value if invert else latest.value, lo, hi)
        if invert:
            value_label = f"{pace_label(latest.value)}{unit}"
        else:
            value_label = number_label(latest.value, unit)
        add_latest_label(parts, ly, value_label, color, dy=index * 18)
    if not used_any:
        add_no_data(parts)
    write_svg(path, parts)
    return warnings


def render_vo2(path: Path, newest: date) -> list[str]:
    global ACTIVE_RIGHT
    ACTIVE_RIGHT = RIGHT_LABELS
    start = newest - timedelta(days=364)
    vo2_cols = ["VO2max / ml/kg/min", "VO2max / ml/min/kg"]
    bike = window(points_from_first_available(DATA_DIR / "VO2max" / "VO2max_bike.md", vo2_cols), start, newest)
    run = window(points_from_first_available(DATA_DIR / "VO2max" / "VO2max_run.md", vo2_cols), start, newest)
    lo, hi = domain([p.value for p in bike + run])
    parts = svg_open("VO2max")
    add_grid(parts, start, newest, lo, hi, left_label=f"{hi:.1f}")
    add_line(parts, bike, start, newest, lo, hi, COLORS["bike"], width=3)
    add_line(parts, run, start, newest, lo, hi, COLORS["vo2_run"], width=3)
    add_legend(parts, [("Bike", COLORS["bike"]), ("Run", COLORS["vo2_run"])])
    if bike:
        add_latest_label(parts, y_for(bike[-1].value, lo, hi), number_label(bike[-1].value, "", 1), COLORS["bike"])
    if run:
        add_latest_label(parts, y_for(run[-1].value, lo, hi), number_label(run[-1].value, "", 1), COLORS["vo2_run"], dy=20)
    if not bike and not run:
        add_no_data(parts)
    write_svg(path, parts)
    return [] if bike or run else ["VO2max: keine Daten im Zeitraum."]


def generate(week: str, newest: date) -> list[str]:
    out_dir = TREND_DIR / week
    out_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []

    for stale_name in ["readiness_resting_hr.svg", "readiness_sleep.svg", "load_tsb_acr.svg"]:
        stale_plot = out_dir / stale_name
        if stale_plot.exists():
            stale_plot.unlink()

    warnings += render_hrv(out_dir / "readiness_hrv.svg", newest)
    warnings += render_readiness_sleep(out_dir / "readiness_sleep_resting_hr.svg", newest)
    warnings += render_weight(out_dir / "body_weight.svg", newest)
    warnings += render_steps(out_dir / "body_steps.svg", newest)
    warnings += render_weekly_duration(out_dir / "weekly_duration.svg", week)
    warnings += render_weekly_tss(out_dir / "weekly_tss.svg", week)
    warnings += render_weekly_zones(out_dir / "weekly_zones.svg", week)
    warnings += render_long_sessions(out_dir / "weekly_long_sessions.svg", week)
    warnings += render_loads(out_dir, newest)
    warnings += render_thresholds(out_dir / "performance_thresholds.svg", newest)
    warnings += render_vo2(out_dir / "performance_vo2max.svg", newest)

    return warnings


def trend_section_html(week: str) -> str:
    base = f"assets/{week}"
    return f"""    <section class="trends" aria-label="Zeitreihen">
      <h2>Trends</h2>

      <div class="trend-board trend-board-top">
        <div class="trend-group">
          <h3>Performance (12 Monate)</h3>
          <div class="trend-grid stack">
            <img src="{base}/performance_thresholds.svg" alt="Swim-, Bike- und Run-Thresholds der letzten 12Monate">
            <img src="{base}/performance_vo2max.svg" alt="Bike- und Run-VO2max der letzten 12Monate">
          </div>
        </div>

        <div class="trend-group">
          <h3>Belastung (90 Tage)</h3>
          <div class="trend-grid stack">
            <img src="{base}/load_atl_ctl.svg" alt="Tages-TSS, ATL und CTL der letzten 90Tage">
            <img src="{base}/load_tsb.svg" alt="TSB der letzten 90Tage">
          </div>
        </div>
      </div>

      <div class="trend-middle">
        <div class="trend-middle-top">
          <img src="{base}/weekly_duration.svg" alt="Wochenumfang pro Sportart der letzten 12 Wochen">
          <img src="{base}/weekly_tss.svg" alt="Wochen-TSS pro Sportart der letzten 12 Wochen">
        </div>
        <div class="trend-middle-bottom">
          <img class="trend-wide" src="{base}/weekly_zones.svg" alt="Zeit und Distanz in Zonen der letzten abgeschlossenen Woche">
          <img class="trend-narrow" src="{base}/weekly_long_sessions.svg" alt="Längste Bike- und Run-Session pro Woche der letzten 12 Wochen">
        </div>
      </div>

      <div class="trend-board trend-board-bottom">
        <div class="trend-group">
          <h3>Readiness (90 Tage)</h3>
          <div class="trend-grid stack">
            <img src="{base}/readiness_hrv.svg" alt="HRV mit Tageswert, 7-Tage-Trend und 90-Tage-Korridor">
            <img src="{base}/readiness_sleep_resting_hr.svg" alt="Schlafdauer, Sleepscore und Ruhepuls der letzten 90Tage">
          </div>
        </div>

        <div class="trend-group">
          <h3>Alltag (90 Tage)</h3>
          <div class="trend-grid stack">
            <img src="{base}/body_weight.svg" alt="Gewicht und Körperfett mit Tageswerten und 7-Tage-Mitteln der letzten 90Tage">
            <img src="{base}/body_steps.svg" alt="Schritte mit Tageswerten und 7-Tage-Mittel der letzten 90Tage">
          </div>
        </div>
      </div>
    </section>"""


def update_plan_html(week: str, html_path: Path) -> None:
    if not html_path.exists():
        raise FileNotFoundError(f"Plan HTML not found: {html_path}")
    content = html_path.read_text(encoding="utf-8")
    section = trend_section_html(week)
    pattern = re.compile(r"\n\s*<section class=\"trends\"[\s\S]*?</section>\s*(?=\n\s*</main>)", re.MULTILINE)
    if pattern.search(content):
        content = pattern.sub("\n\n" + section, content)
    else:
        marker = "\n  </main>"
        if marker not in content:
            raise ValueError(f"Could not find </main> marker in {html_path}")
        content = content.replace(marker, "\n\n" + section + marker, 1)
    write_text_atomic(html_path, content)


def resolve_plan_html_path(value: str | None, week: str) -> Path:
    requested = Path(value) if value else PLAN_DIR / f"{week}.html"
    if requested.is_absolute():
        resolved = requested.resolve()
    elif len(requested.parts) == 1:
        resolved = (PLAN_DIR / requested).resolve()
    else:
        resolved = (ROOT / requested).resolve()
    plans_root = PLAN_DIR.resolve()
    if not resolved.is_relative_to(plans_root):
        raise ValueError(
            f"Plan HTML must belong to the active profile and be below {plans_root}: {resolved}"
        )
    if resolved.suffix.lower() != ".html":
        raise ValueError(f"Plan must be an HTML file: {resolved}")
    return resolved


def infer_week(newest: date) -> str:
    year, week, _ = newest.isocalendar()
    return f"{year}-W{week:02d}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate SVG trend plots for a weekly training plan.")
    parser.add_argument("--week", help="ISO week target, e.g. 2026-W24. Defaults to week of --newest.")
    parser.add_argument("--newest", help="Last date for plots, YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--update-html", action="store_true", help="Insert or replace the trend section in the weekly plan HTML.")
    parser.add_argument(
        "--plan-html",
        help="Plan HTML path. Defaults to the active profile's plans/<week>.html.",
    )
    args = parser.parse_args()

    newest = parse_day(args.newest) if args.newest else date.today()
    if newest is None:
        raise SystemExit("--newest must use YYYY-MM-DD")
    week = args.week or infer_week(newest)
    warnings = generate(week, newest)

    print(f"Generated trend plots: {TREND_DIR / week}")
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")
    if args.update_html:
        try:
            html_path = resolve_plan_html_path(args.plan_html, week)
            update_plan_html(week, html_path)
        except (FileNotFoundError, ValueError) as exc:
            parser.error(str(exc))
        print(f"Updated plan HTML: {html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
