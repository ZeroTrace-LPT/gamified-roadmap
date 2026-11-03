"""Workbook-derived quest board, recommendations, and prerequisite review."""

from __future__ import annotations

from typing import Any, Iterable

from app.quests.rules import classify_quest
from app.services.prerequisite_service import (
    get_reviewed_prerequisite_ids,
    prerequisite_readiness,
    resolve_prerequisites,
)
from app.services.roadmap_service import get_active_workbook, get_roadmap_items


_PRIORITY_RANK = {
    "major milestone": 0,
    "mandatory": 1,
    "very high": 2,
    "high": 3,
    "core": 3,
    "medium": 4,
    "low": 5,
    "optional": 6,
    "optional / future": 6,
    "future": 7,
    "done": 8,
}


def _enrich_quests(connection: Any) -> list[dict[str, Any]]:
    workbook = get_active_workbook(connection)
    if workbook is None:
        return []
    workbook_id = workbook["workbook_id"]
    items = get_roadmap_items(connection, sort_by="Source")
    sheet_order = {
        row["sheet_name"]: int(row["position"])
        for row in connection.execute(
            "SELECT sheet_name, position FROM source_sheets WHERE workbook_id=?",
            (workbook_id,),
        ).fetchall()
    }
    items.sort(key=lambda item: (
        sheet_order.get(item["source_sheet"], 9999), item["source_row"], item["item_id"]
    ))
    items_by_id = {item["item_id"]: item for item in items}
    items_by_name: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        items_by_name.setdefault(item["name"].strip().casefold(), []).append(item)

    verified_ids = get_reviewed_prerequisite_ids(connection, workbook_id)

    for item in items:
        classification = classify_quest(item)
        prerequisites, unresolved = resolve_prerequisites(item, items_by_id, items_by_name)
        missing = [entry for entry in prerequisites if not entry["complete"]]
        source_note = str(item.get("prerequisite_notes") or "").strip()
        note_review_required = bool(source_note)
        verified = item["item_id"] in verified_ids
        readiness = prerequisite_readiness(item, prerequisites, unresolved, verified)

        item.update({
            "quest_type": classification.quest_type,
            "is_boss_quest": classification.is_boss,
            "boss_reason": classification.boss_reason,
            "quest_tags": list(classification.tags),
            "prerequisites": prerequisites,
            "unresolved_prerequisites": unresolved,
            "missing_prerequisites": missing,
            "has_prerequisite_note": note_review_required,
            "prerequisites_verified": verified,
            "quest_readiness": readiness,
            "source_order": (sheet_order.get(item["source_sheet"], 9999), item["source_row"]),
        })
    return items


def _priority_rank(item: dict[str, Any]) -> int:
    return _PRIORITY_RANK.get(str(item.get("priority") or "").strip().casefold(), 9)


def get_recommended_quests(
    items: Iterable[dict[str, Any]], limit: int = 5
) -> list[dict[str, Any]]:
    """Choose the next ready source objectives, preserving workbook order."""
    eligible = [
        item for item in items
        if item["quest_readiness"] == "Available"
        and item["progress_status"] not in {"Completed", "Blocked"}
    ]
    eligible.sort(key=lambda item: (
        0 if item["progress_status"] == "In progress" else 1,
        0 if item["quest_type"] == "Main Quest" else 1,
        item["source_order"][0],
        _priority_rank(item),
        item["source_order"][1],
    ))

    for rank, item in enumerate(eligible, start=1):
        item["recommendation_rank"] = rank
        if item["progress_status"] == "In progress":
            item["recommendation_reason"] = "Continue an in-progress quest."
        elif item["quest_type"] == "Main Quest":
            item["recommendation_reason"] = "Next incomplete main quest in workbook order."
        elif item.get("priority"):
            item["recommendation_reason"] = f"Next available quest · source priority: {item['priority']}."
        elif item["prerequisites"]:
            item["recommendation_reason"] = "Recorded prerequisites are complete."
        else:
            item["recommendation_reason"] = "Next available objective in workbook order."
    return eligible[:max(0, limit)]


def get_quest_board(
    connection: Any,
    *,
    query: str = "",
    quest_type: str = "",
    progress_status: str = "",
    readiness: str = "",
) -> dict[str, Any]:
    """Return a filtered quest board plus global counts and recommendations."""
    all_items = _enrich_quests(connection)
    recommendations = get_recommended_quests(all_items)
    for rank, item in enumerate(recommendations, start=1):
        item["recommendation_rank"] = rank

    normalized_query = query.strip().casefold()
    filtered = []
    for item in all_items:
        if quest_type == "Boss Quest":
            if not item["is_boss_quest"]:
                continue
        elif quest_type and quest_type != "All quest types" and item["quest_type"] != quest_type:
            continue
        if progress_status and item["progress_status"] != progress_status:
            continue
        if readiness and item["quest_readiness"] != readiness:
            continue
        searchable = " ".join(str(item.get(field) or "") for field in (
            "name", "description", "category", "phase", "priority", "source_sheet",
            "prerequisite_notes", "notes", "progress_note", "quest_type", "quest_readiness",
        )).casefold()
        if normalized_query and normalized_query not in searchable:
            continue
        filtered.append(item)

    recommendation_ids = {
        item["item_id"]: item["recommendation_rank"] for item in recommendations
    }
    filtered.sort(key=lambda item: (
        0 if item["item_id"] in recommendation_ids else 1,
        recommendation_ids.get(item["item_id"], 9999),
        {"Available": 0, "Needs review": 1, "Locked": 2}.get(item["quest_readiness"], 3),
        item["source_order"],
    ))

    counts = {
        "total": len(all_items),
        "available": sum(
            item["quest_readiness"] == "Available"
            and item["progress_status"] == "Not started"
            for item in all_items
        ),
        "in_progress": sum(item["progress_status"] == "In progress" for item in all_items),
        "user_blocked": sum(item["progress_status"] == "Blocked" for item in all_items),
        "needs_review": sum(item["quest_readiness"] == "Needs review" for item in all_items),
        "locked": sum(item["quest_readiness"] == "Locked" for item in all_items),
        "completed": sum(item["progress_status"] == "Completed" for item in all_items),
        "boss_quests": sum(item["is_boss_quest"] for item in all_items),
    }
    return {"items": filtered, "recommendations": recommendations, "counts": counts}


def set_prerequisites_verified(connection: Any, item_id: str, verified: bool) -> None:
    """Store a user review of a source prerequisite note without editing the source."""
    workbook = get_active_workbook(connection)
    if workbook is None:
        raise KeyError("No active workbook is imported.")
    item = connection.execute(
        """SELECT item_id, prerequisite_notes FROM roadmap_items
           WHERE item_id=? AND workbook_id=?""",
        (item_id, workbook["workbook_id"]),
    ).fetchone()
    if item is None:
        raise KeyError("Quest does not exist in the active workbook.")
    if verified and not str(item["prerequisite_notes"] or "").strip():
        raise ValueError("This quest has no source prerequisite note to verify.")

    with connection:
        if verified:
            connection.execute(
                """INSERT INTO quest_prerequisite_reviews(item_id) VALUES(?)
                   ON CONFLICT(item_id) DO NOTHING""",
                (item_id,),
            )
        else:
            connection.execute(
                "DELETE FROM quest_prerequisite_reviews WHERE item_id=?", (item_id,)
            )
