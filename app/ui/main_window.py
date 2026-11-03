"""Application shell and page navigation."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from app import __version__
from app.importers.excel_importer import import_excel
from app.services.roadmap_service import (
    clear_item_progress,
    get_roadmap_filter_options,
    get_roadmap_item,
    get_roadmap_items,
    save_item_progress,
)
from app.services.gamification_service import get_gamification_data, sync_xp_awards
from app.services.quest_service import get_quest_board, set_prerequisites_verified
from app.services.skill_tree_service import get_skill_tree
from app.services.roadmap_service import (
    get_active_workbook,
    get_dashboard_data,
    get_import_issues,
    get_source_sheets,
)
from app.ui.dialogs.progress_dialog import ProgressDialog
from app.ui.views.dashboard_view import DashboardView
from app.ui.views.import_view import ImportView
from app.ui.views.quest_view import QuestView
from app.ui.views.roadmap_view import RoadmapView
from app.ui.views.skill_tree_view import SkillTreeView


class MainWindow(QMainWindow):
    def __init__(self, connection, database_path: Path):
        super().__init__()
        self.connection = connection
        self.database_path = database_path
        self.setWindowTitle(f"Cybersecurity Career Roadmap · v{__version__}")
        self.resize(1360, 850)
        self.setMinimumSize(1040, 680)

        root = QWidget()
        root.setObjectName("root")
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.setCentralWidget(root)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(228)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 20, 16, 14)
        sidebar_layout.setSpacing(8)
        brand = QLabel("PROJECT 25")
        brand.setObjectName("brand")
        brand_hint = QLabel("CYBERSECURITY ROADMAP")
        brand_hint.setObjectName("eyebrow")
        sidebar_layout.addWidget(brand)
        sidebar_layout.addWidget(brand_hint)
        sidebar_layout.addSpacing(18)

        self.pages = QStackedWidget()
        self.dashboard = DashboardView(self.choose_workbook, lambda: self.navigate(1))
        self.roadmap = RoadmapView()
        self.roadmap.filters_changed.connect(self.refresh_roadmap)
        self.roadmap.progress_edit_requested.connect(self.edit_item_progress)
        self.quest = QuestView()
        self.quest.filters_changed.connect(self.refresh_quests)
        self.quest.progress_edit_requested.connect(self.edit_item_progress)
        self.quest.prerequisite_review_requested.connect(self.review_quest_prerequisites)
        self.skill_tree = SkillTreeView()
        self.skill_tree.filters_changed.connect(self.refresh_skill_tree)
        self.skill_tree.progress_edit_requested.connect(self.edit_item_progress)
        self.skill_tree.prerequisite_review_requested.connect(self.review_skill_prerequisites)
        self.import_page = ImportView(self.choose_workbook)
        self.pages.addWidget(self.dashboard)
        self.pages.addWidget(self.roadmap)
        self.pages.addWidget(self.quest)
        self.pages.addWidget(self.skill_tree)
        self.pages.addWidget(self.import_page)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: list[QPushButton] = []
        for index, label in enumerate(("Dashboard", "Roadmap", "Quests", "Skill Tree", "Import data")):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda checked=False, page=index: self.navigate(page))
            self.nav_group.addButton(button, index)
            self.nav_buttons.append(button)
            sidebar_layout.addWidget(button)
        sidebar_layout.addStretch(1)
        source_note = QLabel("Offline-first\nSQLite · local data")
        source_note.setObjectName("muted")
        sidebar_layout.addWidget(source_note)
        version_label = QLabel(f"VERSION {__version__}")
        version_label.setObjectName("eyebrow")
        sidebar_layout.addWidget(version_label)

        root_layout.addWidget(sidebar)
        root_layout.addWidget(self.pages, 1)
        self.statusBar().showMessage("Offline-first · progress data is stored locally")
        self.refresh_pages()
        self.navigate(0)

    def navigate(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        self.nav_buttons[index].setChecked(True)

    def refresh_pages(self) -> None:
        sync_xp_awards(self.connection)
        dashboard_data = get_dashboard_data(self.connection)
        self.dashboard.refresh(dashboard_data)
        self.roadmap.set_filter_options(get_roadmap_filter_options(self.connection))
        self.refresh_roadmap()
        self.refresh_quests()
        self.refresh_skill_tree()
        self.import_page.refresh(
            get_active_workbook(self.connection),
            get_source_sheets(self.connection),
            get_import_issues(self.connection),
        )

    def refresh_roadmap(self) -> None:
        records = get_roadmap_items(self.connection, **self.roadmap.filter_values())
        self.roadmap.refresh(records)

    def refresh_quests(self) -> None:
        board = get_quest_board(self.connection, **self.quest.filter_values())
        self.quest.refresh(board)

    def refresh_skill_tree(self) -> None:
        tree = get_skill_tree(self.connection, **self.skill_tree.filter_values())
        self.skill_tree.refresh(tree)

    def review_quest_prerequisites(self, item_id: str, verified: bool) -> None:
        try:
            set_prerequisites_verified(self.connection, item_id, verified)
        except (KeyError, ValueError) as error:
            QMessageBox.warning(self, "Prerequisites not updated", str(error))
            return
        self.refresh_quests()
        message = "Source prerequisites verified" if verified else "Prerequisite verification removed"
        self.statusBar().showMessage(message, 6000)

    def review_skill_prerequisites(self, item_id: str, verified: bool) -> None:
        try:
            set_prerequisites_verified(self.connection, item_id, verified)
        except (KeyError, ValueError) as error:
            QMessageBox.warning(self, "Prerequisites not updated", str(error))
            return
        self.refresh_skill_tree()
        message = "Source prerequisites verified" if verified else "Prerequisite verification removed"
        self.statusBar().showMessage(message, 6000)

    def edit_item_progress(self, item_id: str) -> None:
        before = get_gamification_data(self.connection)
        record = get_roadmap_item(self.connection, item_id)
        if record is None:
            QMessageBox.warning(self, "Roadmap item unavailable", "This item is no longer in the active workbook.")
            self.refresh_pages()
            return
        dialog = ProgressDialog(record, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            if dialog.reset_requested:
                answer = QMessageBox.question(
                    self,
                    "Reset local progress",
                    "Remove this item's local progress and return to its source-derived display state?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return
                clear_item_progress(self.connection, item_id)
                message = "Local progress reset · workbook data remains unchanged"
            else:
                save_item_progress(self.connection, item_id, dialog.progress_update())
                message = "Local progress saved · workbook data remains unchanged"
        except (KeyError, ValueError) as error:
            QMessageBox.warning(self, "Progress not saved", str(error))
            return
        self.refresh_pages()
        after = get_gamification_data(self.connection)
        career_delta = after["career_xp"] - before["career_xp"]
        total_delta = after["total_xp"] - before["total_xp"]
        if after.get("current_level") and after.get("current_level") > (before.get("current_level") or 0):
            message = f"LEVEL UP · Level {after['current_level']} — {after['level_title']}"
        elif career_delta > 0:
            message = f"+{career_delta:,} Career XP · {message}"
        elif total_delta > 0:
            message = f"+{total_delta:,} track XP · {message}"
        elif total_delta < 0:
            message = f"{total_delta:,} XP reversed · {message}"
        self.statusBar().showMessage(message, 8000)

    def choose_workbook(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Import cybersecurity roadmap",
            str(Path.home()),
            "Excel workbooks (*.xlsx *.xlsm)",
        )
        if not filename:
            return
        try:
            result = import_excel(self.connection, filename)
        except Exception as error:  # A visible dialog keeps import failures actionable.
            QMessageBox.critical(self, "Import failed", str(error))
            return

        self.refresh_pages()
        self.navigate(4)
        if result.already_imported:
            title = "Workbook already imported"
            message = "This exact workbook was already imported. The existing local snapshot was reactivated without replacing it."
        else:
            title = "Import complete"
            message = (
                f"Imported {result.sheet_count} sheets, {result.source_row_count:,} populated rows, "
                f"{result.source_cell_count:,} populated cells, and {result.item_count:,} normalized roadmap records.\n\n"
                f"Validation findings: {len(result.issues)}. Open Import data to review them."
            )
        QMessageBox.information(self, title, message)
        self.statusBar().showMessage("Import complete · local SQLite snapshot active")

    def closeEvent(self, event) -> None:
        self.connection.close()
        super().closeEvent(event)
