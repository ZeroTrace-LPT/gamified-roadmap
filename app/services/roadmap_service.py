"""Roadmap queries and user-owned progress persistence."""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from app.models.roadmap import PROGRESS_STATUSES, ProgressUpdate


_SOURCE_DONE = {"done", "complete", "completed"}
_SOURCE_IN_PROGRESS = {"in progress", "in-progress", "started"}


def _active_workbook_id(connection: Any) -> str | None:
    row = connection.execute(
        "SELECT value_json FROM user_settings WHERE setting_key='active_workbook_id'"
    ).fetchone()
    return json.loads(row[0]) if row else None


def _default_progress(source_status: Any, source_percent: Any) -> tuple[str, int]:
    """Derive a display default from known source terms without rewriting them."""
    raw_status = str(source_status or "").strip().casefold()
    percent = int(source_percent) if isinstance(source_percent, (int, float)) else 0
    if raw_status in _SOURCE_DONE:
        return "Completed", 100
    if raw_status in _SOURCE_IN_PROGRESS:
        return "In progress", min(max(percent, 0), 100)
    if percent >= 100:
        return "Completed", 100
    if percent > 0:
        return "In progress", min(percent, 100)
    return "Not started", 0


def _with_progress(row: Any) -> dict[str, Any]:
    """Add the effective local state while leaving imported source fields intact."""
    item = dict(row)
    override_status = item.pop("_override_status", None)
    override_percent = item.pop("_override_percent", None)
    override_started = item.pop("_override_date_started", None)
    override_completed = item.pop("_override_date_completed", None)
    override_note = item.pop("_override_note", None)

    source_percent = item.get("progress_percent")
    default_status, default_percent = _default_progress(item.get("status"), source_percent)
    has_override = override_status is not None
    item["source_progress_percent"] = source_percent
    item["progress_status"] = override_status or default_status
    item["progress_percent"] = (
        int(override_percent) if override_percent is not None else default_percent
    )
    item["progress_date_started"] = (
        override_started if has_override else item.get("date_started")
    )
    item["progress_date_completed"] = (
        override_completed if has_override else item.get("date_completed")
    )
    item["progress_note"] = override_note or ""
    item["has_progress_override"] = has_override
    item["xp_awarded"] = int(item.get("xp_awarded") or 0)
    return item


def _roadmap_select() -> str:
    return """SELECT i.*,
                     p.status AS _override_status,
                     p.progress_percent AS _override_percent,
                     p.date_started AS _override_date_started,
                     p.date_completed AS _override_date_completed,
                     p.note AS _override_note,
                     COALESCE((SELECT SUM(x.amount) FROM xp_transactions x
                               WHERE x.item_id=i.item_id), 0) AS xp_awarded
              FROM roadmap_items i
              LEFT JOIN roadmap_progress p ON p.item_id=i.item_id"""


def _local_status_sql() -> str:
    return """COALESCE(p.status,
        CASE
          WHEN lower(trim(i.status)) IN ('done', 'complete', 'completed') THEN 'Completed'
          WHEN lower(trim(i.status)) IN ('in progress', 'in-progress', 'started') THEN 'In progress'
          WHEN COALESCE(i.progress_percent, 0) >= 100 THEN 'Completed'
          WHEN COALESCE(i.progress_percent, 0) > 0 THEN 'In progress'
          ELSE 'Not started'
        END)"""


def get_active_workbook(connection: Any) -> Any | None:
    workbook_id = _active_workbook_id(connection)
    if not workbook_id:
        return None
    return connection.execute(
        "SELECT * FROM workbooks WHERE workbook_id=?", (workbook_id,)
    ).fetchone()


def get_roadmap_filter_options(connection: Any) -> dict[str, list[str]]:
    """Return source-backed filter choices for the active workbook."""
    workbook_id = _active_workbook_id(connection)
    if not workbook_id:
        return {"types": [], "categories": [], "phases": [], "source_statuses": [], "years": []}

    def distinct(column: str) -> list[str]:
        rows = connection.execute(
            f"""SELECT DISTINCT {column} FROM roadmap_items
                WHERE workbook_id=? AND {column} IS NOT NULL AND trim({column})<>''
                ORDER BY {column} COLLATE NOCASE""",
            (workbook_id,),
        ).fetchall()
        return [str(row[0]) for row in rows]

    periods = distinct("target_period")
    years = sorted({
        match.group(1)
        for period in periods
        if (match := re.match(r"^(\d{4})(?:-\d{2})?$", period))
    })
    return {
        "types": distinct("item_type"),
        "categories": distinct("category"),
        "phases": distinct("phase"),
        "source_statuses": distinct("status"),
        "years": years,
    }


