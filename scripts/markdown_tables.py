"""Read and write the simple Markdown tables used by training histories."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Sequence


def parse_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def read_table(path: Path) -> tuple[list[str], list[list[str]]]:
    """Read one pipe table and reject malformed data rows."""
    if not path.exists():
        return [], []
    lines = [
        line.strip()
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip().startswith("|")
    ]
    if len(lines) < 2:
        return [], []
    header = parse_row(lines[0])
    rows: list[list[str]] = []
    for line_number, line in enumerate(lines[2:], start=3):
        cells = parse_row(line)
        if len(cells) != len(header):
            raise ValueError(
                f"Malformed Markdown table row in {path} at line {line_number}: "
                f"expected {len(header)} cells, got {len(cells)}"
            )
        rows.append(cells)
    return header, rows


def rows_by_key(rows: Iterable[list[str]], key_index: int = 0) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for row in rows:
        if len(row) > key_index and row[key_index]:
            result[row[key_index]] = row
    return result


def rows_as_dicts(header: Sequence[str], rows: Iterable[Sequence[str]]) -> list[dict[str, str]]:
    return [dict(zip(header, row)) for row in rows]


def render_table(header: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    lines = [
        "| " + " | ".join(str(cell) for cell in header) + " |",
        "|" + "|".join("-" for _ in header) + "|",
    ]
    for row in rows:
        cells = [str(cell) for cell in row]
        if len(cells) != len(header):
            raise ValueError(f"Expected {len(header)} cells, got {len(cells)}")
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def write_text_atomic(path: Path, text: str) -> None:
    """Replace a UTF-8 text file without exposing a partially written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(text, encoding="utf-8", newline="\n")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def write_bytes_atomic(path: Path, data: bytes) -> None:
    """Replace a binary file without exposing a partially written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_bytes(data)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
