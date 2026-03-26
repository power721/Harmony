"""
Dialog for editing media information for tracks.
"""
import logging
from pathlib import Path
from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QDialogButtonBox,
    QFormLayout,
    QCheckBox,
    QProgressBar,
    QPushButton,
    QMessageBox,
    QWidget,
)

from services import MetadataService
from system.i18n import t
from system.event_bus import EventBus

logger = logging.getLogger(__name__)


class EditMediaInfoDialog(QDialog):
    """Dialog for editing media information for one or more tracks."""

    tracks_updated = Signal(list)  # Emitted when tracks are updated with list of track IDs

    def __init__(self, track_ids: List[int], library_service, parent=None):
        """
        Initialize the dialog.

        Args:
            track_ids: List of track IDs to edit
            library_service: Library service for track operations
            parent: Parent widget
        """
        super().__init__(parent)
        self._track_ids = track_ids
        self._library_service = library_service
        self._is_batch_edit = len(track_ids) > 1

        self._setup_ui()

    def _setup_ui(self):
        """Setup the user interface."""
        if self._is_batch_edit:
            self.setWindowTitle(
                f"{t('edit_media_info_title')} ({len(self._track_ids)} {t('tracks')})"
            )
        else:
            self.setWindowTitle(t("edit_media_info_title"))
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
                padding: 8px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #1db954;
            }
            QCheckBox {
                color: #ffffff;
                font-size: 13px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:checked {
                background-color: #1db954;
                border: 2px solid #1db954;
                border-radius: 3px;
            }
            QCheckBox::indicator:unchecked {
                background-color: #181818;
                border: 2px solid #404040;
                border-radius: 3px;
            }
            QPushButton {
                background-color: #1db954;
                color: #000000;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1ed760;
            }
            QPushButton[role="cancel"] {
                background-color: #404040;
                color: #ffffff;
            }
            QPushButton[role="cancel"]:hover {
                background-color: #505050;
            }
            QPushButton:disabled {
                background-color: #404040;
                color: #808080;
            }
        """)

        layout = QVBoxLayout(self)

        # Get first track for initial values
        first_track = self._library_service.get_track(self._track_ids[0])
        if not first_track:
            self.reject()
            return

        # Info label for batch edit
        if self._is_batch_edit:
            info_label = QLabel(
                f"{t('batch_edit_info')}: {len(self._track_ids)} {t('tracks')}"
            )
            info_label.setStyleSheet(
                "color: #1db954; font-size: 14px; padding: 10px; background-color: #1a1a1a; border-radius: 4px;"
            )
            layout.addWidget(info_label)

        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        form_layout.setLabelAlignment(Qt.AlignRight)

        # Only show title field for single track edit
        self._title_input = None
        if not self._is_batch_edit:
            self._title_input = QLineEdit(first_track.title or "")
            self._title_input.setPlaceholderText(t("enter_title"))
            form_layout.addRow(t("title") + ":", self._title_input)

        self._artist_input = QLineEdit(first_track.artist or "")
        self._artist_input.setPlaceholderText(t("enter_artist"))
        self._album_input = QLineEdit(first_track.album or "")
        self._album_input.setPlaceholderText(t("enter_album"))

        # For batch edit, add checkboxes to control which fields to update
        if self._is_batch_edit:
            self._update_artist_cb = QCheckBox(t("update_artist"))
            self._update_artist_cb.setChecked(True)
            self._update_album_cb = QCheckBox(t("update_album"))
            self._update_album_cb.setChecked(True)

            form_layout.addRow(t("artist") + ":", self._artist_input)
            form_layout.addRow("", self._update_artist_cb)
            form_layout.addRow(t("album") + ":", self._album_input)
            form_layout.addRow("", self._update_album_cb)
        else:
            form_layout.addRow(t("artist") + ":", self._artist_input)
            form_layout.addRow(t("album") + ":", self._album_input)

            # Show file information for single track
            self._add_file_info(form_layout, first_track)

        layout.addLayout(form_layout)

        # Progress bar for batch edit
        self._progress_bar = None
        if self._is_batch_edit:
            self._progress_bar = QProgressBar()
            self._progress_bar.setVisible(False)
            self._progress_bar.setStyleSheet("""
                QProgressBar {
                    border: 2px solid #404040;
                    border-radius: 5px;
                    text-align: center;
                    color: #ffffff;
                }
                QProgressBar::chunk {
                    background-color: #1db954;
                    border-radius: 3px;
                }
            """)
            layout.addWidget(self._progress_bar)

        # Buttons
        buttons = QDialogButtonBox()
        self._ok_button = QPushButton(t("save"))
        self._ok_button.setObjectName("saveBtn")
        cancel_button = QPushButton(t("cancel"))
        cancel_button.setProperty("role", "cancel")

        buttons.addButton(self._ok_button, QDialogButtonBox.AcceptRole)
        buttons.addButton(cancel_button, QDialogButtonBox.RejectRole)

        self._ok_button.clicked.connect(self._save_changes)
        cancel_button.clicked.connect(self.reject)

        layout.addWidget(buttons)

        # Store first track for later use
        self._first_track = first_track

    def _add_file_info(self, form_layout: QFormLayout, track):
        """Add file information to the form for single track edit."""
        try:
            track_file = Path(track.path)
            file_size = track_file.stat().st_size
            file_size_str = self._format_file_size(file_size)

            # Get audio codec info using mutagen
            import mutagen

            audio_info = mutagen.File(track.path)
            media_info = []

            if audio_info and hasattr(audio_info, "info"):
                info = audio_info.info
                # Bitrate
                if hasattr(info, "bitrate") and info.bitrate:
                    media_info.append(f"{info.bitrate // 1000} kbps")

                # Sample rate
                if hasattr(info, "sample_rate") and info.sample_rate:
                    media_info.append(f"{info.sample_rate // 1000} kHz")

                # Length/Duration
                if hasattr(info, "length") and info.length:
                    minutes = int(info.length // 60)
                    seconds = int(info.length % 60)
                    media_info.append(f"{minutes}:{seconds:02d}")

            # Format (codec)
            if audio_info:
                mime_type = audio_info.mime if hasattr(audio_info, "mime") else []
                if mime_type:
                    format_str = mime_type[0].split("/")[-1].upper()
                    media_info.append(format_str)
                else:
                    # Try to get format from type
                    if hasattr(audio_info, "type"):
                        media_info.append(audio_info.type)

            # Create info text
            file_info_text = f"{file_size_str}"
            if media_info:
                file_info_text += f" | {' | '.join(media_info)}"

            info_label = QLabel(file_info_text)
            info_label.setStyleSheet("color: #808080; font-size: 11px;")

            # File path
            path_label = QLabel(track.path)
            path_label.setStyleSheet("color: #606060; font-size: 10px;")
            path_label.setWordWrap(True)

            # Add both labels in a vertical layout
            info_container = QWidget()
            info_layout = QVBoxLayout(info_container)
            info_layout.setContentsMargins(0, 0, 0, 0)
            info_layout.setSpacing(2)
            info_layout.addWidget(info_label)
            info_layout.addWidget(path_label)

            form_layout.addRow(t("file") + ":", info_container)

        except Exception as e:
            logger.error(f"Error displaying track info: {e}", exc_info=True)
            # Fallback to just show path if there's an error
            path_label = QLabel(track.path)
            path_label.setStyleSheet("color: #808080; font-size: 11px;")
            path_label.setWordWrap(True)
            form_layout.addRow(t("file") + ":", path_label)

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

    def _save_changes(self):
        """Save the changes to tracks."""
        if self._is_batch_edit:
            self._save_batch_edit()
        else:
            self._save_single_edit()

    def _save_batch_edit(self):
        """Save changes for batch edit mode."""
        new_artist = self._artist_input.text().strip()
        new_album = self._album_input.text().strip()

        if not self._update_artist_cb.isChecked() and not self._update_album_cb.isChecked():
            QMessageBox.warning(
                self, t("warning"), t("select_fields_to_update")
            )
            return

        if not new_artist and not new_album:
            QMessageBox.warning(self, t("warning"), t("enter_artist_or_album"))
            return

        # Show progress
        if self._progress_bar:
            self._progress_bar.setVisible(True)
            self._progress_bar.setMaximum(len(self._track_ids))
            self._ok_button.setEnabled(False)
            self._ok_button.setText(t("saving") + "...")

        success_count = 0
        for i, track_id in enumerate(self._track_ids):
            track = self._library_service.get_track(track_id)
            if not track:
                continue

            # Determine values to save
            save_artist = (
                new_artist
                if (self._update_artist_cb.isChecked() and new_artist)
                else track.artist
            )
            save_album = (
                new_album
                if (self._update_album_cb.isChecked() and new_album)
                else track.album
            )

            # Save to file
            success = MetadataService.save_metadata(
                track.path,
                title=track.title,
                artist=save_artist,
                album=save_album,
            )

            if success:
                self._library_service.update_track_metadata(
                    track_id,
                    title=track.title,
                    artist=save_artist,
                    album=save_album,
                )
                # Emit metadata_updated signal to update play_queue
                EventBus.instance().metadata_updated.emit(track_id)
                success_count += 1

            # Update progress
            if self._progress_bar:
                self._progress_bar.setValue(i + 1)

        if success_count > 0:
            QMessageBox.information(
                self,
                t("success"),
                f"{t('batch_save_success')}: {success_count}/{len(self._track_ids)}",
            )
            self.tracks_updated.emit(self._track_ids)
            self.accept()
        else:
            QMessageBox.warning(self, "Error", t("media_save_failed"))

    def _save_single_edit(self):
        """Save changes for single track edit mode."""
        new_title = self._title_input.text().strip() or self._first_track.title
        new_artist = self._artist_input.text().strip() or self._first_track.artist
        new_album = self._album_input.text().strip() or self._first_track.album

        success = MetadataService.save_metadata(
            self._first_track.path,
            title=new_title,
            artist=new_artist,
            album=new_album,
        )

        if success:
            self._library_service.update_track_metadata(
                self._track_ids[0],
                title=new_title,
                artist=new_artist,
                album=new_album,
            )
            # Emit metadata_updated signal to update play_queue
            EventBus.instance().metadata_updated.emit(self._track_ids[0])
            QMessageBox.information(self, t("success"), t("media_saved"))
            self.tracks_updated.emit(self._track_ids)
            self.accept()
        else:
            QMessageBox.warning(self, "Error", t("media_save_failed"))

    def get_updated_track_ids(self) -> List[int]:
        """Get the list of track IDs that were updated."""
        return self._track_ids