def get_roadmap_items(
    connection: Any,
    *,
    query: str = "",
    item_type: str = "",
    category: str = "",
    phase: str = "",
    progress_status: str = "",
    source_status: str = "",
    year: str = "",
    sort_by: str = "Month",
) -> list[dict[str, Any]]:
    """Search and filter normalized items, retaining their exact imported status."""
    workbook_id = _active_workbook_id(connection)
    if not workbook_id:
        return []

    conditions = ["i.workbook_id=?"]
    params: list[Any] = [workbook_id]
    for column, value in (
        ("i.item_type", item_type),
        ("i.category", category),
        ("i.phase", phase),
        ("i.status", source_status),
    ):
        if value:
            conditions.append(f"{column}=? COLLATE NOCASE")
            params.append(value)

    local_status = _local_status_sql()
    if progress_status:
        conditions.append(f"{local_status}=?")
        params.append(progress_status)
    if year:
        conditions.append("substr(i.target_period, 1, 4)=?")
        params.append(year)
    if query.strip():
        needle = query.strip().replace("!", "!!").replace("%", "!%").replace("_", "!_")
        search_columns = (
            "i.name", "i.description", "i.category", "i.phase", "i.target_period",
            "i.status", "i.priority", "i.source_sheet", "i.prerequisite_notes",
            "i.notes", "i.resources_json", "i.source_record_json", "p.note",
        )
        conditions.append("(" + " OR ".join(
            f"COALESCE({column}, '') LIKE ? ESCAPE '!' COLLATE NOCASE"
            for column in search_columns
        ) + ")")
        params.extend([f"%{needle}%"] * len(search_columns))

    order_by = {
        "Month": "CASE WHEN i.target_period GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]' THEN 0 ELSE 1 END, i.target_period COLLATE NOCASE, i.phase COLLATE NOCASE, i.source_sheet, i.source_row",
        "Year": "CASE WHEN i.target_period GLOB '[0-9][0-9][0-9][0-9]*' THEN substr(i.target_period, 1, 4) ELSE '9999' END, i.target_period COLLATE NOCASE, i.phase COLLATE NOCASE, i.source_sheet, i.source_row",
        "Phase": "CASE WHEN trim(i.phase)='' THEN 1 ELSE 0 END, i.phase COLLATE NOCASE, i.target_period COLLATE NOCASE, i.source_sheet, i.source_row",
        "Source": "i.source_sheet COLLATE NOCASE, i.source_row",
    }.get(sort_by, "CASE WHEN i.target_period GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]' THEN 0 ELSE 1 END, i.target_period COLLATE NOCASE, i.phase COLLATE NOCASE, i.source_sheet, i.source_row")

    rows = connection.execute(
        _roadmap_select() + " WHERE " + " AND ".join(conditions) + " ORDER BY " + order_by,
        params,
    ).fetchall()
    return [_with_progress(row) for row in rows]


def get_roadmap_item(connection: Any, item_id: str) -> dict[str, Any] | None:
    """Fetch a single item from the active workbook with its local progress overlay."""
    workbook_id = _active_workbook_id(connection)
    if not workbook_id:
        return None
    row = connection.execute(
        _roadmap_select() + " WHERE i.item_id=? AND i.workbook_id=?",
        (item_id, workbook_id),
    ).fetchone()
    return _with_progress(row) if row else None


