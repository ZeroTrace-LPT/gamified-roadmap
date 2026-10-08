"""Read-only query helpers for the v0.1 foundation UI."""

from __future__ import annotations

import json
from datetime import date
from typing import Any


def _active_workbook_id(connection: Any) -> str | None:
    row = connection.execute(
        "SELECT value_json FROM user_settings WHERE setting_key='active_workbook_id'"
    ).fetchone()
    return json.loads(row[0]) if row else None


def get_active_workbook(connection: Any) -> Any | None:
    workbook_id = _active_workbook_id(connection)
    if not workbook_id:
        return None
    return connection.execute(
        "SELECT * FROM workbooks WHERE workbook_id=?", (workbook_id,)
    ).fetchone()


def get_dashboard_data(connection: Any) -> dict[str, Any]:
    workbook = get_active_workbook(connection)
    if workbook is None:
        return {"has_data": False}

    workbook_id = workbook["workbook_id"]
    missions = connection.execute(
        """SELECT * FROM roadmap_items
           WHERE workbook_id=? AND item_type='monthly_mission'
           ORDER BY target_period, source_row""",
        (workbook_id,),
    ).fetchall()
    total = len(missions)
    completed = sum(1 for item in missions if item["status"].casefold() in {"done", "completed"})
    in_progress = sum(1 for item in missions if item["status"].casefold() == "in progress")
    now_month = date.today().strftime("%Y-%m")
    current = next((item for item in missions if item["target_period"] >= now_month and item["status"].casefold() not in {"done", "completed"}), None)
    if current is None:
        current = next((item for item in missions if item["status"].casefold() not in {"done", "completed"}), None)

    items_total = connection.execute(
        "SELECT COUNT(*) FROM roadmap_items WHERE workbook_id=?", (workbook_id,)
    ).fetchone()[0]
    normalized = json.loads(workbook["summary_json"] or "{}")
    profile_name = normalized.get("profile_name") or "Cybersecurity Apprentice"

    # The workbook's own ladder lives in Dashboard A15:C24. The v0.1 UI uses
    # the saved level and XP cells, without introducing a new progression rule.
    source_level = connection.execute(
        "SELECT cached_value_json FROM source_cells WHERE workbook_id=? AND sheet_name='Dashboard' AND coordinate='E9'",
        (workbook_id,),
    ).fetchone()
    source_xp = connection.execute(
        "SELECT cached_value_json FROM source_cells WHERE workbook_id=? AND sheet_name='Dashboard' AND coordinate='E8'",
        (workbook_id,),
    ).fetchone()
    level = json.loads(source_level[0]) if source_level and source_level[0] else 1
    xp = json.loads(source_xp[0]) if source_xp and source_xp[0] else 0
    if isinstance(level, dict):
        level = level.get("value", 1)
    if isinstance(xp, dict):
        xp = xp.get("value", 0)
    level_row = connection.execute(
        """SELECT value_json FROM source_cells
           WHERE workbook_id=? AND sheet_name='Dashboard' AND coordinate=?""",
        (workbook_id, f"C{14 + int(level)}"),
    ).fetchone()
    level_title = json.loads(level_row[0]) if level_row and level_row[0] else "IT Apprentice"

    return {
        "has_data": True,
        "workbook": workbook,
        "profile_name": profile_name,
        "level": int(level) if isinstance(level, (int, float)) else 1,
        "level_title": level_title,
        "xp": int(xp) if isinstance(xp, (int, float)) else 0,
        "roadmap_total": total,
        "roadmap_completed": completed,
        "roadmap_in_progress": in_progress,
        "roadmap_percent": (completed / total * 100) if total else 0,
        "record_total": items_total,
        "current_mission": current,
        "current_month": now_month,
    }


def get_core_roadmap(connection: Any) -> list[Any]:
    workbook_id = _active_workbook_id(connection)
    if not workbook_id:
        return []
    return connection.execute(
        """SELECT * FROM roadmap_items WHERE workbook_id=? AND item_type='monthly_mission'
           ORDER BY target_period, source_row""",
        (workbook_id,),
    ).fetchall()


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
        "SELECT * FROM import_issues WHERE workbook_id=? ORDER BY CASE severity WHEN 'error' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END, issue_id",
        (workbook_id,),
    ).fetchall()
