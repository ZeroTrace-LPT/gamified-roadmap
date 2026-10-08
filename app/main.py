"""Desktop application entry point."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from app.config.paths import get_database_path
from app.database.connection import connect_database
from app.ui.main_window import MainWindow
from app.ui.theme import apply_theme


def main() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName("Cybersecurity Career Roadmap")
    application.setOrganizationName("Cybersecurity Roadmap")
    apply_theme(application)
    database_path = get_database_path()
    try:
        connection = connect_database(database_path)
    except Exception as error:
        QMessageBox.critical(None, "Database error", f"Could not open the local SQLite database.\n\n{error}")
        return 1
    window = MainWindow(connection, database_path)
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
