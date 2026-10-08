"""Application shell and page navigation."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from app import __version__
from app.importers.excel_importer import import_excel
from app.services.roadmap_service import (
    get_active_workbook,
    get_core_roadmap,
    get_dashboard_data,
    get_import_issues,
    get_source_sheets,
)
from app.ui.views.dashboard_view import DashboardView
from app.ui.views.import_view import ImportView
from app.ui.views.roadmap_view import RoadmapView


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
        self.import_page = ImportView(self.choose_workbook)
        self.pages.addWidget(self.dashboard)
        self.pages.addWidget(self.roadmap)
        self.pages.addWidget(self.import_page)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: list[QPushButton] = []
        for index, label in enumerate(("Dashboard", "Roadmap", "Import data")):
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
        dashboard_data = get_dashboard_data(self.connection)
        self.dashboard.refresh(dashboard_data)
        self.roadmap.refresh(get_core_roadmap(self.connection))
        self.import_page.refresh(
            get_active_workbook(self.connection),
            get_source_sheets(self.connection),
            get_import_issues(self.connection),
        )

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
        self.navigate(2)
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
