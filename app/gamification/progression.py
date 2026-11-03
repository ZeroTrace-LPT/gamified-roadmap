"""Pure level parsing and XP progression calculations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class LevelDefinition:
    """One level row parsed from the workbook's Dashboard level table."""

    level: int
    xp_min: int
    xp_band: str
    title: str
    unlock: str
    reward: str


def _threshold(unlock: str, xp_band: str) -> int | None:
    match = re.search(r"([\d,]+)\s*XP\b", unlock, re.IGNORECASE)
    if match:
        return int(match.group(1).replace(",", ""))
    if unlock.strip().casefold() == "start":
        return 0
    match = re.search(r"([\d,]+)", xp_band)
    return int(match.group(1).replace(",", "")) if match else None


def parse_level_definitions(cells: Mapping[str, Any]) -> tuple[LevelDefinition, ...]:
    """Parse the source-defined level table from Dashboard cell coordinates.

    ``cells`` maps coordinates such as ``A14`` or ``D15`` to decoded source
    values. Rows are discovered from their headers instead of fixed positions.
    """
    by_row: dict[int, dict[str, Any]] = {}
    for coordinate, value in cells.items():
        match = re.fullmatch(r"([A-Z]+)(\d+)", coordinate.upper())
        if match:
            by_row.setdefault(int(match.group(2)), {})[match.group(1)] = value

    header_row = None
    for row_number, values in by_row.items():
        labels = [str(values.get(column, "")).strip().casefold() for column in "ABCDE"]
        if labels == ["level", "xp band", "title", "unlock", "reward"]:
            header_row = row_number
            break
    if header_row is None:
        return ()

    levels: list[LevelDefinition] = []
    for row_number in sorted(number for number in by_row if number > header_row):
        values = by_row[row_number]
        raw_level = values.get("A")
        title = str(values.get("C") or "").strip()
        if isinstance(raw_level, bool) or not isinstance(raw_level, (int, float)) or not title:
            continue
        level_number = int(raw_level)
        if level_number < 1 or float(raw_level) != level_number:
            continue
        xp_band = str(values.get("B") or "").strip()
        unlock = str(values.get("D") or "").strip()
        reward = str(values.get("E") or "").strip()
        minimum = _threshold(unlock, xp_band)
        if minimum is None:
            continue
        levels.append(LevelDefinition(level_number, minimum, xp_band, title, unlock, reward))

    unique = {definition.level: definition for definition in levels}
    return tuple(sorted(unique.values(), key=lambda definition: definition.level))


def calculate_progression(total_xp: int, levels: tuple[LevelDefinition, ...]) -> dict[str, Any]:
    """Calculate current level and next-level progress from source thresholds."""
    if not levels:
        return {
            "level_system_available": False,
            "current_level": None,
            "level_title": "",
            "level_band": "",
            "level_progress_percent": 0,
            "xp_to_next_level": None,
            "next_level": None,
            "next_level_title": "",
            "next_level_unlock": "",
            "next_level_reward": "",
            "is_max_level": False,
        }

    xp = max(0, int(total_xp))
    ordered = tuple(sorted(levels, key=lambda definition: definition.xp_min))
    current_index = 0
    for index, definition in enumerate(ordered):
        if xp >= definition.xp_min:
            current_index = index
        else:
            break
    current = ordered[current_index]
    next_level = ordered[current_index + 1] if current_index + 1 < len(ordered) else None
    if next_level is None:
        percent = 100
        xp_to_next = 0
    else:
        span = max(1, next_level.xp_min - current.xp_min)
        percent = round(min(max((xp - current.xp_min) / span * 100, 0), 100))
        xp_to_next = max(0, next_level.xp_min - xp)

    return {
        "level_system_available": True,
        "current_level": current.level,
        "level_title": current.title,
        "level_band": current.xp_band,
        "level_progress_percent": percent,
        "xp_to_next_level": xp_to_next,
        "next_level": next_level.level if next_level else None,
        "next_level_title": next_level.title if next_level else "",
        "next_level_unlock": next_level.unlock if next_level else "",
        "next_level_reward": next_level.reward if next_level else "",
        "is_max_level": next_level is None,
    }