def save_item_progress(connection: Any, item_id: str, update: ProgressUpdate) -> None:
    """Persist user progress separately; never update source rows or source status."""
    if update.status not in PROGRESS_STATUSES:
        raise ValueError(f"Choose one of: {', '.join(PROGRESS_STATUSES)}.")
    if isinstance(update.progress_percent, bool) or not isinstance(update.progress_percent, int):
        raise ValueError("Progress must be a whole number from 0 to 100.")
    if not 0 <= update.progress_percent <= 100:
        raise ValueError("Progress must be between 0 and 100.")
    if update.status == "Completed" and update.progress_percent != 100:
        raise ValueError("Completed items must have 100% progress.")
    if update.status == "Not started" and update.progress_percent != 0:
        raise ValueError("Not started items must have 0% progress.")

    def validate_date(value: str | None, label: str) -> str | None:
        if not value:
            return None
        try:
            parsed = date.fromisoformat(value)
        except ValueError as error:
            raise ValueError(f"{label} must use YYYY-MM-DD format.") from error
        if parsed.isoformat() != value:
            raise ValueError(f"{label} must use YYYY-MM-DD format.")
        return value

    started = validate_date(update.date_started, "Start date")
    completed = validate_date(update.date_completed, "Completion date")
    if completed and update.status != "Completed":
        raise ValueError("A completion date can only be recorded for a completed item.")
    if started and completed and completed < started:
        raise ValueError("Completion date cannot be earlier than the start date.")

    workbook_id = _active_workbook_id(connection)
    exists = connection.execute(
        "SELECT 1 FROM roadmap_items WHERE item_id=? AND workbook_id=?",
        (item_id, workbook_id),
    ).fetchone() if workbook_id else None
    if not exists:
        raise KeyError("Roadmap item does not exist in the active workbook.")

    with connection:
        connection.execute(
            """INSERT INTO roadmap_progress(item_id, status, progress_percent,
                       date_started, date_completed, note)
               VALUES(?, ?, ?, ?, ?, ?)
               ON CONFLICT(item_id) DO UPDATE SET
                   status=excluded.status,
                   progress_percent=excluded.progress_percent,
                   date_started=excluded.date_started,
                   date_completed=excluded.date_completed,
                   note=excluded.note,
                   updated_at=datetime('now')""",
            (item_id, update.status, update.progress_percent, started, completed, update.note.strip()),
        )
    from app.services.gamification_service import sync_xp_awards

    sync_xp_awards(connection)


def clear_item_progress(connection: Any, item_id: str) -> None:
    """Remove a local override and return display progress to source-derived defaults."""
    workbook_id = _active_workbook_id(connection)
    exists = connection.execute(
        "SELECT 1 FROM roadmap_items WHERE item_id=? AND workbook_id=?",
        (item_id, workbook_id),
    ).fetchone() if workbook_id else None
    if not exists:
        raise KeyError("Roadmap item does not exist in the active workbook.")
    with connection:
        connection.execute("DELETE FROM roadmap_progress WHERE item_id=?", (item_id,))
    from app.services.gamification_service import sync_xp_awards

    sync_xp_awards(connection)


