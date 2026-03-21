"""
Artist rename dialog for renaming artists and merging duplicates.
"""

import logging
from typing import Optional, Callable

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QProgressBar,
    QMessageBox,
    QFrame,
)
from PySide6.QtCore import Qt, Signal, QThread

from domain.artist import Artist
from services.library import LibraryService
from system.i18n import t

logger = logging.getLogger(__name__)


class RenameArtistWorker(QThread):
    """Worker thread for renaming artist."""
    finished = Signal(dict)  # Result dict
    progress = Signal(int, int)  # current, total

    def __init__(
        self,
        library_service: LibraryService,
        old_name: str,
        new_name: str,
        parent=None
    ):
        super().__init__(parent)
        self._library = library_service
        self._old_name = old_name
        self._new_name = new_name

    def run(self):
        result = self._library.rename_artist(self._old_name, self._new_name)
        self.finished.emit(result)


class ArtistRenameDialog(QDialog):
    """
    Dialog for renaming an artist.

    Features:
    - Shows current artist name with editable input
    - Displays track count that will be affected
    - Warns about merge scenario if new name already exists
    - Progress bar during operation
    """

    artist_renamed = Signal(str, str)  # old_name, new_name

    def __init__(
        self,
        artist: Artist,
        library_service: LibraryService,
        parent=None
    ):
        super().__init__(parent)
        self._artist = artist
        self._library = library_service
        self._worker = None

        self._setup_ui()
        self._check_for_existing()

    def _setup_ui(self):
        """Set up the dialog UI."""
        self.setWindowTitle(t("rename_artist"))
        self.setMinimumWidth(450)
        self.setStyleSheet("""
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
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Info label
        track_count = self._artist.song_count
        info_text = f"{t('rename_artist_info')}: {track_count} {t('tracks')}"
        info_label = QLabel(info_text)
        info_label.setStyleSheet(
            "color: #1db954; font-size: 14px; padding: 12px; "
            "background-color: #1a1a1a; border-radius: 6px;"
        )
        layout.addWidget(info_label)

        # Artist name input
        name_layout = QHBoxLayout()
        name_label = QLabel(t("artist_name") + ":")
        name_label.setFixedWidth(80)
        self._name_input = QLineEdit(self._artist.name)
        self._name_input.setPlaceholderText(t("enter_artist_name"))
        self._name_input.textChanged.connect(self._on_name_changed)
        name_layout.addWidget(name_label)
        name_layout.addWidget(self._name_input)
        layout.addLayout(name_layout)

        # Warning label (for merge scenario)
        self._warning_label = QLabel()
        self._warning_label.setStyleSheet(
            "color: #f59e0b; font-size: 13px; padding: 10px; "
            "background-color: #2a2a1a; border-radius: 4px;"
        )
        self._warning_label.setWordWrap(True)
        self._warning_label.setVisible(False)
        layout.addWidget(self._warning_label)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setStyleSheet("""
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
        """)
        layout.addWidget(self._progress_bar)

        # Buttons
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

    def _check_for_existing(self):
        """Check if the new name already exists."""
        current_name = self._name_input.text().strip()
        if current_name and current_name != self._artist.name:
            existing = self._library.get_artist_by_name(current_name)
            if existing:
                self._warning_label.setText(
                    f"{t('artist_merge_warning')}: {existing.song_count} {t('tracks')}"
                )
                self._warning_label.setVisible(True)
                return
        self._warning_label.setVisible(False)

    def _on_name_changed(self, text: str):
        """Handle name input change."""
        self._check_for_existing()

    def _on_rename_clicked(self):
        """Handle rename button click."""
        new_name = self._name_input.text().strip()

        if not new_name:
            QMessageBox.warning(self, t("warning"), t("enter_artist_name"))
            return

        if new_name == self._artist.name:
            QMessageBox.warning(self, t("warning"), t("name_unchanged"))
            return

        # Confirm merge scenario
        if self._warning_label.isVisible():
            confirm = QMessageBox.question(
                self,
                t("confirm_merge"),
                t("artist_merge_confirm"),
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
                f"{t('rename_artist_confirm')}\n\n"
                f"{self._artist.name} → {new_name}\n\n"
                f"{self._artist.song_count} {t('tracks_affected')}",
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

        self._worker = RenameArtistWorker(
            self._library,
            self._artist.name,
            new_name
        )
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
            msg = t("artist_merged") if merged else t("artist_renamed")
            QMessageBox.information(
                self,
                t("success"),
                f"{msg}: {updated} {t('tracks_updated')}"
            )
            self.artist_renamed.emit(self._artist.name, self._name_input.text().strip())
            self.accept()

        if self._worker:
            self._worker.deleteLater()
            self._worker = None

    def closeEvent(self, event):
        """Handle dialog close."""
        if self._worker and self._worker.isRunning():
            self._worker.wait()
        super().closeEvent(event)
