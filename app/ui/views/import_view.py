"""Workbook import and validation report page."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget


class ImportView(QWidget):
    def __init__(self, on_import):
        super().__init__()
        self.on_import = on_import
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(28, 24, 28, 24)
        self.layout.setSpacing(12)
        eyebrow = QLabel("PROJECT 25  /  SOURCE DATA")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Import & validation")
        title.setObjectName("pageTitle")
        self.summary = QLabel("No workbook imported.")
        self.summary.setObjectName("muted")
        self.button = QPushButton("Import Excel workbook…")
        self.button.setObjectName("primary")
        self.button.clicked.connect(self.on_import)
        self.sheet_table = QTableWidget(0, 3)
        self.sheet_table.setHorizontalHeaderLabels(["Source sheet", "Rows stored", "Cells stored"])
        self.sheet_table.setAlternatingRowColors(True)
        self.sheet_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.sheet_table.verticalHeader().setVisible(False)
        self.sheet_table.horizontalHeader().setStretchLastSection(True)
        self.issues = QTableWidget(0, 4)
        self.issues.setHorizontalHeaderLabels(["Severity", "Finding", "Source", "Details"])
        self.issues.setAlternatingRowColors(True)
        self.issues.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.issues.verticalHeader().setVisible(False)
        self.issues.horizontalHeader().setStretchLastSection(True)
        self.layout.addWidget(eyebrow)
        self.layout.addWidget(title)
        self.layout.addWidget(self.summary)
        self.layout.addWidget(self.button, 0)
        self.layout.addWidget(QLabel("Imported sheets"))
        self.layout.addWidget(self.sheet_table, 1)
        self.layout.addWidget(QLabel("Validation report"))
        self.layout.addWidget(self.issues, 2)

    def refresh(self, workbook, sheets: list, issues: list) -> None:
        if workbook is None:
            self.summary.setText("No workbook imported. The source workbook is never modified by this app.")
            self.sheet_table.setRowCount(0)
            self.issues.setRowCount(0)
            return
        self.summary.setText(
            f"{workbook['filename']} · {workbook['sheet_count']} sheets · "
            f"{workbook['source_row_count']:,} populated rows · "
            f"{workbook['source_cell_count']:,} populated cells · "
            f"{workbook['formula_count']} formulas · {workbook['item_count']:,} normalized records"
        )
        self.sheet_table.setRowCount(len(sheets))
        for row, sheet in enumerate(sheets):
            values = [sheet["sheet_name"], str(sheet["stored_rows"]), str(sheet["stored_cells"])]
            for col, value in enumerate(values):
                self.sheet_table.setItem(row, col, QTableWidgetItem(str(value)))
            self.sheet_table.setRowHeight(row, 28)

        self.issues.setRowCount(len(issues))
        for row, issue in enumerate(issues):
            source = ":".join(part for part in (issue["sheet_name"], issue["cell_reference"]) if part)
            values = [issue["severity"].upper(), issue["code"], source or "Workbook", issue["message"]]
            for col, value in enumerate(values):
                self.issues.setItem(row, col, QTableWidgetItem(str(value)))
            self.issues.setRowHeight(row, 48)
