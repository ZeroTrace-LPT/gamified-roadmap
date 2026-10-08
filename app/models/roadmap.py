"""Data models shared by the importer, services, and UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RoadmapItem:
    """A normalized view of one source roadmap record."""

    item_id: str
    source_sheet: str
    source_row: int
    item_type: str
    name: str
    description: str = ""
    category: str = ""
    phase: str = ""
    target_period: str = ""
    status: str = ""
    priority: str = ""
    xp_reward: int | None = None
    xp_earned: int | None = None
    prerequisite_notes: str = ""
    resources: tuple[str, ...] = field(default_factory=tuple)
    notes: str = ""
    source_record: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ImportIssue:
    """A validation finding tied to source data where possible."""

    severity: str
    code: str
    message: str
    sheet: str = ""
    cell: str = ""


@dataclass(frozen=True)
class ImportResult:
    """Summary of a workbook import transaction."""

    workbook_id: str
    filename: str
    sheet_count: int
    source_row_count: int
    source_cell_count: int
    formula_count: int
    item_count: int
    issues: tuple[ImportIssue, ...]
    already_imported: bool = False
