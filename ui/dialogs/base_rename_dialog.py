"""
Base class for rename dialogs.
"""
import logging
from abc import abstractmethod

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QProgressBar,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal, QThread

from system.i18n import t

logger = logging.getLogger(__name__)


class BaseRenameWorker(QThread):
    """Base worker thread for rename operations."""
    finished = Signal(dict)  # Result dict
    progress = Signal(int, int)  # current, total

    def run(self):
        """Subclass must implement."""
        pass


class BaseRenameDialog(QDialog):
    """Base class for rename dialogs."""

    # Common stylesheet for all rename dialogs
    DARK_STYLE = """
        QDialog {
            background-color: #282828;
            color: #ffffff;
        }
        QLabel {
            color: #ffffff;
            font-size: 13px;
        }
        QLineEdit {
            background-color: #181818;
            color: #ffffff;
            border: 1px solid #404040;
            border-radius: 4px;
            padding: 10px;
            font-size: 14px;
        }
        QLineEdit:focus {
            border: 1px solid #1db954;
        }
        QLineEdit:read-only {
            background-color: #1a1a1a;
            color: #b3b3b3;
        }
        QPushButton {
            background-color: #1db954;
            color: #000000;
            border: none;
            padding: 10px 24px;
            border-radius: 4px;
            font-weight: bold;
            font-size: 14px;
        }
        QPushButton:hover {
            background-color: #1ed760;
        }
        QPushButton:disabled {
            background-color: #404040;
            color: #808080;
        }
        QPushButton[role="cancel"] {
            background-color: #404040;
            color: #ffffff;
        }
        QPushButton[role="cancel"]:hover {
            background-color: #505050;
        }
        QProgressBar {
            background-color: #181818;
            border: none;
            border-radius: 4px;
            height: 6px;
            text-align: center;
        }
        QProgressBar::chunk {
            background-color: #1db954;
            border-radius: 4px;
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._warning_label = None
        self._name_input = None
        self._progress_bar = None
        self._rename_btn = None
        self._cancel_btn = None

    def _setup_common_ui(self, title: str, min_width: int = 450):
        """Setup common UI elements.

        Args:
            title: Dialog window title
            min_width: Minimum dialog width
        """
        self.setWindowTitle(title)
        self.setMinimumWidth(min_width)
        self.setStyleSheet(self.DARK_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        return layout

    def _add_info_label(self, layout: QVBoxLayout, text: str) -> QLabel:
        """Add info label to layout."""
        info_label = QLabel(text)
        info_label.setStyleSheet(
            "color: #1db954; font-size: 14px; padding: 12px; "
            "background-color: #1a1a1a; border-radius: 6px;"
        )
        layout.addWidget(info_label)
        return info_label

    def _add_name_input(self, layout: QVBoxLayout, label_text: str, initial_value: str) -> QLineEdit:
        """Add name input field to layout."""
        name_layout = QHBoxLayout()
        name_label = QLabel(label_text)
        name_label.setFixedWidth(80)
        self._name_input = QLineEdit(initial_value)
        self._name_input.setPlaceholderText(t("enter_name"))
        self._name_input.textChanged.connect(self._on_name_changed)
        name_layout.addWidget(name_label)
        name_layout.addWidget(self._name_input)
        layout.addLayout(name_layout)
        return self._name_input

    def _add_warning_label(self, layout: QVBoxLayout) -> QLabel:
        """Add warning label to layout."""
        self._warning_label = QLabel()
        self._warning_label.setStyleSheet(
            "color: #f59e0b; font-size: 13px; padding: 10px; "
            "background-color: #2a2a1a; border-radius: 4px;"
        )
        self._warning_label.setWordWrap(True)
        self._warning_label.setVisible(False)
        layout.addWidget(self._warning_label)
        return self._warning_label

    def _add_progress_bar(self, layout: QVBoxLayout) -> QProgressBar:
        """Add progress bar to layout."""
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)
        return self._progress_bar

    def _add_buttons(self, layout: QVBoxLayout):
        """Add buttons to layout."""
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self._cancel_btn = QPushButton(t("cancel"))
        self._cancel_btn.setProperty("role", "cancel")
        self._cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self._cancel_btn)

        self._rename_btn = QPushButton(t("rename"))
        self._rename_btn.clicked.connect(self._on_rename_clicked)
        button_layout.addWidget(self._rename_btn)

        layout.addLayout(button_layout)

    def _on_name_changed(self, text: str):
        """Handle name input change."""
        self._check_for_existing()

    def _on_rename_clicked(self):
        """Handle rename button click - common validation."""
        new_name = self._name_input.text().strip()

        if not new_name:
            QMessageBox.warning(self, t("warning"), self._get_empty_warning())
            return

        if new_name == self._get_original_name():
            QMessageBox.warning(self, t("warning"), t("name_unchanged"))
            return

        # Check for merge scenario
        if self._warning_label.isVisible():
            confirm = QMessageBox.question(
                self,
                t("confirm_merge"),
                self._get_merge_confirm_message(),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if confirm != QMessageBox.Yes:
                return
        else:
            # Normal rename confirmation
            confirm = QMessageBox.question(
                self,
                t("confirm_rename"),
                self._get_rename_confirm_message(new_name),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if confirm != QMessageBox.Yes:
                return

        # Start the rename operation
        self._start_rename(new_name)

    def _start_rename(self, new_name: str):
        """Start the rename operation in background thread."""
        self._rename_btn.setEnabled(False)
        self._cancel_btn.setEnabled(False)
        self._name_input.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._progress_bar.setRange(0, 0)  # Indeterminate

        self._worker = self._create_worker(new_name)
        self._worker.finished.connect(self._on_rename_finished)
        self._worker.start()

    def _on_rename_finished(self, result: dict):
        """Handle rename operation completion."""
        self._progress_bar.setVisible(False)
        self._rename_btn.setEnabled(True)
        self._cancel_btn.setEnabled(True)
        self._name_input.setEnabled(True)

        updated = result.get('updated_tracks', 0)
        errors = result.get('errors', [])
        merged = result.get('merged', False)

        if errors:
            error_msg = "\n".join(errors[:5])  # Show first 5 errors
            if len(errors) > 5:
                error_msg += f"\n... {len(errors) - 5} more errors"
            QMessageBox.warning(
                self,
                t("partial_success") if updated > 0 else t("error"),
                f"{t('updated_count')}: {updated}\n\n{error_msg}"
            )

        if updated > 0:
            msg = self._get_success_message(merged)
            QMessageBox.information(
                self,
                t("success"),
                f"{msg}: {updated} {t('tracks_updated')}"
            )
            self._emit_success_signal()
            self.accept()

        if self._worker:
            self._worker.deleteLater()
            self._worker = None

    def closeEvent(self, event):
        """Handle dialog close."""
        if self._worker and self._worker.isRunning():
            self._worker.wait()
        super().closeEvent(event)

    # ========================================================================
    # Abstract Methods (Subclasses must implement)
    # ========================================================================

    @abstractmethod
    def _check_for_existing(self):
        """Check if the new name already exists."""
        pass

    @abstractmethod
    def _get_original_name(self) -> str:
        """Get the original name being renamed."""
        pass

    @abstractmethod
    def _get_empty_warning(self) -> str:
        """Get warning message for empty name."""
        pass

    @abstractmethod
    def _get_merge_confirm_message(self) -> str:
        """Get confirmation message for merge scenario."""
        pass

    @abstractmethod
    def _get_rename_confirm_message(self, new_name: str) -> str:
        """Get confirmation message for rename."""
        pass

    @abstractmethod
    def _create_worker(self, new_name: str) -> BaseRenameWorker:
        """Create the worker thread for rename operation."""
        pass

    @abstractmethod
    def _get_success_message(self, merged: bool) -> str:
        """Get success message after rename."""
        pass

    @abstractmethod
    def _emit_success_signal(self):
        """Emit success signal with appropriate parameters."""
        pass
