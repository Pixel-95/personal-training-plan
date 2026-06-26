"""Shared date range helpers for repository scripts."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Iterator


def inclusive_dates(oldest: date, newest: date) -> Iterator[date]:
    """Yield every date in an inclusive range."""
    if newest < oldest:
        raise ValueError(f"newest date {newest} is before oldest date {oldest}")
    current = oldest
    while current <= newest:
        yield current
        current += timedelta(days=1)


def date_range_from_days(days: int, newest: str | None = None) -> tuple[date, date]:
    """Return an inclusive date range ending at newest or today."""
    if days < 1:
        raise ValueError("days must be at least 1")
    newest_date = date.today() if newest is None else date.fromisoformat(newest)
    return newest_date - timedelta(days=days - 1), newest_date


def expand_range_with_overlap(
    oldest: date,
    newest: date,
    overlap_day: date | None,
) -> tuple[date, date]:
    """Expand a range so the latest already synced day is fetched again."""
    if overlap_day is None or overlap_day > newest:
        return oldest, newest
    return min(oldest, overlap_day), newest


def iso_week_id(day: date) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def monday_of_iso_week(week: str) -> date:
    try:
        year_text, week_text = week.split("-W", 1)
        return date.fromisocalendar(int(year_text), int(week_text), 1)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid ISO week: {week}") from exc


def previous_iso_week(week: str) -> str:
    return iso_week_id(monday_of_iso_week(week) - timedelta(days=7))
