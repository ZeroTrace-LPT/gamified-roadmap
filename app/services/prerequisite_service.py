"""Shared resolution and readiness rules for explicit roadmap prerequisites."""

from __future__ import annotations

import json
from typing import Any


def parse_prerequisite_references(raw: Any) -> tuple[list[Any], bool]:
    """Return references and a malformed-data flag without discarding bad input."""
    if raw in (None, ""):
        return [], False
    try:
        value = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, json.JSONDecodeError):
        return [], True
    if isinstance(value, list):
        return value, False
    return ([value] if value else []), False


def resolve_prerequisites(
    item: dict[str, Any],
    items_by_id: dict[str, dict[str, Any]],
    items_by_name: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Resolve only exact IDs or unambiguous exact names from the active workbook."""
    references, malformed = parse_prerequisite_references(item.get("prerequisites_json"))
    resolved: list[dict[str, Any]] = []
    unresolved = ["Malformed structured prerequisite data"] if malformed else []

    for reference in references:
        if isinstance(reference, dict):
            item_id = reference.get("item_id") or reference.get("id")
            name = reference.get("name") or reference.get("title")
        else:
            item_id = reference if isinstance(reference, str) and reference in items_by_id else None
            name = reference if isinstance(reference, str) and not item_id else None

        if item_id:
            candidate = items_by_id.get(str(item_id))
            candidates = [candidate] if candidate else []
        elif name:
            candidates = items_by_name.get(str(name).strip().casefold(), [])
        else:
            candidates = []

        if len(candidates) != 1:
            label = str(name or item_id or reference).strip()
            unresolved.append(f"Unresolved or ambiguous prerequisite: {label}")
            continue

        prerequisite = candidates[0]
        resolved.append({
            "item_id": prerequisite["item_id"],
            "name": prerequisite["name"],
            "progress_status": prerequisite["progress_status"],
            "complete": prerequisite["progress_status"] == "Completed",
        })

    return resolved, unresolved


def get_reviewed_prerequisite_ids(connection: Any, workbook_id: str) -> set[str]:
    """Return local prerequisite-note reviews for one workbook snapshot."""
    return {
        row["item_id"]
        for row in connection.execute(
            """SELECT qpr.item_id FROM quest_prerequisite_reviews qpr
               JOIN roadmap_items i ON i.item_id=qpr.item_id
               WHERE i.workbook_id=?""",
            (workbook_id,),
        ).fetchall()
    }


def prerequisite_readiness(
    item: dict[str, Any],
    prerequisites: list[dict[str, Any]],
    unresolved: list[str],
    reviewed: bool,
) -> str:
    """Calculate ready, locked, or review status from source data and local review."""
    if unresolved:
        return "Needs review"
    if any(not entry["complete"] for entry in prerequisites):
        return "Locked"
    if str(item.get("prerequisite_notes") or "").strip() and not reviewed:
        return "Needs review"
    return "Available"
