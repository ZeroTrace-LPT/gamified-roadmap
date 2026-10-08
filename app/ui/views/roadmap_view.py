"""Read-only core roadmap table for the v0.1 foundation release."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget


class RoadmapView(QWidget):
    HEADERS = ["Month", "Phase", "Track", "Focus", "Monthly mission", "Status", "XP earned"]

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        eyebrow = QLabel("PROJECT 25  /  ROADMAP")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Monthly progression")
        title.setObjectName("pageTitle")
        intro = QLabel("The original 2026–2031 mission sequence is shown with its source wording and status.")
        intro.setObjectName("muted")
        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addWidget(intro)
        layout.addWidget(self.table, 1)

    def refresh(self, records: list) -> None:
        self.table.setRowCount(len(records))
        for row_index, record in enumerate(records):
            values = [
                record["target_period"], record["phase"], record["category"],
                record["name"], record["description"], record["status"],
                str(record["xp_earned"] if record["xp_earned"] is not None else "—"),
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row_index, column, cell)
            self.table.setRowHeight(row_index, 64)
