"""Quest board for the source-backed cybersecurity roadmap."""

from __future__ import annotations

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
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models.roadmap import PROGRESS_STATUSES
from app.quests.rules import QUEST_FILTERS


class QuestView(QWidget):
    """Search and track quests derived from workbook objectives."""

    filters_changed = Signal()
    progress_edit_requested = Signal(str)
    prerequisite_review_requested = Signal(str, bool)

    TABLE_HEADERS = ["Quest", "Quest class", "Source priority", "Readiness", "Progress", "XP reward"]

    def __init__(self):
        super().__init__()
        self.records_by_id: dict[str, dict] = {}
        self.current_item_id: str | None = None

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(28, 24, 28, 24)
        self.layout.setSpacing(12)

        eyebrow = QLabel("PROJECT 25  /  QUEST BOARD")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Quest board")
        title.setObjectName("pageTitle")
        intro = QLabel(
            "Workbook objectives become quests. Recommendations respect roadmap order, "
            "recorded dependencies, and prerequisite notes."
        )
        intro.setObjectName("muted")
        intro.setWordWrap(True)
        self.layout.addWidget(eyebrow)
        self.layout.addWidget(title)
        self.layout.addWidget(intro)

        self.recommendation_card = QFrame()
        self.recommendation_card.setObjectName("card")
        recommendation_layout = QVBoxLayout(self.recommendation_card)
        recommendation_layout.setContentsMargins(16, 11, 16, 11)
        recommendation_layout.setSpacing(4)
        recommendation_heading = QLabel("RECOMMENDED NEXT QUEST")
        recommendation_heading.setObjectName("eyebrow")
        self.recommendation_title = QLabel("Import a workbook to generate quests.")
        self.recommendation_title.setStyleSheet("font-size: 13pt; font-weight: 650; color: #f3f4f6;")
        self.recommendation_reason = QLabel("")
        self.recommendation_reason.setObjectName("muted")
        self.recommendation_reason.setWordWrap(True)
        recommendation_layout.addWidget(recommendation_heading)
        recommendation_layout.addWidget(self.recommendation_title)
        recommendation_layout.addWidget(self.recommendation_reason)
        self.layout.addWidget(self.recommendation_card)

        filter_frame = QFrame()
        filter_frame.setObjectName("card")
        filters = QGridLayout(filter_frame)
        filters.setContentsMargins(12, 10, 12, 10)
        filters.setHorizontalSpacing(8)
        filters.setVerticalSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search quests, source notes, phases, and priorities…")
        self.search.setClearButtonEnabled(True)
        self.type_filter = self._combo("All quest types")
        for label in QUEST_FILTERS:
            if label != "All quest types":
                self.type_filter.addItem(label, label)
        self.progress_filter = self._combo("All progress statuses")
        for status in PROGRESS_STATUSES:
            self.progress_filter.addItem(status, status)
        self.readiness_filter = self._combo("All prerequisite states")
        for value in ("Available", "Needs review", "Locked"):
            self.readiness_filter.addItem(value, value)
        self.reset_button = QPushButton("Reset filters")
        self.reset_button.clicked.connect(self.reset_filters)
        filters.addWidget(self.search, 0, 0, 1, 3)
        filters.addWidget(self.type_filter, 0, 3)
        filters.addWidget(self.progress_filter, 0, 4)
        filters.addWidget(self.readiness_filter, 0, 5)
        filters.addWidget(self.reset_button, 0, 6)
        filters.setColumnStretch(0, 1)
        filters.setColumnStretch(1, 1)
        filters.setColumnStretch(2, 1)
        self.layout.addWidget(filter_frame)

        self.summary = QLabel("No quest data loaded.")
        self.summary.setObjectName("muted")
        self.layout.addWidget(self.summary)

        self.table = QTableWidget(0, len(self.TABLE_HEADERS))
        self.table.setHorizontalHeaderLabels(self.TABLE_HEADERS)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column, width in ((1, 158), (2, 118), (3, 120), (4, 130), (5, 82)):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(column, width)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.doubleClicked.connect(self._edit_current_progress)

        detail_scroll = QScrollArea()
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setMinimumWidth(285)
        detail_scroll.setWidget(self._build_details())
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.table)
        splitter.addWidget(detail_scroll)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([790, 310])
        self.layout.addWidget(splitter, 1)

        self.count_label = QLabel("No quests shown.")
        self.count_label.setObjectName("muted")
        self.layout.addWidget(self.count_label)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(180)
        self._search_timer.timeout.connect(self.filters_changed.emit)
        self.search.textChanged.connect(lambda _text: self._search_timer.start())
        for combo in (self.type_filter, self.progress_filter, self.readiness_filter):
            combo.currentIndexChanged.connect(self.filters_changed.emit)

    @staticmethod
    def _combo(first_label: str) -> QComboBox:
        combo = QComboBox()
        combo.addItem(first_label, "")
        return combo

    def _build_details(self) -> QWidget:
        container = QFrame()
        container.setObjectName("card")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        self.detail_title = QLabel("Select a quest")
        self.detail_title.setStyleSheet("font-size: 14pt; font-weight: 650; color: #f3f4f6;")
        self.detail_title.setWordWrap(True)
        self.detail_origin = self._detail_label()
        self.detail_readiness = self._detail_label()
        self.detail_status = self._detail_label()
        self.detail_reward = self._detail_label()
        self.detail_prerequisites = self._detail_label()
        self.detail_description = self._detail_label()
        self.detail_notes = self._detail_label()
        self.detail_progress_note = self._detail_label()

        for caption, field in (
            ("QUEST / SOURCE", self.detail_title),
            ("TYPE · TRACK · TARGET", self.detail_origin),
            ("PREREQUISITE STATE", self.detail_readiness),
            ("PROGRESS", self.detail_status),
            ("SOURCE XP REWARD", self.detail_reward),
            ("PREREQUISITES", self.detail_prerequisites),
            ("DESCRIPTION", self.detail_description),
            ("SOURCE NOTES", self.detail_notes),
            ("LOCAL PROGRESS NOTES", self.detail_progress_note),
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
        return container

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
            "quest_type": self.type_filter.currentData() or "",
            "progress_status": self.progress_filter.currentData() or "",
            "readiness": self.readiness_filter.currentData() or "",
        }

    def reset_filters(self) -> None:
        self.search.clear()
        for combo in (self.type_filter, self.progress_filter, self.readiness_filter):
            combo.setCurrentIndex(0)
        self.filters_changed.emit()

    def refresh(self, board: dict | None = None) -> None:
        board = board or {"items": [], "recommendations": [], "counts": {}}
        recommendations = board.get("recommendations", [])
        if recommendations:
            mission = recommendations[0]
            quest_class = self._quest_class_text(mission)
            reward = (
                f" · +{int(mission['xp_reward']):,} source XP"
                if mission.get("xp_reward") is not None else " · no source XP reward"
            )
            self.recommendation_title.setText(f"{mission['name']}  ·  {quest_class}{reward}")
            context = " · ".join(value for value in (
                mission.get("target_period"), mission.get("phase"), mission.get("category")
            ) if value)
            reason = mission.get("recommendation_reason") or "Next available source objective."
            self.recommendation_reason.setText(" · ".join(value for value in (reason, context) if value))
        else:
            self.recommendation_title.setText("No ready quest is available.")
            self.recommendation_reason.setText(
                "Review source prerequisite notes, complete earlier dependencies, or import your roadmap."
            )

        counts = board.get("counts", {})
        self.summary.setText(
            f"{counts.get('available', 0)} ready  ·  "
            f"{counts.get('in_progress', 0)} in progress  ·  "
            f"{counts.get('needs_review', 0)} need prerequisite review  ·  "
            f"{counts.get('locked', 0)} locked  ·  "
            f"{counts.get('completed', 0)} completed  ·  "
            f"{counts.get('user_blocked', 0)} user-blocked  ·  "
            f"{counts.get('boss_quests', 0)} boss quests"
        )

        self.records_by_id = {item["item_id"]: item for item in board.get("items", [])}
        self.table.setRowCount(0)
        for row_index, record in enumerate(board.get("items", [])):
            self.table.insertRow(row_index)
            quest_class = self._quest_class_text(record)
            priority = str(record.get("priority") or "—")
            readiness = str(record.get("quest_readiness") or "Available")
            values = [
                record["name"],
                quest_class,
                priority,
                readiness,
                f"{record['progress_status']} · {record['progress_percent']}%",
                f"{int(record['xp_reward']):,} XP" if record.get("xp_reward") is not None else "—",
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                cell.setToolTip(str(value))
                if column == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, record["item_id"])
                self.table.setItem(row_index, column, cell)

        if self.records_by_id:
            self.count_label.setText(f"{len(self.records_by_id):,} source quests shown")
            selected_id = self.current_item_id if self.current_item_id in self.records_by_id else None
            if selected_id is None and recommendations:
                selected_id = recommendations[0]["item_id"]
            if selected_id is None:
                selected_id = next(iter(self.records_by_id))
            self._select_item(selected_id)
        else:
            self.count_label.setText("No quests match these filters.")
            self.current_item_id = None
            self._show_item(None)

    @staticmethod
    def _quest_class_text(record: dict) -> str:
        labels = ["BOSS"] if record.get("is_boss_quest") else []
        labels.append(record.get("quest_type", "Side Quest"))
        labels.extend(record.get("quest_tags", []))
        return " · ".join(labels)

    def _select_item(self, item_id: str) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == item_id:
                self.table.selectRow(row)
                self.current_item_id = item_id
                self._show_item(self.records_by_id.get(item_id))
                return

    def _selection_changed(self) -> None:
        selected = self.table.selectedItems()
        if not selected:
            return
        item_id = selected[0].data(Qt.ItemDataRole.UserRole)
        if item_id:
            self.current_item_id = str(item_id)
            self._show_item(self.records_by_id.get(self.current_item_id))

    def _show_item(self, record: dict | None) -> None:
        has_record = record is not None
        self.progress_button.setEnabled(has_record)
        self.verify_button.setEnabled(bool(record and record.get("has_prerequisite_note")))
        if not record:
            self.detail_title.setText("Select a quest")
            self.detail_origin.setText("")
            self.detail_readiness.setText("")
            self.detail_status.setText("")
            self.detail_reward.setText("")
            self.detail_prerequisites.setText("")
            self.detail_description.setText("")
            self.detail_notes.setText("")
            self.detail_progress_note.setText("")
            self.verify_button.setText("Verify source prerequisites")
            return

        self.detail_title.setText(record["name"])
        source = f"{record['source_sheet']} · row {record['source_row']}"
        origin = " · ".join(value for value in (
            self._quest_class_text(record), record.get("category"), record.get("phase"),
            record.get("target_period"), source,
        ) if value)
        self.detail_origin.setText(origin)
        readiness = record["quest_readiness"]
        details = []
        if record.get("missing_prerequisites"):
            details.append("Incomplete dependencies: " + ", ".join(
                prerequisite["name"] for prerequisite in record["missing_prerequisites"]
            ))
        if record.get("unresolved_prerequisites"):
            details.extend(record["unresolved_prerequisites"])
        if record.get("has_prerequisite_note"):
            state = "verified" if record.get("prerequisites_verified") else "not yet verified"
            details.append(f"Source prerequisite note is {state}.")
        if not details:
            details.append("No prerequisites are recorded in the source.")
        self.detail_readiness.setText(f"{readiness}\n" + "\n".join(details))
        self.detail_status.setText(
            f"{record['progress_status']} · {record['progress_percent']}%\n"
            f"Started: {record.get('progress_date_started') or 'Not recorded'} · "
            f"Completed: {record.get('progress_date_completed') or 'Not recorded'}"
        )
        if record.get("xp_reward") is None:
            self.detail_reward.setText("No XP reward specified in the workbook.")
        else:
            self.detail_reward.setText(
                f"{int(record['xp_reward']):,} XP source reward · "
                f"currently awarded: {int(record.get('xp_awarded') or 0):,} XP"
            )
        prerequisite_text = record.get("prerequisite_notes") or "No prerequisite note recorded."
        explicit = record.get("prerequisites", [])
        if explicit:
            prerequisite_text = "Structured prerequisites: " + ", ".join(
                f"{entry['name']} ({entry['progress_status']})" for entry in explicit
            ) + "\n\n" + prerequisite_text
        self.detail_prerequisites.setText(prerequisite_text)
        self.detail_description.setText(record.get("description") or "No description recorded in the workbook.")
        notes = record.get("notes") or "No additional source notes."
        self.detail_notes.setText(notes)
        self.detail_progress_note.setText(record.get("progress_note") or "No local progress note recorded.")
        if not record.get("has_prerequisite_note"):
            self.verify_button.setText("No source prerequisite note")
        else:
            self.verify_button.setText(
                "Revoke prerequisite verification"
                if record.get("prerequisites_verified") else "I verified these prerequisites"
            )

    def _edit_current_progress(self) -> None:
        if self.current_item_id:
            self.progress_edit_requested.emit(self.current_item_id)

    def _toggle_prerequisite_review(self) -> None:
        record = self.records_by_id.get(self.current_item_id or "")
        if record and record.get("has_prerequisite_note"):
            self.prerequisite_review_requested.emit(
                record["item_id"], not bool(record.get("prerequisites_verified"))
            )
