"""Workbook-backed XP awards, level progression, and reward history."""

from __future__ import annotations

import json
from typing import Any

from app.gamification.progression import calculate_progression, parse_level_definitions


_SOURCE_DONE = {"done", "complete", "completed"}
_SOURCE_IN_PROGRESS = {"in progress", "in-progress", "started"}


def _active_workbook_id(connection: Any) -> str | None:
    row = connection.execute(
        "SELECT value_json FROM user_settings WHERE setting_key='active_workbook_id'"
    ).fetchone()
    return json.loads(row[0]) if row else None


def _as_source_value(value_json: str | None, cached_json: str | None = None) -> Any:
    raw = value_json if value_json not in (None, "null") else cached_json
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return raw


def get_source_levels(connection: Any, workbook_id: str) -> tuple:
    """Read the workbook's Dashboard level table without inventing defaults."""
    rows = connection.execute(
        """SELECT coordinate, value_json, cached_value_json
           FROM source_cells WHERE workbook_id=? AND sheet_name='Dashboard'""",
        (workbook_id,),
    ).fetchall()
    cells = {
        row["coordinate"]: _as_source_value(row["value_json"], row["cached_value_json"])
        for row in rows
    }
    return parse_level_definitions(cells)


def _effective_status(source_status: Any, source_percent: Any, local_status: Any) -> str:
    if local_status:
        return str(local_status)
    raw_status = str(source_status or "").strip().casefold()
    if raw_status in _SOURCE_DONE:
        return "Completed"
    if raw_status in _SOURCE_IN_PROGRESS:
        return "In progress"
    try:
        percent = float(source_percent or 0)
    except (TypeError, ValueError):
        percent = 0
    if percent >= 100:
        return "Completed"
    if percent > 0:
        return "In progress"
    return "Not started"


def _whole_xp(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    numeric = float(value)
    return int(numeric) if numeric.is_integer() and numeric > 0 else 0


def sync_xp_awards(connection: Any) -> int:
    """Reconcile signed XP transactions with each active snapshot's progress.

    A completed source-backed item earns its workbook reward once. Reopening or
    resetting an item writes a reversal, keeping a useful audit history without
    double-awarding on refresh or application restart.
    """
    workbook_id = _active_workbook_id(connection)
    if not workbook_id:
        return 0

    items = connection.execute(
        """SELECT i.item_id, i.name, i.status AS source_status,
                  i.progress_percent AS source_percent, i.xp_reward,
                  i.date_completed AS source_date_completed,
                  p.status AS local_status, p.date_completed AS local_date_completed,
                  p.updated_at AS local_updated_at
           FROM roadmap_items i
           LEFT JOIN roadmap_progress p ON p.item_id=i.item_id
           WHERE i.workbook_id=?
           ORDER BY i.source_sheet, i.source_row""",
        (workbook_id,),
    ).fetchall()
    existing_rows = connection.execute(
        """SELECT xt.item_id, SUM(xt.amount) AS net_amount
           FROM xp_transactions xt
           JOIN roadmap_items i ON i.item_id=xt.item_id
           WHERE i.workbook_id=? GROUP BY xt.item_id""",
        (workbook_id,),
    ).fetchall()
    current_by_item = {row["item_id"]: int(row["net_amount"] or 0) for row in existing_rows}
    transaction_count = 0

    with connection:
        for item in items:
            status = _effective_status(
                item["source_status"], item["source_percent"], item["local_status"]
            )
            reward = _whole_xp(item["xp_reward"])
            expected = reward if status == "Completed" else 0
            current = current_by_item.get(item["item_id"], 0)
            delta = expected - current
            if delta == 0:
                continue

            if current == 0 and delta > 0:
                event_type = "award"
                reason = "Completed workbook item"
                if item["local_status"] == "Completed":
                    occurred_at = item["local_date_completed"] or item["local_updated_at"]
                else:
                    occurred_at = item["source_date_completed"]
            elif delta < 0 and expected == 0:
                event_type = "reversal"
                reason = "Item is no longer marked completed"
                occurred_at = None
            else:
                event_type = "adjustment"
                reason = "Workbook reward reconciliation"
                occurred_at = None

            connection.execute(
                """INSERT INTO xp_transactions(item_id, amount, event_type, reason, created_at)
                   VALUES(?, ?, ?, ?, COALESCE(?, datetime('now')))""",
                (item["item_id"], delta, event_type, reason, occurred_at),
            )
            current_by_item[item["item_id"]] = expected
            transaction_count += 1
    return transaction_count


def get_gamification_data(connection: Any) -> dict[str, Any]:
    """Return current XP totals, source-defined level, and recent transactions."""
    workbook_id = _active_workbook_id(connection)
    if not workbook_id:
        return {"has_data": False, "total_xp": 0, "career_xp": 0, "track_xp": 0}

    totals = connection.execute(
        """SELECT COALESCE(SUM(xt.amount), 0) AS total_xp,
                  COALESCE(SUM(CASE WHEN i.item_type IN ('monthly_mission', 'project')
                                    THEN xt.amount ELSE 0 END), 0) AS career_xp,
                  COALESCE(SUM(CASE WHEN i.item_type NOT IN ('monthly_mission', 'project')
                                    THEN xt.amount ELSE 0 END), 0) AS track_xp
           FROM xp_transactions xt
           JOIN roadmap_items i ON i.item_id=xt.item_id
           WHERE i.workbook_id=?""",
        (workbook_id,),
    ).fetchone()
    total_xp = max(0, int(totals["total_xp"] or 0))
    career_xp = max(0, int(totals["career_xp"] or 0))
    track_xp = max(0, int(totals["track_xp"] or 0))

    reward_items = connection.execute(
        """SELECT i.xp_reward, i.status AS source_status,
                  i.progress_percent AS source_percent, p.status AS local_status
           FROM roadmap_items i LEFT JOIN roadmap_progress p ON p.item_id=i.item_id
           WHERE i.workbook_id=? AND i.xp_reward>0""",
        (workbook_id,),
    ).fetchall()
    completed_reward_items = 0
    xp_available = 0
    for item in reward_items:
        completed = _effective_status(
            item["source_status"], item["source_percent"], item["local_status"]
        ) == "Completed"
        completed_reward_items += int(completed)
        if not completed:
            xp_available += _whole_xp(item["xp_reward"])

    awarded_items = connection.execute(
        """SELECT COUNT(*) FROM (
               SELECT xt.item_id FROM xp_transactions xt
               JOIN roadmap_items i ON i.item_id=xt.item_id
               WHERE i.workbook_id=?
               GROUP BY xt.item_id HAVING SUM(xt.amount)>0
           )""",
        (workbook_id,),
    ).fetchone()[0]

    levels = get_source_levels(connection, workbook_id)
    progression = calculate_progression(career_xp, levels)
    recent = connection.execute(
        """SELECT xt.amount, xt.event_type, xt.created_at, xt.reason,
                  i.name, i.item_type
           FROM xp_transactions xt
           JOIN roadmap_items i ON i.item_id=xt.item_id
           WHERE i.workbook_id=?
           ORDER BY xt.transaction_id DESC LIMIT 8""",
        (workbook_id,),
    ).fetchall()
    return {
        "has_data": True,
        "total_xp": total_xp,
        "career_xp": career_xp,
        "track_xp": track_xp,
        "xp_available": xp_available,
        "reward_items": len(reward_items),
        "completed_reward_items": completed_reward_items,
        "awarded_items": int(awarded_items),
        "levels": levels,
        "recent_transactions": [dict(row) for row in recent],
        **progression,
    }
