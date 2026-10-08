"""Compact v0.1 career dashboard."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QPushButton, QProgressBar, QVBoxLayout, QWidget


def _card(title: str, value: str, detail: str = "") -> QFrame:
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(17, 14, 17, 14)
    caption = QLabel(title.upper())
    caption.setObjectName("eyebrow")
    metric = QLabel(value)
    metric.setObjectName("metric")
    sub = QLabel(detail)
    sub.setObjectName("metricCaption")
    layout.addWidget(caption)
    layout.addWidget(metric)
    layout.addWidget(sub)
    layout.addStretch(1)
    return frame


class DashboardView(QWidget):
    def __init__(self, on_import, on_open_roadmap):
        super().__init__()
        self.on_import = on_import
        self.on_open_roadmap = on_open_roadmap
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(28, 24, 28, 24)
        self.layout.setSpacing(18)
        self.refresh()

    def refresh(self, data: dict | None = None) -> None:
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        data = data or {"has_data": False}

        heading = QVBoxLayout()
        eyebrow = QLabel("PROJECT 25  /  COMMAND CENTER")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Career roadmap")
        title.setObjectName("pageTitle")
        subtitle = QLabel("A local, source-backed view of your cybersecurity progression.")
        subtitle.setObjectName("muted")
        heading.addWidget(eyebrow)
        heading.addWidget(title)
        heading.addWidget(subtitle)
        self.layout.addLayout(heading)

        if not data.get("has_data"):
            empty = QFrame()
            empty.setObjectName("card")
            empty_layout = QVBoxLayout(empty)
            empty_layout.setContentsMargins(24, 24, 24, 24)
            label = QLabel("Import your Excel roadmap to initialize the local database.")
            label.setWordWrap(True)
            button = QPushButton("Import Excel roadmap")
            button.setObjectName("primary")
            button.clicked.connect(self.on_import)
            empty_layout.addWidget(label)
            empty_layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignLeft)
            empty_layout.addStretch(1)
            self.layout.addWidget(empty)
            self.layout.addStretch(1)
            return

        name = data["profile_name"] or "Player"
        profile = QLabel(f"{name}   ·   Level {data['level']} — {data['level_title']}")
        profile.setObjectName("muted")
        self.layout.addWidget(profile)

        cards = QGridLayout()
        cards.setHorizontalSpacing(12)
        cards.setVerticalSpacing(12)
        cards.addWidget(_card("Total XP", f"{data['xp']:,}", "Imported from the workbook's saved summary"), 0, 0)
        cards.addWidget(_card("Core missions", f"{data['roadmap_completed']} / {data['roadmap_total']}", "62 monthly milestones in the source plan"), 0, 1)
        cards.addWidget(_card("Roadmap records", f"{data['record_total']:,}", "Normalized from task-like source rows"), 0, 2)
        self.layout.addLayout(cards)

        progress_card = QFrame()
        progress_card.setObjectName("card")
        progress_layout = QVBoxLayout(progress_card)
        progress_layout.setContentsMargins(18, 16, 18, 16)
        progress_title = QLabel("CORE ROADMAP COMPLETION")
        progress_title.setObjectName("eyebrow")
        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(round(data["roadmap_percent"]))
        progress_bar.setFormat(f"{data['roadmap_percent']:.0f}%")
        progress_layout.addWidget(progress_title)
        progress_layout.addWidget(progress_bar)
        self.layout.addWidget(progress_card)

        current = data.get("current_mission")
        mission_card = QFrame()
        mission_card.setObjectName("card")
        mission_layout = QVBoxLayout(mission_card)
        mission_layout.setContentsMargins(18, 16, 18, 16)
        mission_heading = QLabel("CURRENT ROADMAP MISSION")
        mission_heading.setObjectName("eyebrow")
        mission_title = QLabel(current["name"] if current else "No incomplete mission found")
        mission_title.setStyleSheet("font-size: 15pt; font-weight: 650; color: #f3f4f6;")
        mission_text = QLabel(current["description"] if current else "")
        mission_text.setWordWrap(True)
        mission_text.setObjectName("muted")
        metadata = QLabel(
            f"{current['target_period']}   ·   {current['phase']}   ·   {current['category']}"
            if current else ""
        )
        metadata.setObjectName("eyebrow")
        mission_layout.addWidget(mission_heading)
        mission_layout.addWidget(mission_title)
        mission_layout.addWidget(metadata)
        mission_layout.addWidget(mission_text)
        self.layout.addWidget(mission_card)

        footer = QGridLayout()
        roadmap_button = QPushButton("Open roadmap")
        roadmap_button.clicked.connect(self.on_open_roadmap)
        import_button = QPushButton("Import another workbook")
        import_button.clicked.connect(self.on_import)
        footer.addWidget(roadmap_button, 0, 0)
        footer.addWidget(import_button, 0, 1)
        self.layout.addLayout(footer)
        self.layout.addStretch(1)
