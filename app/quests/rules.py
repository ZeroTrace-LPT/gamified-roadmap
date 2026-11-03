"""Source-preserving rules for presenting roadmap records as quests."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping


QUEST_FILTERS = (
    "All quest types",
    "Main Quest",
    "Side Quest",
    "Certification Quest",
    "Lab Quest",
    "Project Quest",
    "Boss Quest",
)


@dataclass(frozen=True)
class QuestClassification:
    """Quest presentation metadata derived from an imported source record."""

    quest_type: str
    is_boss: bool
    boss_reason: str
    tags: tuple[str, ...]


def classify_quest(item: Mapping[str, Any]) -> QuestClassification:
    """Assign a quest class without creating or changing roadmap objectives.

    Boss status requires a source ``Major milestone`` priority or an explicit
    capstone, final exercise, or purple-team exercise title. Lab tags come from
    explicit lab wording in the workbook record.
    """
    item_type = str(item.get("item_type") or "").strip().casefold()
    text = " ".join(
        str(item.get(field) or "")
        for field in ("name", "description", "category", "phase")
    )
    title = str(item.get("name") or "").strip().casefold()
    priority = str(item.get("priority") or "").strip().casefold()

    if item_type == "monthly_mission":
        quest_type = "Main Quest"
    elif item_type == "certification":
        quest_type = "Certification Quest"
    elif item_type == "project":
        quest_type = "Project Quest"
    elif item_type == "learning_objective" and _has_lab_term(text):
        quest_type = "Lab Quest"
    else:
        quest_type = "Side Quest"

    boss_reason = ""
    if priority == "major milestone":
        boss_reason = "Workbook priority: Major milestone"
    elif re.search(r"\b(capstone|final)\b", title):
        boss_reason = "Workbook title marks a final or capstone objective"
    elif re.search(r"\bpurple[ -]team exercise\b", title):
        boss_reason = "Workbook title identifies a purple-team exercise"

    tags: list[str] = []
    if _has_lab_term(text):
        tags.append("Lab")
    if re.search(r"purple[ -]team", text, re.IGNORECASE):
        tags.append("Purple Team")

    return QuestClassification(
        quest_type=quest_type,
        is_boss=bool(boss_reason),
        boss_reason=boss_reason,
        tags=tuple(tags),
    )


def _has_lab_term(text: str) -> bool:
    return bool(re.search(r"\b(?:lab|laboratory|homelab|home\s+lab)\b", text, re.IGNORECASE))
