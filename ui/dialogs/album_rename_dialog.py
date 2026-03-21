"""
Album rename dialog for renaming albums and merging duplicates.
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
    QFormLayout,
)
from PySide6.QtCore import Qt, Signal, QThread

from domain.album import Album
from services.library import LibraryService
from system.i18n import t

logger = logging.getLogger(__name__)


class RenameAlbumWorker(QThread):
    """Worker thread for renaming album."""
    finished = Signal(dict)  # Result dict
    progress = Signal(int, int)  # current, total

    def __init__(
        self,
        library_service: LibraryService,
        old_name: str,
        artist: str,
        new_name: str,
        parent=None
    ):
        super().__init__(parent)
        self._library = library_service
        self._old_name = old_name
        self._artist = artist
        self._new_name = new_name

    def run(self):
        result = self._library.rename_album(self._old_name, self._artist, self._new_name)
        self.finished.emit(result)


class AlbumRenameDialog(QDialog):
    """
    Dialog for renaming an album.

    Features:
    - Shows current album name with editable input
    - Shows artist name (read-only, for reference)
    - Displays track count that will be affected
    - Warns about merge scenario if new name already exists
    - Progress bar during operation
    """

    album_renamed = Signal(str, str, str)  # old_name, artist, new_name

    def __init__(
        self,
        album: Album,
        library_service: LibraryService,
        parent=None
    ):
        super().__init__(parent)
        self._album = album
        self._library = library_service
        self._worker = None

        self._setup_ui()
        self._check_for_existing()

    def _setup_ui(self):
        """Set up the dialog UI."""
        self.setWindowTitle(t("rename_album"))
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
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Info label
        track_count = self._album.song_count
        info_text = f"{t('rename_album_info')}: {track_count} {t('tracks')}"
        info_label = QLabel(info_text)
        info_label.setStyleSheet(
            "color: #1db954; font-size: 14px; padding: 12px; "
            "background-color: #1a1a1a; border-radius: 6px;"
        )
        layout.addWidget(info_label)

        # Form layout for inputs
        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        form_layout.setLabelAlignment(Qt.AlignRight)

        # Album name input
        self._name_input = QLineEdit(self._album.name)
        self._name_input.setPlaceholderText(t("enter_album_name"))
        self._name_input.textChanged.connect(self._on_name_changed)
        form_layout.addRow(t("album_name") + ":", self._name_input)

        # Artist name (read-only)
        artist_input = QLineEdit(self._album.artist)
        artist_input.setReadOnly(True)
        form_layout.addRow(t("artist") + ":", artist_input)

        layout.addLayout(form_layout)

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
        """Check if the new name already exists for this artist."""
        current_name = self._name_input.text().strip()
        if current_name and current_name != self._album.name:
            # Check if this album name already exists for this artist
            existing_tracks = self._library.get_album_tracks(current_name, self._album.artist)
            if existing_tracks:
                self._warning_label.setText(
                    f"{t('album_merge_warning')}: {len(existing_tracks)} {t('tracks')}"
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
            QMessageBox.warning(self, t("warning"), t("enter_album_name"))
            return

        if new_name == self._album.name:
            QMessageBox.warning(self, t("warning"), t("name_unchanged"))
            return

        # Confirm merge scenario
        if self._warning_label.isVisible():
            confirm = QMessageBox.question(
                self,
                t("confirm_merge"),
                t("album_merge_confirm"),
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
                f"{t('rename_album_confirm')}\n\n"
                f"{self._album.name} → {new_name}\n"
                f"({self._album.artist})\n\n"
                f"{self._album.song_count} {t('tracks_affected')}",
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

        self._worker = RenameAlbumWorker(
            self._library,
            self._album.name,
            self._album.artist,
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
            msg = t("album_merged") if merged else t("album_renamed")
            QMessageBox.information(
                self,
                t("success"),
                f"{msg}: {updated} {t('tracks_updated')}"
            )
            self.album_renamed.emit(self._album.name, self._album.artist, self._name_input.text().strip())
            self.accept()

        if self._worker:
            self._worker.deleteLater()
            self._worker = None

    def closeEvent(self, event):
        """Handle dialog close."""
        if self._worker and self._worker.isRunning():
            self._worker.wait()
        super().closeEvent(event)
