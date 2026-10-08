"""Professional dark theme with restrained crimson accents."""

from __future__ import annotations

from PySide6.QtGui import QPalette, QColor


def apply_theme(application) -> None:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#111316"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#e7e9ed"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#171a1f"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#1d2026"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#e7e9ed"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#22262d"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#e7e9ed"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#9e2534"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    application.setPalette(palette)
    application.setStyleSheet("""
        QWidget { font-family: 'Segoe UI'; font-size: 10pt; }
        QMainWindow, QWidget#root { background: #111316; color: #e7e9ed; }
        QFrame#sidebar { background: #15171b; border-right: 1px solid #292d34; }
        QLabel#brand { color: #f2f3f5; font-size: 13pt; font-weight: 700; }
        QLabel#eyebrow { color: #9ba1aa; font-size: 8pt; font-weight: 700; letter-spacing: 1px; }
        QLabel#pageTitle { color: #f3f4f6; font-size: 21pt; font-weight: 700; }
        QLabel#muted { color: #a4a9b2; }
        QPushButton { background: #22262d; color: #e7e9ed; border: 1px solid #343941;
                      border-radius: 7px; padding: 9px 12px; text-align: left; }
        QPushButton:hover { background: #2b3038; border-color: #535963; }
        QPushButton:checked { background: #342024; color: #ffffff; border: 1px solid #9e2534; }
        QPushButton#primary { background: #9e2534; border: 1px solid #b83747; font-weight: 600; }
        QPushButton#primary:hover { background: #b32f40; }
        QFrame#card { background: #191c21; border: 1px solid #2b2f36; border-radius: 10px; }
        QLabel#metric { color: #f4f5f7; font-size: 22pt; font-weight: 700; }
        QLabel#metricCaption { color: #a7acb4; font-size: 9pt; }
        QProgressBar { background: #242830; color: #e7e9ed; border: none; border-radius: 5px;
                       min-height: 10px; max-height: 10px; text-align: center; }
        QProgressBar::chunk { background: #b33445; border-radius: 5px; }
        QTableWidget { background: #171a1f; alternate-background-color: #1c2026;
                       border: 1px solid #2b2f36; gridline-color: #292d34; }
        QHeaderView::section { background: #20242b; color: #c8ccd2; padding: 8px;
                               border: 0; border-bottom: 1px solid #343941; font-weight: 600; }
        QTableWidget::item { padding: 7px; border-bottom: 1px solid #252930; }
        QLineEdit, QComboBox { background: #171a1f; color: #e7e9ed; border: 1px solid #343941;
                               border-radius: 6px; padding: 8px; }
        QScrollArea { border: none; }
        QScrollBar:vertical { background: #15171b; width: 10px; }
        QScrollBar::handle:vertical { background: #424751; border-radius: 4px; min-height: 24px; }
        QToolTip { background: #20242b; color: #ffffff; border: 1px solid #4a5059; padding: 5px; }
    """)
