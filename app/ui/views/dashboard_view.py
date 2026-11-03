"""SQLite-backed career dashboard and mission overview."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)


def _card(title: str, value: str, detail: str = "") -> QFrame:
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 12, 16, 12)
    layout.setSpacing(5)
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
    """Show source-defined career levels and live local roadmap progress."""

    progress_edit_requested = Signal(str)

    def __init__(self, on_import, on_open_roadmap, on_open_quests, on_open_skills):
        super().__init__()
        self.on_import = on_import
        self.on_open_roadmap = on_open_roadmap
        self.on_open_quests = on_open_quests
        self.on_open_skills = on_open_skills

        page = QVBoxLayout(self)
        page.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        page.addWidget(self.scroll)
        self.refresh()

    def refresh(self, data: dict | None = None) -> None:
        old_content = self.scroll.takeWidget()
        if old_content is not None:
            old_content.deleteLater()

        content = QWidget()
        self.scroll.setWidget(content)
        self.layout = QVBoxLayout(content)
        self.layout.setContentsMargins(28, 24, 28, 24)
        self.layout.setSpacing(13)
        data = data or {"has_data": False}

        heading = QVBoxLayout()
        eyebrow = QLabel("PROJECT 25  /  COMMAND CENTER")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("Career dashboard")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Career progress and recommendations from your local workbook snapshot.")
        subtitle.setObjectName("muted")
        heading.addWidget(eyebrow)
        heading.addWidget(title)
        heading.addWidget(subtitle)
        self.layout.addLayout(heading)

        if not data.get("has_data"):
            self._show_empty_state()
            return

        self._show_profile(data)
        self._show_metrics(data)
        self._show_missions(data)
        self._show_skills(data)
        self._show_recent_xp(data)
        self._show_navigation()
        self.layout.addStretch(1)

    def _show_empty_state(self) -> None:
        empty = QFrame()
        empty.setObjectName("card")
        layout = QVBoxLayout(empty)
        layout.setContentsMargins(24, 24, 24, 24)
        label = QLabel("Import your Excel roadmap to initialize the local database.")
        label.setWordWrap(True)
        button = QPushButton("Import Excel roadmap")
        button.setObjectName("primary")
        button.clicked.connect(self.on_import)
        layout.addWidget(label)
        layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)
        self.layout.addWidget(empty)
        self.layout.addStretch(1)

    def _show_profile(self, data: dict) -> None:
        card = QFrame()
        card.setObjectName("card")
        profile = QGridLayout(card)
        profile.setContentsMargins(18, 14, 18, 14)
        profile.setHorizontalSpacing(18)
        profile.setVerticalSpacing(6)

        name = QLabel(data.get("profile_name") or "Cybersecurity Apprentice")
        name.setStyleSheet("font-size: 16pt; font-weight: 700; color: #f3f4f6;")
        role = QLabel(f"CURRENT ROLE  ·  {data.get('current_role') or 'Role not specified in workbook'}")
        role.setObjectName("muted")
        phase = QLabel(f"CURRENT PHASE  ·  {data.get('current_phase') or 'Not specified in workbook'}")
        phase.setObjectName("muted")
        profile.addWidget(name, 0, 0, 1, 2)
        profile.addWidget(role, 1, 0, 1, 2)
        profile.addWidget(phase, 2, 0, 1, 2)

        gamification = data.get("gamification") or {}
        level = gamification.get("current_level")
        level_title = gamification.get("level_title")
        level_label = QLabel(
            f"LEVEL {level}  ·  {level_title}" if level and level_title
            else "LEVEL STRUCTURE NOT FOUND IN WORKBOOK"
        )
        level_label.setObjectName("eyebrow")
        total_xp = QLabel(f"{gamification.get('total_xp', 0):,} TOTAL XP")
        total_xp.setStyleSheet("font-size: 17pt; font-weight: 700; color: #f3f4f6;")
        progress = QProgressBar()
        progress.setRange(0, 100)
        progress.setValue(int(gamification.get("level_progress_percent", 0)))
        progress.setTextVisible(False)
        next_level = gamification.get("next_level")
        xp_to_next = gamification.get("xp_to_next_level")
        if next_level is not None and xp_to_next is not None:
            level_detail_text = (
                f"{xp_to_next:,} XP to Level {next_level} · "
                f"{gamification.get('next_level_title', '')}"
            )
        elif gamification.get("is_max_level"):
            level_detail_text = "Maximum level defined by the workbook"
        else:
            level_detail_text = "Level progress is unavailable from this workbook"
        level_detail = QLabel(level_detail_text)
        level_detail.setObjectName("metricCaption")
        profile.addWidget(level_label, 0, 2)
        profile.addWidget(total_xp, 1, 2)
        profile.addWidget(progress, 2, 2)
        profile.addWidget(level_detail, 3, 2)
        self.layout.addWidget(card)

    def _show_metrics(self, data: dict) -> None:
        stats = data.get("statistics", {})
        overall = stats.get("overall", {})
        monthly = stats.get("monthly_missions", {})
        cards = [
            _card(
                "Overall roadmap",
                f"{overall.get('percent', 0):.0f}%",
                f"{overall.get('completed', 0):,} of {overall.get('total', 0):,} objectives complete",
            ),
            _card(
                "Skills",
                f"{stats.get('skills', {}).get('completed', 0):,} / {stats.get('skills', {}).get('total', 0):,}",
                "Skill Matrix records completed",
            ),
            _card(
                "Certifications",
                f"{stats.get('certifications', {}).get('completed', 0):,} / {stats.get('certifications', {}).get('total', 0):,}",
                "Source certification records completed",
            ),
            _card(
                "Projects",
                f"{stats.get('projects', {}).get('completed', 0):,} / {stats.get('projects', {}).get('total', 0):,}",
                "Workbook projects completed",
            ),
            _card(
                "Labs",
                f"{stats.get('labs', {}).get('completed', 0):,} / {stats.get('labs', {}).get('total', 0):,}",
                "Lab-tagged source objectives completed",
            ),
            _card(
                "Learning hours",
                f"{stats['learning_hours']:,.1f} h" if stats.get("learning_hours_recorded") else "Not recorded",
                "Estimated hours present in the source workbook",
            ),
        ]
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        for index, card in enumerate(cards):
            grid.addWidget(card, index // 3, index % 3)

        monthly_detail = QLabel(
            f"Monthly missions: {monthly.get('completed', 0):,} of {monthly.get('total', 0):,} complete"
        )
        monthly_detail.setObjectName("muted")
        wrapper = QVBoxLayout()
        wrapper.addLayout(grid)
        wrapper.addWidget(monthly_detail)
        self.layout.addLayout(wrapper)

    def _show_missions(self, data: dict) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._current_mission_card(data.get("current_mission")))
        splitter.addWidget(self._next_objectives_card(data.get("next_objectives", [])))
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        self.layout.addWidget(splitter)

    def _current_mission_card(self, mission: dict | None) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(7)
        heading = QLabel("CURRENT MISSION")
        heading.setObjectName("eyebrow")
        title = QLabel(mission["name"] if mission else "No ready mission available")
        title.setStyleSheet("font-size: 15pt; font-weight: 650; color: #f3f4f6;")
        title.setWordWrap(True)
        if mission:
            detail = QLabel(
                f"{mission.get('quest_type', 'Roadmap objective')}  ·  "
                f"{mission['progress_status']} · {mission['progress_percent']}%"
            )
            reward = mission.get("xp_reward")
            if reward is not None:
                detail.setText(detail.text() + f"  ·  +{int(reward):,} source XP")
            context = "  ·  ".join(value for value in (
                mission.get("target_period"), mission.get("phase"), mission.get("category")
            ) if value)
            description = mission.get("description") or "No description recorded in the workbook."
            reason = mission.get("recommendation_reason") or "Next ready source objective."
        else:
            detail = QLabel("Review prerequisite states in Quests or import a roadmap workbook.")
            context = ""
            description = ""
            reason = ""
        for label in (detail,):
            label.setObjectName("muted")
        context_label = QLabel(context)
        context_label.setObjectName("eyebrow")
        description_label = QLabel(description)
        description_label.setObjectName("muted")
        description_label.setWordWrap(True)
        reason_label = QLabel(reason)
        reason_label.setObjectName("muted")
        reason_label.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(title)
        layout.addWidget(detail)
        if context:
            layout.addWidget(context_label)
        if description:
            layout.addWidget(description_label)
        if reason:
            layout.addWidget(reason_label)
        layout.addStretch(1)
        actions = QHBoxLayout()
        quests_button = QPushButton("Open quest board")
        quests_button.clicked.connect(self.on_open_quests)
        actions.addWidget(quests_button)
        if mission:
            update_button = QPushButton("Update progress")
            update_button.setObjectName("primary")
            update_button.clicked.connect(
                lambda _checked=False, item_id=mission["item_id"]: self.progress_edit_requested.emit(item_id)
            )
            actions.addWidget(update_button)
        layout.addLayout(actions)
        return card

    def _next_objectives_card(self, objectives: list[dict]) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(8)
        heading = QLabel("NEXT OBJECTIVES")
        heading.setObjectName("eyebrow")
        layout.addWidget(heading)
        if objectives:
            for index, objective in enumerate(objectives[:3], start=1):
                row = QVBoxLayout()
                title = QLabel(f"{index}.  {objective['name']}")
                title.setStyleSheet("font-weight: 600; color: #e7e9ed;")
                title.setWordWrap(True)
                detail_text = (
                    f"{objective.get('quest_type', 'Objective')}  ·  "
                    f"{objective['progress_status']} · {objective['progress_percent']}%"
                )
                reward = objective.get("xp_reward")
                if reward is not None:
                    detail_text += f"  ·  +{int(reward):,} XP"
                detail = QLabel(detail_text)
                detail.setObjectName("muted")
                detail.setWordWrap(True)
                row.addWidget(title)
                row.addWidget(detail)
                layout.addLayout(row)
                if index < len(objectives):
                    divider = QFrame()
                    divider.setFrameShape(QFrame.Shape.HLine)
                    divider.setObjectName("divider")
                    layout.addWidget(divider)
        else:
            empty = QLabel("No additional ready objectives. Check prerequisite reviews in Quests.")
            empty.setObjectName("muted")
            empty.setWordWrap(True)
            layout.addWidget(empty)
        layout.addStretch(1)
        return card

    def _show_skills(self, data: dict) -> None:
        heading = QHBoxLayout()
        title = QLabel("SKILL OVERVIEW")
        title.setObjectName("eyebrow")
        open_button = QPushButton("Open skill tree")
        open_button.clicked.connect(self.on_open_skills)
        heading.addWidget(title)
        heading.addStretch(1)
        heading.addWidget(open_button)
        self.layout.addLayout(heading)

        branches = data.get("skill_branches", [])
        if not branches:
            empty = QLabel("No skills or specializations are present in the active workbook.")
            empty.setObjectName("muted")
            self.layout.addWidget(empty)
            return

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        for index, branch in enumerate(branches):
            grid.addWidget(self._skill_branch_card(branch), index // 2, index % 2)
        self.layout.addLayout(grid)

    @staticmethod
    def _skill_branch_card(branch: dict) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(5)
        header = QHBoxLayout()
        name = QLabel(branch["name"])
        name.setStyleSheet("font-weight: 600; color: #e7e9ed;")
        percent = QLabel(f"{branch['progress_percent']}%")
        percent.setObjectName("metricCaption")
        header.addWidget(name)
        header.addStretch(1)
        header.addWidget(percent)
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(int(branch["progress_percent"]))
        bar.setTextVisible(False)
        detail = QLabel(
            f"{branch['completed']} of {branch['total']} complete  ·  "
            f"{branch['in_progress']} in progress"
        )
        detail.setObjectName("metricCaption")
        layout.addLayout(header)
        layout.addWidget(bar)
        layout.addWidget(detail)
        return card

    def _show_recent_xp(self, data: dict) -> None:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 13, 18, 13)
        heading = QLabel("RECENT XP ACTIVITY")
        heading.setObjectName("eyebrow")
        layout.addWidget(heading)
        recent = (data.get("gamification") or {}).get("recent_transactions", [])
        if recent:
            for entry in recent[:5]:
                amount = int(entry["amount"])
                scope = "Career" if entry["item_type"] in {"monthly_mission", "project"} else "Track"
                event_date = str(entry.get("created_at") or "")[:10]
                line = QLabel(f"{amount:+,} XP  ·  {entry['name']}  ·  {scope}  ·  {event_date}")
                line.setObjectName("muted")
                line.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                layout.addWidget(line)
        else:
            empty = QLabel("No XP activity recorded yet.")
            empty.setObjectName("muted")
            layout.addWidget(empty)
        self.layout.addWidget(card)

    def _show_navigation(self) -> None:
        actions = QHBoxLayout()
        for text, callback in (
            ("Open roadmap", self.on_open_roadmap),
            ("Open quests", self.on_open_quests),
            ("Open skill tree", self.on_open_skills),
            ("Import another workbook", self.on_import),
        ):
            button = QPushButton(text)
            button.clicked.connect(callback)
            actions.addWidget(button)
        self.layout.addLayout(actions)
