"""Source-backed skill branches, progress, and prerequisite readiness."""

from __future__ import annotations

from typing import Any

from app.services.prerequisite_service import (
    get_reviewed_prerequisite_ids,
    prerequisite_readiness,
    resolve_prerequisites,
)
from app.services.roadmap_service import get_active_workbook, get_roadmap_items


SKILL_ITEM_TYPES = {"skill", "specialization"}


def get_skill_tree(
    connection: Any,
    *,
    query: str = "",
    branch: str = "",
    progress_status: str = "",
    readiness: str = "",
) -> dict[str, Any]:
    """Return skill nodes grouped by their source track, without inferred edges."""
    workbook = get_active_workbook(connection)
    if workbook is None:
        return {"items": [], "branches": [], "branch_options": [], "counts": _empty_counts()}

    workbook_id = workbook["workbook_id"]
    sheet_order = {
        row["sheet_name"]: int(row["position"])
        for row in connection.execute(
            "SELECT sheet_name, position FROM source_sheets WHERE workbook_id=?",
            (workbook_id,),
        ).fetchall()
    }
    all_items = get_roadmap_items(connection, sort_by="Source")
    all_items.sort(key=lambda item: (
        sheet_order.get(item["source_sheet"], 9999), item["source_row"], item["item_id"]
    ))
    items_by_id = {item["item_id"]: item for item in all_items}
    items_by_name: dict[str, list[dict[str, Any]]] = {}
    for item in all_items:
        items_by_name.setdefault(item["name"].strip().casefold(), []).append(item)

    reviewed_ids = get_reviewed_prerequisite_ids(connection, workbook_id)
    nodes: list[dict[str, Any]] = []
    branch_options: list[str] = []
    for item in all_items:
        if item["item_type"] not in SKILL_ITEM_TYPES:
            continue
        track = str(item.get("category") or "").strip() or "Uncategorized"
        if track not in branch_options:
            branch_options.append(track)
        prerequisites, unresolved = resolve_prerequisites(item, items_by_id, items_by_name)
        reviewed = item["item_id"] in reviewed_ids
        item.update({
            "skill_branch": track,
            "skill_kind": "Specialization" if item["item_type"] == "specialization" else "Skill",
            "skill_timing_label": "Timeframe" if item["item_type"] == "specialization" else "Target age",
            "skill_timing": str(item.get("target_period") or "Not specified"),
            "skill_prerequisites": prerequisites,
            "skill_missing_prerequisites": [entry for entry in prerequisites if not entry["complete"]],
            "skill_unresolved_prerequisites": unresolved,
            "skill_has_prerequisite_note": bool(str(item.get("prerequisite_notes") or "").strip()),
            "skill_prerequisites_verified": reviewed,
            "skill_readiness": prerequisite_readiness(item, prerequisites, unresolved, reviewed),
            "skill_source_order": (sheet_order.get(item["source_sheet"], 9999), item["source_row"]),
        })
        nodes.append(item)

    query_key = query.strip().casefold()
    filtered: list[dict[str, Any]] = []
    for node in nodes:
        if branch and node["skill_branch"] != branch:
            continue
        if progress_status and node["progress_status"] != progress_status:
            continue
        if readiness and node["skill_readiness"] != readiness:
            continue
        searchable = " ".join(str(node.get(field) or "") for field in (
            "name", "description", "category", "target_period", "status", "priority",
            "source_sheet", "notes", "progress_note", "prerequisite_notes",
            "resources_json", "skill_kind", "skill_readiness",
        )).casefold()
        prerequisite_text = " ".join(
            entry["name"] for entry in node["skill_prerequisites"]
        ).casefold()
        if query_key and query_key not in searchable and query_key not in prerequisite_text:
            continue
        filtered.append(node)

    branch_groups = [
        {
            "name": branch_name,
            "items": [node for node in filtered if node["skill_branch"] == branch_name],
        }
        for branch_name in branch_options
        if any(node["skill_branch"] == branch_name for node in filtered)
    ]
    counts = {
        "total": len(nodes),
        "branches": len(branch_options),
        "available": sum(node["skill_readiness"] == "Available" for node in nodes),
        "locked": sum(node["skill_readiness"] == "Locked" for node in nodes),
        "needs_review": sum(node["skill_readiness"] == "Needs review" for node in nodes),
        "in_progress": sum(node["progress_status"] == "In progress" for node in nodes),
        "completed": sum(node["progress_status"] == "Completed" for node in nodes),
    }
    return {
        "items": filtered,
        "branches": branch_groups,
        "branch_options": branch_options,
        "counts": counts,
    }


def _empty_counts() -> dict[str, int]:
    return {
        "total": 0,
        "branches": 0,
        "available": 0,
        "locked": 0,
        "needs_review": 0,
        "in_progress": 0,
        "completed": 0,
    }
