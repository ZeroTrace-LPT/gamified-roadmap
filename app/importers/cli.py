"""Import a workbook from the command line for setup and support."""

from __future__ import annotations

import argparse
import json

from app.config.paths import get_database_path
from app.database.connection import connect_database
from app.importers.excel_importer import import_excel


def main() -> int:
    parser = argparse.ArgumentParser(description="Import a cybersecurity roadmap workbook into local SQLite.")
    parser.add_argument("workbook", help="Path to the .xlsx or .xlsm source workbook")
    parser.add_argument("--database", help="Optional explicit SQLite path")
    args = parser.parse_args()
    database_path = args.database or get_database_path()
    connection = connect_database(database_path)
    try:
        result = import_excel(connection, args.workbook)
    finally:
        connection.close()
    print(json.dumps({
        "workbook_id": result.workbook_id,
        "filename": result.filename,
        "sheets": result.sheet_count,
        "source_rows": result.source_row_count,
        "source_cells": result.source_cell_count,
        "formulas": result.formula_count,
        "normalized_items": result.item_count,
        "already_imported": result.already_imported,
        "issues": [issue.__dict__ for issue in result.issues],
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
