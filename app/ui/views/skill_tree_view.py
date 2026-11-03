"""Interactive skill tree grouped by the workbook's own track taxonomy."""

from __future__ import annotations

import json

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models.roadmap import PROGRESS_STATUSES


class SkillTreeView(QWidget):
    """Browse skill nodes by source track and inspect their unlock state."""

    filters_changed = Signal()
    progress_edit_requested = Signal(str)
    prerequisite_review_requested = Signal(str, bool)

    TREE_HEADERS = ["Skill / branch", "Type", "Unlock state", "Progress", "Workbook timing"]

    def __init__(self) -> None:
        super().__init__()
        self.records_by_id: dict[str, dict] = {}
        self.current_item_id: str | None = None

        page = QVBoxLayout(self)
        page.setContentsMargins(28, 24, 28, 24)
        page.setSpacing(12)

        eyebrow = QLabel("PROJECT 25  /  SKILL TREE")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Skill tree")
        title.setObjectName("pageTitle")
        intro = QLabel(
            "Branches use the workbook's Track values. Unlock state follows explicit prerequisites; "
            "target ages and timeframes are shown as recorded."
        )
        intro.setObjectName("muted")
        intro.setWordWrap(True)
        page.addWidget(eyebrow)
        page.addWidget(title)
        page.addWidget(intro)

        filter_card = QFrame()
        filter_card.setObjectName("card")
        filters = QGridLayout(filter_card)
        filters.setContentsMargins(12, 10, 12, 10)
        filters.setHorizontalSpacing(8)
        filters.setVerticalSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search skills, tracks, tools, and prerequisites…")
        self.search.setClearButtonEnabled(True)
        self.branch_filter = self._combo("All workbook tracks")
        self.progress_filter = self._combo("All progress statuses")
        for status in PROGRESS_STATUSES:
            self.progress_filter.addItem(status, status)
        self.readiness_filter = self._combo("All unlock states")
        for state in ("Available", "Locked", "Needs review"):
            self.readiness_filter.addItem(state, state)
        self.reset_button = QPushButton("Reset filters")
        self.reset_button.clicked.connect(self.reset_filters)
        filters.addWidget(self.search, 0, 0, 1, 3)
        filters.addWidget(self.branch_filter, 0, 3)
        filters.addWidget(self.progress_filter, 0, 4)
        filters.addWidget(self.readiness_filter, 0, 5)
        filters.addWidget(self.reset_button, 0, 6)
        filters.setColumnStretch(0, 1)
        filters.setColumnStretch(1, 1)
        filters.setColumnStretch(2, 1)
        page.addWidget(filter_card)

        self.summary = QLabel("No skill data loaded.")
        self.summary.setObjectName("muted")
        page.addWidget(self.summary)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(self.TREE_HEADERS)
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.tree.setEditTriggers(QTreeWidget.EditTrigger.NoEditTriggers)
        self.tree.setIndentation(18)
        self.tree.setColumnWidth(1, 118)
        self.tree.setColumnWidth(2, 120)
        self.tree.setColumnWidth(3, 132)
        self.tree.setColumnWidth(4, 180)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.itemSelectionChanged.connect(self._selection_changed)
        self.tree.itemDoubleClicked.connect(self._edit_current_progress)

        details_scroll = QScrollArea()
        details_scroll.setWidgetResizable(True)
        details_scroll.setMinimumWidth(300)
        details_scroll.setWidget(self._build_details())
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.tree)
        splitter.addWidget(details_scroll)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([790, 330])
        page.addWidget(splitter, 1)

        self.count_label = QLabel("No skills shown.")
        self.count_label.setObjectName("muted")
        page.addWidget(self.count_label)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(180)
        self._search_timer.timeout.connect(self.filters_changed.emit)
        self.search.textChanged.connect(lambda _text: self._search_timer.start())
        for control in (self.branch_filter, self.progress_filter, self.readiness_filter):
            control.currentIndexChanged.connect(self.filters_changed.emit)

    @staticmethod
    def _combo(first_label: str) -> QComboBox:
        combo = QComboBox()
        combo.addItem(first_label, "")
        return combo

    def _build_details(self) -> QWidget:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        self.detail_title = QLabel("Select a skill")
        self.detail_title.setStyleSheet("font-size: 14pt; font-weight: 650; color: #f3f4f6;")
        self.detail_title.setWordWrap(True)
        self.detail_branch = self._detail_label()
        self.detail_readiness = self._detail_label()
        self.detail_progress = self._detail_label()
        self.detail_timing = self._detail_label()
        self.detail_reward = self._detail_label()
        self.detail_prerequisites = self._detail_label()
        self.detail_description = self._detail_label()
        self.detail_resources = self._detail_label()
        self.detail_source_notes = self._detail_label()
        self.detail_progress_notes = self._detail_label()

        for caption, field in (
            ("SKILL / SOURCE", self.detail_title),
            ("WORKBOOK TRACK", self.detail_branch),
            ("UNLOCK STATE", self.detail_readiness),
            ("PROGRESS", self.detail_progress),
            ("WORKBOOK TIMING", self.detail_timing),
            ("SOURCE XP", self.detail_reward),
            ("PREREQUISITES", self.detail_prerequisites),
            ("DESCRIPTION", self.detail_description),
            ("RESOURCES / PORTFOLIO", self.detail_resources),
            ("SOURCE NOTES", self.detail_source_notes),
            ("LOCAL PROGRESS NOTES", self.detail_progress_notes),
        ):
            if field is not self.detail_title:
                label = QLabel(caption)
                label.setObjectName("eyebrow")
                layout.addWidget(label)
            layout.addWidget(field)

        self.verify_button = QPushButton("Verify source prerequisites")
        self.verify_button.clicked.connect(self._toggle_prerequisite_review)
        self.progress_button = QPushButton("Update progress")
        self.progress_button.setObjectName("primary")
        self.progress_button.clicked.connect(self._edit_current_progress)
        layout.addStretch(1)
        layout.addWidget(self.verify_button)
        layout.addWidget(self.progress_button)
        return card

    @staticmethod
    def _detail_label() -> QLabel:
        label = QLabel("—")
        label.setObjectName("muted")
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    def filter_values(self) -> dict[str, str]:
        return {
            "query": self.search.text(),
            "branch": self.branch_filter.currentData() or "",
            "progress_status": self.progress_filter.currentData() or "",
            "readiness": self.readiness_filter.currentData() or "",
        }

    def reset_filters(self) -> None:
        self.search.clear()
        for control in (self.branch_filter, self.progress_filter, self.readiness_filter):
            control.setCurrentIndex(0)
        self.filters_changed.emit()

    def refresh(self, data: dict | None = None) -> None:
        data = data or {"items": [], "branches": [], "branch_options": [], "counts": {}}
        self._refresh_branch_options(data.get("branch_options", []))
        counts = data.get("counts", {})
        self.summary.setText(
            f"{counts.get('total', 0)} skill nodes across {counts.get('branches', 0)} workbook tracks  ·  "
            f"{counts.get('available', 0)} available  ·  {counts.get('in_progress', 0)} in progress  ·  "
            f"{counts.get('completed', 0)} completed  ·  {counts.get('locked', 0)} locked  ·  "
            f"{counts.get('needs_review', 0)} need review"
        )

        self.records_by_id = {item["item_id"]: item for item in data.get("items", [])}
        self.tree.clear()
        for branch in data.get("branches", []):
            branch_items = branch["items"]
            root = QTreeWidgetItem([
                f"{branch['name']}  ·  {len(branch_items)}",
                "Workbook track",
                "",
                "",
                "",
            ])
            root.setFont(0, self._bold_font())
            root.setForeground(0, QColor("#dfe2e7"))
            root.setFlags(root.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.tree.addTopLevelItem(root)
            root.setExpanded(True)
            for record in branch_items:
                row = QTreeWidgetItem([
                    record["name"],
                    record["skill_kind"],
                    record["skill_readiness"],
                    f"{record['progress_status']} · {record['progress_percent']}%",
                    f"{record['skill_timing_label']}: {record['skill_timing']}",
                ])
                row.setData(0, Qt.ItemDataRole.UserRole, record["item_id"])
                row.setToolTip(0, record.get("description") or record["name"])
                row.setToolTip(2, self._readiness_text(record))
                color = self._state_color(record)
                for column in range(5):
                    row.setForeground(column, color)
                if record["progress_status"] == "Completed":
                    row.setFont(0, self._bold_font())
                root.addChild(row)

        if self.records_by_id:
            self.count_label.setText(f"{len(self.records_by_id):,} skill nodes shown.")
            selected_id = (
                self.current_item_id
                if self.current_item_id in self.records_by_id else next(iter(self.records_by_id))
            )
            self._select_item(selected_id)
        else:
            self.count_label.setText("No skill nodes match these filters.")
            self.current_item_id = None
            self._show_item(None)

    def _refresh_branch_options(self, options: list[str]) -> None:
        selected = self.branch_filter.currentData() or ""
        self.branch_filter.blockSignals(True)
        self.branch_filter.clear()
        self.branch_filter.addItem("All workbook tracks", "")
        for option in options:
            self.branch_filter.addItem(option, option)
        index = self.branch_filter.findData(selected)
        self.branch_filter.setCurrentIndex(max(index, 0))
        self.branch_filter.blockSignals(False)

    @staticmethod
    def _bold_font() -> QFont:
        font = QFont()
        font.setBold(True)
        return font

    @staticmethod
    def _state_color(record: dict) -> QColor:
        if record["progress_status"] == "Completed":
            return QColor("#91cda9")
        if record["skill_readiness"] == "Locked":
            return QColor("#e2b76c")
        if record["skill_readiness"] == "Needs review":
            return QColor("#e5a46b")
        return QColor("#d9dde3")

    @staticmethod
    def _readiness_text(record: dict) -> str:
        messages = []
        if record.get("skill_missing_prerequisites"):
            names = ", ".join(item["name"] for item in record["skill_missing_prerequisites"])
            messages.append(f"Waiting for: {names}")
        messages.extend(record.get("skill_unresolved_prerequisites", []))
        if record.get("skill_has_prerequisite_note"):
            state = "reviewed" if record.get("skill_prerequisites_verified") else "needs review"
            messages.append(f"Source prerequisite note {state}.")
        elif not record.get("skill_prerequisites") and not record.get("skill_unresolved_prerequisites"):
            messages.append("No prerequisite link is recorded in the workbook.")
        elif not record.get("skill_missing_prerequisites") and not record.get("skill_unresolved_prerequisites"):
            messages.append("All recorded prerequisites are complete.")
        return "\n".join(messages)

    def _select_item(self, item_id: str) -> None:
        for root_index in range(self.tree.topLevelItemCount()):
            root = self.tree.topLevelItem(root_index)
            for child_index in range(root.childCount()):
                child = root.child(child_index)
                if child.data(0, Qt.ItemDataRole.UserRole) == item_id:
                    self.tree.setCurrentItem(child)
                    self.current_item_id = item_id
                    self._show_item(self.records_by_id.get(item_id))
                    return

    def _selection_changed(self) -> None:
        selected = self.tree.currentItem()
        if selected is None:
            return
        item_id = selected.data(0, Qt.ItemDataRole.UserRole)
        if item_id:
            self.current_item_id = str(item_id)
            self._show_item(self.records_by_id.get(self.current_item_id))

    def _show_item(self, record: dict | None) -> None:
        has_record = record is not None
        self.progress_button.setEnabled(has_record)
        self.verify_button.setEnabled(bool(record and record.get("skill_has_prerequisite_note")))
        if not record:
            for label in (
                self.detail_title,
                self.detail_branch,
                self.detail_readiness,
                self.detail_progress,
                self.detail_timing,
                self.detail_reward,
                self.detail_prerequisites,
                self.detail_description,
                self.detail_resources,
                self.detail_source_notes,
                self.detail_progress_notes,
            ):
                label.setText("")
            self.detail_title.setText("Select a skill")
            self.verify_button.setText("Verify source prerequisites")
            return

        self.detail_title.setText(record["name"])
        self.detail_branch.setText(f"{record['skill_kind']} · {record['skill_branch'] or 'Track not specified'}")
        self.detail_readiness.setText(
            f"{record['skill_readiness']}\n{self._readiness_text(record)}"
        )
        self.detail_progress.setText(
            f"{record['progress_status']} · {record['progress_percent']}%\n"
            f"Source status: {record.get('status') or 'Not specified'}\n"
            f"Started: {record.get('progress_date_started') or 'Not recorded'} · "
            f"Completed: {record.get('progress_date_completed') or 'Not recorded'}"
        )
        self.detail_timing.setText(
            f"{record['skill_timing_label']}: {record['skill_timing']}\n"
            f"Source: {record['source_sheet']} · row {record['source_row']}"
        )
        if record.get("xp_reward") is None:
            self.detail_reward.setText("No XP reward specified in the workbook.")
        else:
            self.detail_reward.setText(
                f"{int(record['xp_reward']):,} source XP · "
                f"currently awarded: {int(record.get('xp_awarded') or 0):,} XP"
            )

        prereq_lines = []
        for prerequisite in record.get("skill_prerequisites", []):
            state = "Complete" if prerequisite["complete"] else prerequisite["progress_status"]
            prereq_lines.append(f"{prerequisite['name']} · {state}")
        prereq_lines.extend(record.get("skill_unresolved_prerequisites", []))
        if record.get("prerequisite_notes"):
            prereq_lines.append(str(record["prerequisite_notes"]))
        self.detail_prerequisites.setText("\n".join(prereq_lines) or "No prerequisite links are recorded in the workbook.")
        self.detail_description.setText(record.get("description") or "No description recorded in the workbook.")
        self.detail_resources.setText(self._resource_text(record.get("resources_json")))
        self.detail_source_notes.setText(record.get("notes") or "No additional source notes.")
        self.detail_progress_notes.setText(record.get("progress_note") or "No local progress note recorded.")
        if not record.get("skill_has_prerequisite_note"):
            self.verify_button.setText("No source prerequisite note")
        else:
            self.verify_button.setText(
                "Revoke prerequisite verification"
                if record.get("skill_prerequisites_verified") else "I verified these prerequisites"
            )

    @staticmethod
    def _resource_text(raw: str | None) -> str:
        if not raw:
            return "No resources recorded in the workbook."
        try:
            resources = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return str(raw)
        values = [str(value).strip() for value in resources if str(value).strip()]
        return "\n".join(values) if values else "No resources recorded in the workbook."

    def _edit_current_progress(self, _item=None, _column: int = 0) -> None:
        if self.current_item_id:
            self.progress_edit_requested.emit(self.current_item_id)

    def _toggle_prerequisite_review(self) -> None:
        record = self.records_by_id.get(self.current_item_id or "")
        if record and record.get("skill_has_prerequisite_note"):
            self.prerequisite_review_requested.emit(
                record["item_id"], not bool(record.get("skill_prerequisites_verified"))
            )
