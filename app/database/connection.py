"""SQLite connection and schema versioning."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS workbooks (
    workbook_id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    imported_at TEXT NOT NULL DEFAULT (datetime('now')),
    importer_version TEXT NOT NULL,
    sheet_count INTEGER NOT NULL,
    source_row_count INTEGER NOT NULL,
    source_cell_count INTEGER NOT NULL,
    formula_count INTEGER NOT NULL,
    item_count INTEGER NOT NULL,
    summary_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS source_sheets (
    workbook_id TEXT NOT NULL REFERENCES workbooks(workbook_id) ON DELETE CASCADE,
    sheet_name TEXT NOT NULL,
    position INTEGER NOT NULL,
    state TEXT NOT NULL,
    max_row INTEGER NOT NULL,
    max_column INTEGER NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (workbook_id, sheet_name)
);

CREATE TABLE IF NOT EXISTS source_rows (
    workbook_id TEXT NOT NULL,
    sheet_name TEXT NOT NULL,
    row_number INTEGER NOT NULL,
    values_json TEXT NOT NULL,
    PRIMARY KEY (workbook_id, sheet_name, row_number),
    FOREIGN KEY (workbook_id, sheet_name)
        REFERENCES source_sheets(workbook_id, sheet_name) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS source_cells (
    workbook_id TEXT NOT NULL,
    sheet_name TEXT NOT NULL,
    coordinate TEXT NOT NULL,
    row_number INTEGER NOT NULL,
    column_number INTEGER NOT NULL,
    data_type TEXT NOT NULL,
    value_json TEXT,
    formula_text TEXT,
    cached_value_json TEXT,
    number_format TEXT,
    hyperlink TEXT,
    PRIMARY KEY (workbook_id, sheet_name, coordinate),
    FOREIGN KEY (workbook_id, sheet_name)
        REFERENCES source_sheets(workbook_id, sheet_name) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS roadmap_items (
    item_id TEXT PRIMARY KEY,
    workbook_id TEXT NOT NULL REFERENCES workbooks(workbook_id) ON DELETE CASCADE,
    source_sheet TEXT NOT NULL,
    source_row INTEGER NOT NULL,
    item_type TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    phase TEXT NOT NULL DEFAULT '',
    target_period TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '',
    priority TEXT NOT NULL DEFAULT '',
    difficulty TEXT,
    estimated_hours REAL,
    prerequisites_json TEXT NOT NULL DEFAULT '[]',
    prerequisite_notes TEXT NOT NULL DEFAULT '',
    xp_reward INTEGER,
    xp_earned INTEGER,
    progress_percent REAL,
    resources_json TEXT NOT NULL DEFAULT '[]',
    notes TEXT NOT NULL DEFAULT '',
    source_record_json TEXT NOT NULL,
    date_started TEXT,
    date_completed TEXT,
    UNIQUE (workbook_id, source_sheet, source_row)
);

CREATE INDEX IF NOT EXISTS idx_roadmap_items_period
    ON roadmap_items(workbook_id, target_period, source_row);
CREATE INDEX IF NOT EXISTS idx_roadmap_items_category
    ON roadmap_items(workbook_id, category, item_type);

CREATE TABLE IF NOT EXISTS import_issues (
    issue_id INTEGER PRIMARY KEY AUTOINCREMENT,
    workbook_id TEXT NOT NULL REFERENCES workbooks(workbook_id) ON DELETE CASCADE,
    severity TEXT NOT NULL,
    code TEXT NOT NULL,
    sheet_name TEXT NOT NULL DEFAULT '',
    cell_reference TEXT NOT NULL DEFAULT '',
    message TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_settings (
    setting_key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL
);
"""


def connect_database(path: str | Path) -> sqlite3.Connection:
    """Open the database, create its parent directory, and apply migrations."""
    database_path = Path(path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    initialize_database(connection)
    return connection


def initialize_database(connection: sqlite3.Connection) -> None:
    """Apply idempotent schema creation and record the current migration."""
    with connection:
        connection.executescript(SCHEMA)
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations(version) VALUES (?)",
            (SCHEMA_VERSION,),
        )
