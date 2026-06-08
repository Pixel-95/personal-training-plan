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


ROOT = Path(__file__).resolve().parents[1]
PLAN_DIR = ROOT / "plans"
TREND_DIR = PLAN_DIR / "assets" / "trends"

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


@dataclass(frozen=True)
class Point:
    day: date
    value: float
    label: str = ""


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def read_table(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    lines = [
        line.strip()
        for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        if line.strip().startswith("|")
    ]
    if len(lines) < 2:
        return []
    header = [cell.strip() for cell in lines[0].strip("|").split("|")]
    rows: list[dict[str, str]] = []
    for line in lines[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != len(header):
            continue
        row = dict(zip(header, cells))
        if row.get("Datum"):
            rows.append(row)
    return rows


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


def window(points: list[Point], start: date, end: date) -> list[Point]:
    return [p for p in points if start <= p.day <= end]


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
) -> None:
    for i in range(5):
        y = TOP + i * (H - TOP - BOTTOM) / 4
        parts.append(f'<line x1="{LEFT}" y1="{y:.1f}" x2="{W - ACTIVE_RIGHT}" y2="{y:.1f}" stroke="{COLORS["grid"]}" stroke-width="1"/>')
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts) + "\n" + svg_close(), encoding="utf-8")


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
    rows = read_table(ROOT / "data" / "health" / "hrv.md")
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
    ACTIVE_RIGHT = RIGHT_COMPACT
    start = newest - timedelta(days=29)
    daily = window(points_from_table(ROOT / "data" / "health" / "weight.md", "Gewicht / kg"), start, newest)
    trend = window(points_from_table(ROOT / "data" / "health" / "weight.md", "7-Tage-Mittel-Gewicht / kg"), start, newest)
    lo, hi = domain([p.value for p in daily + trend])
    parts = svg_open("Gewicht")
    add_grid(parts, start, newest, lo, hi, left_label=f"{hi:.1f}kg")
    add_bars(parts, daily, start, newest, lo, hi, COLORS["weight"], baseline=lo)
    add_line(parts, trend, start, newest, lo, hi, COLORS["weight_trend"], width=3)
    add_legend(parts, [("Tageswert", COLORS["weight"]), ("7-Tage-Mittel", COLORS["weight_trend"])])
    if not daily:
        add_no_data(parts)
    write_svg(path, parts)
    return [] if daily else ["Gewicht: keine Daten im Zeitraum."]


def render_steps(path: Path, newest: date) -> list[str]:
    global ACTIVE_RIGHT
    ACTIVE_RIGHT = RIGHT_COMPACT
    start = newest - timedelta(days=29)
    daily = window(points_from_table(ROOT / "data" / "health" / "steps.md", "Schritte"), start, newest)
    trend = window(points_from_table(ROOT / "data" / "health" / "steps.md", "7-Tage-Mittel-Schritte"), start, newest)
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


def render_readiness_sleep(path: Path, newest: date) -> list[str]:
    global ACTIVE_RIGHT
    ACTIVE_RIGHT = RIGHT_COMPACT
    start = newest - timedelta(days=89)
    duration = window(points_from_table(ROOT / "data" / "health" / "sleep.md", "Schlafdauer / hh:mm", parse_hhmm), start, newest)
    score = window(points_from_table(ROOT / "data" / "health" / "sleep.md", "Sleepscore"), start, newest)
    rhr = window(points_from_table(ROOT / "data" / "health" / "resting_heart_rate.md", "Ruhepuls / bpm"), start, newest)
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
    table = ROOT / "data" / "health" / "loads.md"
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
        ("Swim CSS", COLORS["swim"], window(points_from_table(ROOT / "data" / "thresholds" / "thresholds_swim.md", "CSS / min:sec/100m", parse_pace_seconds), start, newest), True, "/100m"),
        ("Bike FTP", COLORS["bike"], window(points_from_table(ROOT / "data" / "thresholds" / "thresholds_bike.md", "FTP / W"), start, newest), False, "W"),
        ("Run Pace", COLORS["run_pace"], window(points_from_table(ROOT / "data" / "thresholds" / "thresholds_run.md", "LT / min:sec/km", parse_pace_seconds), start, newest), True, "/km"),
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
    bike = window(points_from_first_available(ROOT / "data" / "VO2max" / "VO2max_bike.md", vo2_cols), start, newest)
    run = window(points_from_first_available(ROOT / "data" / "VO2max" / "VO2max_run.md", vo2_cols), start, newest)
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
    warnings += render_loads(out_dir, newest)
    warnings += render_thresholds(out_dir / "performance_thresholds.svg", newest)
    warnings += render_vo2(out_dir / "performance_vo2max.svg", newest)

    return warnings


def trend_section_html(week: str) -> str:
    base = f"assets/trends/{week}"
    return f"""    <section class="trends" aria-label="Zeitreihen">
      <h2>Trends</h2>

      <div class="trend-board">
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

        <div class="trend-group">
          <h3>Readiness (90 Tage)</h3>
          <div class="trend-grid stack">
            <img src="{base}/readiness_hrv.svg" alt="HRV mit Tageswert, 7-Tage-Trend und 90-Tage-Korridor">
            <img src="{base}/readiness_sleep_resting_hr.svg" alt="Schlafdauer, Sleepscore und Ruhepuls der letzten 90Tage">
          </div>
        </div>

        <div class="trend-group">
          <h3>Alltag (30 Tage)</h3>
          <div class="trend-grid stack">
            <img src="{base}/body_weight.svg" alt="Gewicht mit Tageswerten und 7-Tage-Mittel der letzten 30Tage">
            <img src="{base}/body_steps.svg" alt="Schritte mit Tageswerten und 7-Tage-Mittel der letzten 30Tage">
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
    html_path.write_text(content, encoding="utf-8")


def infer_week(newest: date) -> str:
    year, week, _ = newest.isocalendar()
    return f"{year}-W{week:02d}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate SVG trend plots for a weekly training plan.")
    parser.add_argument("--week", help="ISO week target, e.g. 2026-W24. Defaults to week of --newest.")
    parser.add_argument("--newest", help="Last date for plots, YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--update-html", action="store_true", help="Insert or replace the trend section in the weekly plan HTML.")
    parser.add_argument("--plan-html", help="Plan HTML path. Defaults to plans/<week>.html when --update-html is used.")
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
        html_path = Path(args.plan_html) if args.plan_html else PLAN_DIR / f"{week}.html"
        if not html_path.is_absolute():
            html_path = ROOT / html_path
        update_plan_html(week, html_path)
        print(f"Updated plan HTML: {html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