def get_dashboard_data(connection: Any) -> dict[str, Any]:
    from app.quests.rules import classify_quest
    from app.services.gamification_service import get_gamification_data
    from app.services.quest_service import get_quest_board
    from app.services.skill_tree_service import get_skill_tree

    workbook = get_active_workbook(connection)
    if workbook is None:
        return {"has_data": False}

    missions = get_core_roadmap(connection)
    total = len(missions)
    completed = sum(1 for item in missions if item["progress_status"] == "Completed")
    in_progress = sum(1 for item in missions if item["progress_status"] == "In progress")
    now_month = date.today().strftime("%Y-%m")
    all_items = get_roadmap_items(connection, sort_by="Source")
    items_total = len(all_items)
    overall_completed = sum(item["progress_status"] == "Completed" for item in all_items)
    overall_in_progress = sum(item["progress_status"] == "In progress" for item in all_items)

    def type_summary(item_type: str) -> dict[str, int]:
        selected = [item for item in all_items if item["item_type"] == item_type]
        return {
            "total": len(selected),
            "completed": sum(item["progress_status"] == "Completed" for item in selected),
            "in_progress": sum(item["progress_status"] == "In progress" for item in selected),
        }

    lab_items = []
    for item in all_items:
        classification = classify_quest(item)
        if "Lab" in classification.tags or classification.quest_type == "Lab Quest":
            lab_items.append(item)
    hour_values = [
        float(item["estimated_hours"])
        for item in all_items
        if item.get("estimated_hours") is not None
    ]
    skill_tree = get_skill_tree(connection)
    skill_branches = []
    for branch in skill_tree["branches"]:
        branch_items = branch["items"]
        count = len(branch_items)
        skill_branches.append({
            "name": branch["name"],
            "total": count,
            "completed": sum(item["progress_status"] == "Completed" for item in branch_items),
            "in_progress": sum(item["progress_status"] == "In progress" for item in branch_items),
            "progress_percent": round(
                sum(int(item["progress_percent"]) for item in branch_items) / count
            ) if count else 0,
        })
    quest_board = get_quest_board(connection)
    recommendations = quest_board["recommendations"]
    current = recommendations[0] if recommendations else None
    next_objectives = recommendations[1:4]
    normalized = json.loads(workbook["summary_json"] or "{}")
    profile_name = normalized.get("profile_name") or "Cybersecurity Apprentice"

    gamification = get_gamification_data(connection)

    statistics = {
        "monthly_missions": {
            "total": total,
            "completed": completed,
            "in_progress": in_progress,
            "percent": completed / total * 100 if total else 0,
        },
        "skills": type_summary("skill"),
        "specializations": type_summary("specialization"),
        "certifications": type_summary("certification"),
        "projects": type_summary("project"),
        "labs": {
            "total": len(lab_items),
            "completed": sum(item["progress_status"] == "Completed" for item in lab_items),
            "in_progress": sum(item["progress_status"] == "In progress" for item in lab_items),
        },
        "overall": {
            "total": items_total,
            "completed": overall_completed,
            "in_progress": overall_in_progress,
            "percent": overall_completed / items_total * 100 if items_total else 0,
        },
        "learning_hours": sum(hour_values) if hour_values else None,
        "learning_hours_recorded": bool(hour_values),
    }
    current_phase = "Not specified in workbook"
    if current:
        current_phase = str(current.get("phase") or current.get("target_period") or current_phase)

    return {
        "has_data": True,
        "workbook": workbook,
        "profile_name": profile_name,
        "current_role": gamification["level_title"] or "Role not specified in workbook",
        "current_phase": current_phase,
        "level": gamification["current_level"],
        "level_title": gamification["level_title"],
        "xp": gamification["career_xp"],
        "gamification": gamification,
        "statistics": statistics,
        "skill_branches": skill_branches,
        "roadmap_total": total,
        "roadmap_completed": completed,
        "roadmap_in_progress": in_progress,
        "roadmap_percent": (completed / total * 100) if total else 0,
        "overall_total": items_total,
        "overall_completed": overall_completed,
        "overall_in_progress": overall_in_progress,
        "overall_percent": statistics["overall"]["percent"],
        "record_total": items_total,
        "current_mission": current,
        "next_objectives": next_objectives,
        "current_month": now_month,
    }


def get_core_roadmap(connection: Any) -> list[dict[str, Any]]:
    """Return monthly missions with local progress overlaid for the dashboard."""
    return get_roadmap_items(connection, item_type="monthly_mission", sort_by="Month")


def get_source_sheets(connection: Any) -> list[Any]:
    workbook_id = _active_workbook_id(connection)
    if not workbook_id:
        return []
    return connection.execute(
        """SELECT ss.*,
                  (SELECT COUNT(*) FROM source_rows sr
                   WHERE sr.workbook_id=ss.workbook_id AND sr.sheet_name=ss.sheet_name) AS stored_rows,
                  (SELECT COUNT(*) FROM source_cells sc
                   WHERE sc.workbook_id=ss.workbook_id AND sc.sheet_name=ss.sheet_name) AS stored_cells
           FROM source_sheets ss WHERE workbook_id=? ORDER BY position""",
        (workbook_id,),
    ).fetchall()


def get_import_issues(connection: Any) -> list[Any]:
    workbook_id = _active_workbook_id(connection)
    if not workbook_id:
        return []
    return connection.execute(
        """SELECT * FROM import_issues WHERE workbook_id=?
           ORDER BY CASE severity WHEN 'error' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END, issue_id""",
        (workbook_id,),
    ).fetchall()
