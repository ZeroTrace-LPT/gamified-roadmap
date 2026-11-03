"""Career dashboard with source-backed XP and progression."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)


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
    sub.setWordWrap(True)
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
        self.layout.setSpacing(14)
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
        subtitle = QLabel("Progress and rewards calculated from your local workbook snapshot.")
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

        gamification = data.get("gamification") or {}
        name = data.get("profile_name") or "Player"
        if gamification.get("level_system_available"):
            profile_text = (
                f"{name}   ·   LEVEL {gamification['current_level']} — {gamification['level_title']}"
                f"   ·   TOTAL XP {gamification.get('total_xp', 0):,}"
            )
        else:
            profile_text = (
                f"{name}   ·   No level table found in workbook"
                f"   ·   TOTAL XP {gamification.get('total_xp', 0):,}"
            )
        profile = QLabel(profile_text)
        profile.setObjectName("muted")
        self.layout.addWidget(profile)

        cards = QGridLayout()
        cards.setHorizontalSpacing(12)
        cards.setVerticalSpacing(12)
        next_level = gamification.get("next_level")
        xp_to_next = gamification.get("xp_to_next_level")
        next_value = f"{xp_to_next:,}" if xp_to_next is not None else "—"
        next_detail = (
            f"to Level {next_level} · {gamification.get('next_level_title', '')}"
            if next_level is not None else "Source-defined maximum level reached"
        )
        cards.addWidget(_card(
            "Career XP",
            f"{gamification.get('career_xp', 0):,}",
            "Monthly missions and projects · used for workbook levels",
        ), 0, 0)
        cards.addWidget(_card(
            "Track XP",
            f"{gamification.get('track_xp', 0):,}",
            "Other completed items with source-defined XP rewards",
        ), 0, 1)
        cards.addWidget(_card(
            "XP to next level",
            next_value,
            next_detail,
        ), 0, 2)
        self.layout.addLayout(cards)

        level_card = QFrame()
        level_card.setObjectName("card")
        level_layout = QVBoxLayout(level_card)
        level_layout.setContentsMargins(18, 14, 18, 14)
        level_title = QLabel("LEVEL PROGRESSION")
        level_title.setObjectName("eyebrow")
        level_bar = QProgressBar()
        level_bar.setRange(0, 100)
        level_percent = int(gamification.get("level_progress_percent", 0))
        level_bar.setValue(level_percent)
        level_bar.setTextVisible(False)
        if gamification.get("is_max_level"):
            level_title.setText("LEVEL PROGRESSION · MAX LEVEL")
        elif gamification.get("level_system_available"):
            level_title.setText(f"LEVEL PROGRESSION · {level_percent}%")
        else:
            level_title.setText("LEVEL PROGRESSION · SOURCE TABLE NOT FOUND")
        next_reward = gamification.get("next_level_reward") or gamification.get("next_level_unlock")
        reward = QLabel(
            f"Next source reward: {next_reward}"
            if next_reward and next_level is not None else
            f"Current XP band: {gamification.get('level_band') or 'Not defined in source'}"
        )
        reward.setObjectName("muted")
        level_layout.addWidget(level_title)
        level_layout.addWidget(level_bar)
        level_layout.addWidget(reward)
        self.layout.addWidget(level_card)

        stats = QFrame()
        stats.setObjectName("card")
        stats_layout = QVBoxLayout(stats)
        stats_layout.setContentsMargins(18, 13, 18, 13)
        stats_title = QLabel("ROADMAP COMPLETION")
        stats_title.setObjectName("eyebrow")
        stats_title.setText(
            f"ROADMAP COMPLETION · {data['roadmap_percent']:.0f}% · "
            f"{data['roadmap_completed']} OF {data['roadmap_total']} MONTHLY MISSIONS"
        )
        stats_bar = QProgressBar()
        stats_bar.setRange(0, 100)
        stats_bar.setValue(round(data["roadmap_percent"]))
        stats_bar.setTextVisible(False)
        stats_layout.addWidget(stats_title)
        stats_layout.addWidget(stats_bar)
        self.layout.addWidget(stats)

        current = data.get("current_mission")
        mission_card = QFrame()
        mission_card.setObjectName("card")
        mission_layout = QVBoxLayout(mission_card)
        mission_layout.setContentsMargins(18, 14, 18, 14)
        mission_heading = QLabel("CURRENT ROADMAP MISSION")
        mission_heading.setObjectName("eyebrow")
        mission_title = QLabel(current["name"] if current else "No incomplete mission found")
        mission_title.setStyleSheet("font-size: 15pt; font-weight: 650; color: #f3f4f6;")
        mission_progress_text = (
            f"Local progress: {current['progress_status']} · {current['progress_percent']}%"
            if current else ""
        )
        reward_xp = current.get("xp_reward") if current else None
        if reward_xp:
            mission_progress_text += f"   ·   Reward: +{int(reward_xp):,} XP"
        mission_progress = QLabel(mission_progress_text)
        mission_progress.setObjectName("muted")
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
        mission_layout.addWidget(mission_progress)
        mission_layout.addWidget(metadata)
        mission_layout.addWidget(mission_text)
        self.layout.addWidget(mission_card)

        activity = QFrame()
        activity.setObjectName("card")
        activity_layout = QVBoxLayout(activity)
        activity_layout.setContentsMargins(18, 13, 18, 13)
        activity_title = QLabel("RECENT XP ACTIVITY")
        activity_title.setObjectName("eyebrow")
        activity_layout.addWidget(activity_title)
        recent = gamification.get("recent_transactions", [])
        if recent:
            for entry in recent[:5]:
                amount = int(entry["amount"])
                scope = "Career" if entry["item_type"] in {"monthly_mission", "project"} else "Track"
                event_date = str(entry.get("created_at") or "")[:10]
                line = QLabel(f"{amount:+,} XP  ·  {entry['name']}  ·  {scope}  ·  {event_date}")
                line.setObjectName("muted")
                line.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                activity_layout.addWidget(line)
        else:
            no_events = QLabel("No rewards recorded yet. Complete a source-reward item to begin.")
            no_events.setObjectName("muted")
            activity_layout.addWidget(no_events)
        self.layout.addWidget(activity)

        footer = QGridLayout()
        roadmap_button = QPushButton("Open roadmap")
        roadmap_button.clicked.connect(self.on_open_roadmap)
        import_button = QPushButton("Import another workbook")
        import_button.clicked.connect(self.on_import)
        footer.addWidget(roadmap_button, 0, 0)
        footer.addWidget(import_button, 0, 1)
        self.layout.addLayout(footer)
        self.layout.addStretch(1)
