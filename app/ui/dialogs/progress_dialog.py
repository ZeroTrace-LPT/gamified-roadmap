"""Dialog for editing user-owned progress without changing imported source data."""

from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.models.roadmap import PROGRESS_STATUSES, ProgressUpdate


class ProgressDialog(QDialog):
    """Edit one item's local status, percentage, dates, and note."""

    def __init__(self, record: dict, parent: QWidget | None = None):
        super().__init__(parent)
        self.record = record
        self.reset_requested = False
        self.setWindowTitle("Update roadmap progress")
        self.setMinimumWidth(470)

        layout = QVBoxLayout(self)
        title = QLabel(record["name"])
        title.setWordWrap(True)
        title.setStyleSheet("font-size: 15pt; font-weight: 650; color: #f3f4f6;")
        source_status = record.get("status") or "Blank in source"
        source = QLabel(f"Source status: {source_status}\nThis source value stays unchanged.")
        source.setObjectName("muted")
        source.setWordWrap(True)
        form = QFormLayout()

        self.status = QComboBox()
        self.status.addItems(PROGRESS_STATUSES)
        self.status.setCurrentText(record["progress_status"])
        self.percent = QSpinBox()
        self.percent.setRange(0, 100)
        self.percent.setSuffix("%")
        self.percent.setValue(int(record.get("progress_percent") or 0))
        form.addRow("Local progress status", self.status)
        form.addRow("Progress", self.percent)

        self.started_enabled = QCheckBox("Record start date")
        self.started_date = self._date_editor(record.get("progress_date_started"))
        self.started_enabled.setChecked(bool(record.get("progress_date_started")))
        self.started_date.setEnabled(self.started_enabled.isChecked())
        self.started_enabled.toggled.connect(self.started_date.setEnabled)
        form.addRow(self.started_enabled, self.started_date)

        self.completed_enabled = QCheckBox("Record completion date")
        self.completed_date = self._date_editor(record.get("progress_date_completed"))
        self.completed_enabled.setChecked(bool(record.get("progress_date_completed")))
        self.completed_date.setEnabled(self.completed_enabled.isChecked())
        self.completed_enabled.toggled.connect(self.completed_date.setEnabled)
        form.addRow(self.completed_enabled, self.completed_date)

        self.note = QPlainTextEdit()
        self.note.setPlaceholderText("Private progress note for this item")
        self.note.setPlainText(record.get("progress_note") or "")
        self.note.document().setMaximumBlockCount(500)
        form.addRow("Local note", self.note)

        layout.addWidget(title)
        layout.addWidget(source)
        layout.addLayout(form)

        self.reset_button = QPushButton("Reset local progress to source")
        self.reset_button.setEnabled(bool(record.get("has_progress_override")))
        self.reset_button.clicked.connect(self._request_reset)
        layout.addWidget(self.reset_button, 0, Qt.AlignmentFlag.AlignLeft)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _date_editor(value: str | None) -> QDateEdit:
        editor = QDateEdit()
        editor.setCalendarPopup(True)
        editor.setDisplayFormat("yyyy-MM-dd")
        if value:
            parsed = QDate.fromString(value, Qt.DateFormat.ISODate)
            if parsed.isValid():
                editor.setDate(parsed)
        else:
            editor.setDate(QDate.currentDate())
        return editor

    def _request_reset(self) -> None:
        self.reset_requested = True
        self.accept()

    def _validate_and_accept(self) -> None:
        status = self.status.currentText()
        percent = self.percent.value()
        if status == "Completed" and percent != 100:
            QMessageBox.warning(self, "Progress needs review", "Completed items must be at 100%.")
            return
        if status == "Not started" and percent != 0:
            QMessageBox.warning(self, "Progress needs review", "Not started items must be at 0%.")
            return
        if self.completed_enabled.isChecked() and status != "Completed":
            QMessageBox.warning(self, "Progress needs review", "A completion date requires Completed status.")
            return
        if self.started_enabled.isChecked() and self.completed_enabled.isChecked():
            if self.completed_date.date() < self.started_date.date():
                QMessageBox.warning(self, "Progress needs review", "Completion date cannot precede start date.")
                return
        self.accept()

    def progress_update(self) -> ProgressUpdate:
        """Return validated values after the dialog is accepted for saving."""
        return ProgressUpdate(
            status=self.status.currentText(),
            progress_percent=self.percent.value(),
            date_started=(
                self.started_date.date().toString(Qt.DateFormat.ISODate)
                if self.started_enabled.isChecked() else None
            ),
            date_completed=(
                self.completed_date.date().toString(Qt.DateFormat.ISODate)
                if self.completed_enabled.isChecked() else None
            ),
            note=self.note.toPlainText(),
        )
