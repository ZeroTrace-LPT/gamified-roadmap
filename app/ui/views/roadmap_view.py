"""Searchable, source-aware roadmap table and timeline views."""

from __future__ import annotations

import json
import re

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models.roadmap import PROGRESS_STATUSES


class RoadmapView(QWidget):
    """Display every normalized record with source and local progress side by side."""

    filters_changed = Signal()
    progress_edit_requested = Signal(str)

    TABLE_HEADERS = [
        "Target", "Roadmap item", "Type", "Track / phase", "Local progress",
    ]

    def __init__(self):
        super().__init__()
        self.records_by_id: dict[str, dict] = {}
        self.current_item_id: str | None = None

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(28, 24, 28, 24)
        self.layout.setSpacing(12)
        eyebrow = QLabel("PROJECT 25  /  ROADMAP ENGINE")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Roadmap progression")
        title.setObjectName("pageTitle")
        intro = QLabel(
            "Search the workbook-backed plan, compare source status with your local progress, and view items by month, year, or phase."
        )
        intro.setObjectName("muted")
        intro.setWordWrap(True)
        self.layout.addWidget(eyebrow)
        self.layout.addWidget(title)
        self.layout.addWidget(intro)

        filter_frame = QFrame()
        filter_frame.setObjectName("card")
        filters = QGridLayout(filter_frame)
        filters.setContentsMargins(12, 10, 12, 10)
        filters.setHorizontalSpacing(8)
        filters.setVerticalSpacing(8)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search names, notes, technologies, resources…")
        self.search.setClearButtonEnabled(True)
        self.type_filter = self._combo("All item types")
        self.progress_filter = self._combo("All local statuses")
        for status in PROGRESS_STATUSES:
            self.progress_filter.addItem(status, status)
        self.phase_filter = self._combo("All phases")
        self.category_filter = self._combo("All categories")
        self.source_filter = self._combo("All workbook statuses")
        self.year_filter = self._combo("All target years")
        self.group_filter = self._combo("Timeline by month")
        for label, mode in (
            ("Timeline by month", "Month"),
            ("Timeline by year", "Year"),
            ("Timeline by phase", "Phase"),
            ("Source sheet order", "Source"),
        ):
            self.group_filter.addItem(label, mode)
        self.reset_button = QPushButton("Reset filters")
        self.reset_button.clicked.connect(self.reset_filters)

        filters.addWidget(self.search, 0, 0, 1, 3)
        filters.addWidget(self.type_filter, 0, 3)
        filters.addWidget(self.progress_filter, 0, 4)
        filters.addWidget(self.phase_filter, 1, 0)
        filters.addWidget(self.category_filter, 1, 1)
        filters.addWidget(self.source_filter, 1, 2)
        filters.addWidget(self.year_filter, 1, 3)
        filters.addWidget(self.group_filter, 1, 4)
        filters.addWidget(self.reset_button, 0, 5, 2, 1)
        filters.setColumnStretch(0, 1)
        filters.setColumnStretch(1, 1)
        filters.setColumnStretch(2, 1)
        filters.setColumnStretch(5, 0)
        self.layout.addWidget(filter_frame)

        self.tabs = QTabWidget()
        self.table = QTableWidget(0, len(self.TABLE_HEADERS))
        self.table.setHorizontalHeaderLabels(self.TABLE_HEADERS)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 92)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for column, width in ((2, 125), (3, 165), (4, 145)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(column, width)
        self.timeline = QTreeWidget()
        self.timeline.setHeaderLabels(["Target", "Roadmap item", "Local progress"])
        self.timeline.setAlternatingRowColors(True)
        self.timeline.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.timeline.setRootIsDecorated(True)
        self.timeline.setUniformRowHeights(True)
        self.timeline.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.timeline.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.timeline.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tabs.addTab(self.table, "Roadmap list")
        self.tabs.addTab(self.timeline, "Timeline")

        self.details = self._build_details_panel()
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.tabs)
        splitter.addWidget(self.details)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([780, 330])
        self.layout.addWidget(splitter, 1)

        self.count_label = QLabel("No roadmap imported.")
        self.count_label.setObjectName("muted")
        self.layout.addWidget(self.count_label)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(180)
        self._search_timer.timeout.connect(self.filters_changed.emit)
        self.search.textChanged.connect(lambda _text: self._search_timer.start())
        for combo in (
            self.type_filter, self.progress_filter, self.phase_filter,
            self.category_filter, self.source_filter, self.year_filter, self.group_filter,
        ):
            combo.currentIndexChanged.connect(self.filters_changed.emit)
        self.table.itemSelectionChanged.connect(self._table_selection_changed)
        self.timeline.itemSelectionChanged.connect(self._timeline_selection_changed)
        self.edit_button.clicked.connect(self._edit_selected)

    @staticmethod
    def _combo(placeholder: str) -> QComboBox:
        combo = QComboBox()
        combo.addItem(placeholder, "")
        combo.setMinimumContentsLength(11)
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        return combo

    def _build_details_panel(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        panel = QFrame()
        panel.setObjectName("card")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 15, 16, 15)
        layout.setSpacing(10)
        self.detail_title = QLabel("Select a roadmap item")
        self.detail_title.setWordWrap(True)
        self.detail_title.setStyleSheet("font-size: 15pt; font-weight: 650; color: #f3f4f6;")
        self.detail_origin = QLabel("")
        self.detail_origin.setObjectName("eyebrow")
        self.detail_origin.setWordWrap(True)
        self.detail_status = QLabel("")
        self.detail_status.setWordWrap(True)
        self.detail_progress = QProgressBar()
        self.detail_progress.setRange(0, 100)
        self.detail_dates = self._detail_label()
        self.detail_description = self._detail_label()
        self.detail_prerequisites = self._detail_label()
        self.detail_resources = self._detail_label()
        self.detail_source_notes = self._detail_label()
        self.detail_local_note = self._detail_label()
        self.edit_button = QPushButton("Update progress")
        self.edit_button.setObjectName("primary")
        self.edit_button.setEnabled(False)
        layout.addWidget(self.detail_title)
        layout.addWidget(self.detail_origin)
        layout.addWidget(self.detail_status)
        layout.addWidget(self.detail_progress)
        dates_caption = QLabel("LOCAL DATES")
        dates_caption.setObjectName("eyebrow")
        layout.addWidget(dates_caption)
        layout.addWidget(self.detail_dates)
        for label, widget in (
            ("Description", self.detail_description),
            ("Prerequisite notes", self.detail_prerequisites),
            ("Resources", self.detail_resources),
            ("Workbook notes", self.detail_source_notes),
            ("Local progress note", self.detail_local_note),
        ):
            caption = QLabel(label.upper())
            caption.setObjectName("eyebrow")
            layout.addWidget(caption)
            layout.addWidget(widget)
        layout.addStretch(1)
        layout.addWidget(self.edit_button)
        scroll.setWidget(panel)
        return scroll

    @staticmethod
    def _detail_label() -> QLabel:
        label = QLabel("—")
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setObjectName("muted")
        return label

    @staticmethod
    def _replace_options(combo: QComboBox, values: list[str], placeholder: str, labels: dict[str, str] | None = None) -> None:
        previous = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(placeholder, "")
        for value in values:
            combo.addItem((labels or {}).get(value, value), value)
        index = combo.findData(previous)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

    def set_filter_options(self, options: dict[str, list[str]]) -> None:
        type_labels = {value: value.replace("_", " ").title() for value in options.get("types", [])}
        self._replace_options(self.type_filter, options.get("types", []), "All item types", type_labels)
        self._replace_options(self.phase_filter, options.get("phases", []), "All phases")
        self._replace_options(self.category_filter, options.get("categories", []), "All categories")
        self._replace_options(self.source_filter, options.get("source_statuses", []), "All workbook statuses")
        self._replace_options(self.year_filter, options.get("years", []), "All target years")

    def filter_values(self) -> dict[str, str]:
        return {
            "query": self.search.text(),
            "item_type": str(self.type_filter.currentData() or ""),
            "progress_status": str(self.progress_filter.currentData() or ""),
            "phase": str(self.phase_filter.currentData() or ""),
            "category": str(self.category_filter.currentData() or ""),
            "source_status": str(self.source_filter.currentData() or ""),
            "year": str(self.year_filter.currentData() or ""),
            "sort_by": str(self.group_filter.currentData() or "Month"),
        }

    def reset_filters(self) -> None:
        self._search_timer.stop()
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        for combo in (
            self.type_filter, self.progress_filter, self.phase_filter,
            self.category_filter, self.source_filter, self.year_filter,
        ):
            combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
        self.group_filter.blockSignals(True)
        self.group_filter.setCurrentIndex(0)
        self.group_filter.blockSignals(False)
        self.filters_changed.emit()

    def refresh(self, records: list[dict], selected_item_id: str | None = None) -> None:
        previous = selected_item_id or self.current_item_id
        self.records_by_id = {record["item_id"]: record for record in records}
        self.table.blockSignals(True)
        self.table.setRowCount(len(records))
        for row_index, record in enumerate(records):
            values = [
                record.get("target_period") or "—",
                record["name"],
                record["item_type"].replace("_", " ").title(),
                " · ".join(value for value in (record.get("category"), record.get("phase")) if value) or "—",
                f"{record['progress_status']} · {record['progress_percent']}%",
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                cell.setToolTip(str(value))
                if column == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, record["item_id"])
                self.table.setItem(row_index, column, cell)
            self.table.setRowHeight(row_index, 50)
        self.table.blockSignals(False)
        self._populate_timeline(records)
        self.count_label.setText(f"{len(records):,} roadmap items shown")

        if previous in self.records_by_id:
            self.select_item(previous)
        elif records:
            self.select_item(records[0]["item_id"])
        else:
            self.current_item_id = None
            self._show_details(None)

    def _populate_timeline(self, records: list[dict]) -> None:
        self.timeline.blockSignals(True)
        self.timeline.clear()
        mode = self.group_filter.currentData() or "Month"
        groups: dict[str, list[dict]] = {}
        for record in records:
            target = (record.get("target_period") or "").strip()
            if mode == "Phase":
                label = record.get("phase") or "Phase not specified in source"
            elif mode == "Year":
                match = re.match(r"^(\d{4})", target)
                label = match.group(1) if match else "Source-defined timing"
            elif mode == "Source":
                label = record["source_sheet"]
            else:
                label = target if re.fullmatch(r"\d{4}-\d{2}", target) else "Source-defined timing"
            groups.setdefault(label, []).append(record)

        def group_order(value: str) -> tuple[int, str]:
            if value == "Source-defined timing" or value == "Phase not specified in source":
                return (1, value.casefold())
            return (0, value.casefold())

        for label in sorted(groups, key=group_order):
            group = QTreeWidgetItem([label, f"{len(groups[label])} items", ""])
            group.setFlags(group.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.timeline.addTopLevelItem(group)
            for record in groups[label]:
                child = QTreeWidgetItem([
                    record.get("target_period") or "Unscheduled",
                    record["name"],
                    f"{record['progress_status']} · {record['progress_percent']}%",
                ])
                child.setData(0, Qt.ItemDataRole.UserRole, record["item_id"])
                group.addChild(child)
            group.setExpanded(True)
        self.timeline.blockSignals(False)

    def select_item(self, item_id: str) -> None:
        self.current_item_id = item_id
        self._show_details(self.records_by_id.get(item_id))
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).data(Qt.ItemDataRole.UserRole) == item_id:
                self.table.selectRow(row)
                self.table.blockSignals(False)
                break
        else:
            self.table.blockSignals(False)
        self.timeline.blockSignals(True)
        for group_index in range(self.timeline.topLevelItemCount()):
            group = self.timeline.topLevelItem(group_index)
            for child_index in range(group.childCount()):
                child = group.child(child_index)
                if child.data(0, Qt.ItemDataRole.UserRole) == item_id:
                    self.timeline.setCurrentItem(child)
                    self.timeline.blockSignals(False)
                    return
        self.timeline.blockSignals(False)

    def _table_selection_changed(self) -> None:
        selected = self.table.selectedItems()
        if not selected:
            return
        item_id = self.table.item(selected[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        if item_id in self.records_by_id:
            self.current_item_id = item_id
            self._show_details(self.records_by_id[item_id])

    def _timeline_selection_changed(self) -> None:
        selected = self.timeline.selectedItems()
        if not selected:
            return
        item_id = selected[0].data(0, Qt.ItemDataRole.UserRole)
        if item_id in self.records_by_id:
            self.current_item_id = item_id
            self._show_details(self.records_by_id[item_id])
            self.table.blockSignals(True)
            for row in range(self.table.rowCount()):
                if self.table.item(row, 0).data(Qt.ItemDataRole.UserRole) == item_id:
                    self.table.selectRow(row)
                    break
            self.table.blockSignals(False)

    def _show_details(self, record: dict | None) -> None:
        self.edit_button.setEnabled(record is not None)
        if record is None:
            self.detail_title.setText("No matching roadmap items")
            self.detail_origin.setText("")
            self.detail_status.setText("")
            self.detail_progress.setValue(0)
            self.detail_progress.setFormat("0%")
            self.detail_dates.setText("—")
            for label in (
                self.detail_description, self.detail_prerequisites, self.detail_resources,
                self.detail_source_notes, self.detail_local_note,
            ):
                label.setText("—")
            return

        self.detail_title.setText(record["name"])
        origin = f"{record['source_sheet']} · row {record['source_row']}"
        target = record.get("target_period") or "No timeline value in source"
        phase = record.get("phase") or "No phase value in source"
        category = record.get("category") or "No category value in source"
        self.detail_origin.setText(f"{origin}\n{target} · {phase} · {category}")
        source_status = record.get("status") or "Blank in source"
        self.detail_status.setText(
            f"Workbook status: {source_status}\n"
            f"Local status: {record['progress_status']} · {record['progress_percent']}%"
        )
        self.detail_progress.setValue(record["progress_percent"])
        self.detail_progress.setFormat(f"{record['progress_percent']}%")
        started = record.get("progress_date_started") or "Not recorded"
        completed = record.get("progress_date_completed") or "Not recorded"
        self.detail_dates.setText(f"Started: {started}\nCompleted: {completed}")
        self.detail_description.setText(record.get("description") or "No description recorded in source.")
        self.detail_prerequisites.setText(
            record.get("prerequisite_notes") or "No structured prerequisite note recorded in source."
        )
        resources = record.get("resources_json") or "[]"
        try:
            resources = json.loads(resources) if isinstance(resources, str) else resources
        except json.JSONDecodeError:
            resources = [str(resources)]
        self.detail_resources.setText("\n".join(str(value) for value in resources) or "No resources recorded in source.")
        self.detail_source_notes.setText(record.get("notes") or "No source notes.")
        self.detail_local_note.setText(record.get("progress_note") or "No local note.")

    def _edit_selected(self) -> None:
        if self.current_item_id:
            self.progress_edit_requested.emit(self.current_item_id)
