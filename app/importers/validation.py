"""Workbook validation that reports uncertainty without dropping source data."""

from __future__ import annotations

import re
from typing import Any

from openpyxl.worksheet.worksheet import Worksheet

from app.models.roadmap import ImportIssue, RoadmapItem

CELL_REF = re.compile(r"(?<![A-Z0-9_])\$?([A-Z]{1,3})\$?(\d+)", re.IGNORECASE)
MONTH_TEXT = re.compile(r"^\d{4}-\d{2}$")
ERROR_VALUES = ("#REF!", "#DIV/0!", "#VALUE!", "#NAME?", "#N/A", "#NUM!", "#NULL!")


def _issue(severity: str, code: str, message: str, sheet: str = "", cell: str = "") -> ImportIssue:
    return ImportIssue(severity=severity, code=code, message=message, sheet=sheet, cell=cell)


def validate_workbook(
    worksheets: list[Worksheet],
    cached_sheets: dict[str, Worksheet],
    items: list[RoadmapItem],
) -> list[ImportIssue]:
    """Return import findings; every finding leaves source data intact."""
    issues: list[ImportIssue] = []
    by_name = {ws.title: ws for ws in worksheets}

    required_fields = {
        "Roadmap": (2, 63, {1: "month", 3: "year", 4: "track", 5: "focus", 6: "mission", 7: "status"}),
        "Skill Matrix": (2, 32, {1: "skill", 2: "track", 5: "status"}),
        "Certifications": (2, 20, {1: "certification", 2: "status"}),
        "Projects": (2, 18, {1: "project id", 2: "project", 7: "status"}),
    }
    for sheet_name, (first, last, columns) in required_fields.items():
        ws = by_name.get(sheet_name)
        if ws is None:
            issues.append(_issue("error", "MISSING_SHEET", f"Required source sheet '{sheet_name}' is missing.", sheet_name))
            continue
        for row_number in range(first, last + 1):
            row_values = [ws.cell(row_number, col).value for col in columns]
            if not any(value is not None for value in row_values):
                continue
            for col, label in columns.items():
                if ws.cell(row_number, col).value in (None, ""):
                    cell = ws.cell(row_number, col)
                    issues.append(_issue(
                        "warning", "MISSING_REQUIRED_FIELD",
                        f"Row {row_number} has no {label}; the source row was retained.",
                        sheet_name, cell.coordinate,
                    ))

    # Exact duplicates inside an authoritative list can be errors. Duplicates
    # across sheets remain separate because the workbook uses parallel trackers.
    for sheet_name, col, first, last, label in (
        ("Roadmap", 1, 2, 63, "month"),
        ("Skill Matrix", 1, 2, 32, "skill"),
        ("Certifications", 1, 2, 20, "certification name"),
        ("Projects", 1, 2, 18, "project ID"),
        ("My Certifications", 1, 25, 28, "personal certification name"),
        ("Microsoft Track", 2, 44, 51, "Microsoft ladder certification"),
    ):
        ws = by_name.get(sheet_name)
        if ws is None:
            continue
        seen: dict[str, int] = {}
        for row_number in range(first, last + 1):
            value = ws.cell(row_number, col).value
            if value in (None, ""):
                continue
            key = str(value).strip().casefold()
            if key in seen:
                issues.append(_issue(
                    "warning", "DUPLICATE_SOURCE_KEY",
                    f"Duplicate {label} '{value}' also appears on row {seen[key]}; both rows were retained.",
                    sheet_name, ws.cell(row_number, col).coordinate,
                ))
            else:
                seen[key] = row_number

    for ws in worksheets:
        for row in ws.iter_rows():
            for cell in row:
                value = cell.value
                if isinstance(value, str) and MONTH_TEXT.fullmatch(value):
                    month = int(value[-2:])
                    if not 1 <= month <= 12:
                        issues.append(_issue(
                            "warning", "INVALID_MONTH",
                            f"'{value}' is not a valid YYYY-MM month; the original text was retained.",
                            ws.title, cell.coordinate,
                        ))
                if isinstance(value, str) and value.startswith("="):
                    refs = CELL_REF.findall(value.upper())
                    if any(col.upper() == cell.column_letter and int(row_num) == cell.row for col, row_num in refs):
                        issues.append(_issue(
                            "warning", "FORMULA_CIRCULAR_REFERENCE",
                            f"Formula in {cell.coordinate} refers to itself. Its formula and cached value were preserved.",
                            ws.title, cell.coordinate,
                        ))
                    cached = cached_sheets[ws.title][cell.coordinate].value
                    if isinstance(cached, str) and cached in ERROR_VALUES:
                        issues.append(_issue(
                            "warning", "FORMULA_CACHED_ERROR",
                            f"Formula has cached result {cached}; formula and cached value were preserved.",
                            ws.title, cell.coordinate,
                        ))

    roadmap = by_name.get("Roadmap")
    if roadmap is not None:
        periods = [roadmap.cell(r, 1).value for r in range(2, 64) if roadmap.cell(r, 1).value]
        if periods and all(isinstance(value, str) and MONTH_TEXT.fullmatch(value) for value in periods):
            if len(periods) != len(set(periods)):
                # Per-row duplicate details are already reported above.
                pass

    formula_count = sum(
        1 for ws in worksheets for row in ws.iter_rows()
        for cell in row if isinstance(cell.value, str) and cell.value.startswith("=")
    )
    issues.append(_issue(
        "info", "FORMULAS_STORED_NOT_EXECUTED",
        f"{formula_count} formulas were imported as source text with their saved cached values. The app does not execute workbook formulas.",
    ))
    issues.append(_issue(
        "info", "NO_STRUCTURED_DEPENDENCIES",
        "No prerequisite-ID field was found. Dependency guidance in prose was retained in each source record rather than converted into invented links.",
    ))
    issues.append(_issue(
        "info", "NO_DIFFICULTY_OR_ESTIMATES",
        "The workbook does not provide structured difficulty or estimated-hour fields; those values remain empty.",
    ))
    issues.append(_issue(
        "info", "NO_DEDICATED_LAB_SHEET",
        "No dedicated lab tracker sheet was found. Lab missions remain in their original mission, project, and learning-track records.",
    ))
    issues.append(_issue(
        "info", "SOURCE_CATEGORY_TERMS",
        "Track/category vocabularies vary between sheets, and some core roadmap tracks combine multiple domains. Labels remain source-specific; no category remapping was inferred.",
    ))
    issues.append(_issue(
        "info", "SOURCE_TIMELINES_AS_TEXT",
        "Roadmap periods and target windows are stored as text in the workbook. Their original forms are preserved instead of being coerced into dates.",
    ))

    wallet = by_name.get("My Certifications")
    if wallet is not None:
        blank_wallet_slots = sum(
            1 for row_number in range(5, 25)
            if wallet.cell(row_number, 1).value in (None, "")
            and wallet.cell(row_number, 6).value not in (None, "")
        )
        if blank_wallet_slots:
            issues.append(_issue(
                "info", "BLANK_CERTIFICATION_SLOTS",
                f"The personal certification wallet has {blank_wallet_slots} blank rows with default statuses. They were preserved in raw source rows and omitted from normalized certification items.",
                "My Certifications",
            ))

    microsoft = by_name.get("Microsoft Track")
    if microsoft is not None:
        mission_rows = [r for r in range(9, 41) if microsoft.cell(r, 1).value and microsoft.cell(r, 4).value]
        cached_total = cached_sheets["Microsoft Track"]["A5"].value if "Microsoft Track" in cached_sheets else None
        if microsoft["A5"].value == "=COUNTA(A9:A60)" and len(mission_rows) != cached_total:
            issues.append(_issue(
                "warning", "SUMMARY_RANGE_INCLUDES_SECTION_ROWS",
                f"The saved mission total is {cached_total}, while {len(mission_rows)} mission records are present; the formula range includes certification ladder headings and rows.",
                "Microsoft Track", "A5",
            ))

    dashboard = by_name.get("Dashboard")
    projects = by_name.get("Projects")
    if dashboard is not None and projects is not None:
        project_rows = [
            r for r in range(2, projects.max_row + 1)
            if projects.cell(r, 1).value and str(projects.cell(r, 1).value).startswith("P")
        ]
        if "G2:G12" in str(dashboard["E8"].value).replace("$", "") and len(project_rows) > 0:
            issues.append(_issue(
                "warning", "PROJECT_XP_RANGE_TRUNCATED",
                f"The Dashboard XP formula stops at Projects row 12, but {len(project_rows)} project records extend through row {max(project_rows)}.",
                "Dashboard", "E8",
            ))

    # Certification names intentionally recur between the core ladder, the
    # Microsoft ladder and the personal wallet. Keep those records distinct.
    certification_sources = {
        "Certifications": [by_name["Certifications"].cell(r, 1).value for r in range(2, 21)] if "Certifications" in by_name else [],
        "My Certifications": [by_name["My Certifications"].cell(r, 1).value for r in range(25, 29)] if "My Certifications" in by_name else [],
        "Microsoft Track": [by_name["Microsoft Track"].cell(r, 2).value for r in range(44, 52)] if "Microsoft Track" in by_name else [],
    }
    occurrences: dict[str, list[str]] = {}
    for source, names in certification_sources.items():
        for name in names:
            if not name:
                continue
            normalized = re.sub(r"\s+", " ", str(name)).strip().casefold()
            if normalized in {"custom future certification"}:
                continue
            occurrences.setdefault(normalized, []).append(source)
    overlaps = [name for name, sources in occurrences.items() if len(set(sources)) > 1]
    if overlaps:
        issues.append(_issue(
            "info", "CERTIFICATION_TRACK_OVERLAP",
            f"Certification names recur across independent sheets ({len(overlaps)} exact-name overlaps). Each source record remains separate.",
        ))

    # The status terms vary by sheet. Do not silently coerce them during v0.1.
    status_terms = sorted({
        str(item.status).strip() for item in items if item.status
    }, key=str.casefold)
    issues.append(_issue(
        "info", "SOURCE_STATUS_TERMS",
        "Source status labels are preserved verbatim: " + ", ".join(status_terms) + ".",
    ))

    return issues


def issue_to_dict(issue: ImportIssue) -> dict[str, Any]:
    """Serialize a validation issue for persistence."""
    return {
        "severity": issue.severity,
        "code": issue.code,
        "message": issue.message,
        "sheet": issue.sheet,
        "cell": issue.cell,
    }
