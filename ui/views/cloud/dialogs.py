"""
Dialogs for cloud file operations.
"""

import logging
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QDialogButtonBox,
    QPushButton,
    QFormLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from ui.dialogs.message_dialog import MessageDialog
from domain.cloud import CloudFile
from services import MetadataService
from system.i18n import t

if TYPE_CHECKING:
    from services.library import LibraryService

logger = logging.getLogger(__name__)


class CloudMediaInfoDialog(QDialog):
    """
    Dialog for editing media info of downloaded cloud files.

    Allows editing title, artist, and album metadata.
    Updates both the file and the database.
    """

    _STYLE_TEMPLATE = """
        QDialog {
            background-color: %background_hover%;
            color: %text%;
        }
        QLabel {
            color: %text%;
            font-size: 13px;
        }
        QLineEdit {
            background-color: %background_alt%;
            color: %text%;
            border: 1px solid %border%;
            border-radius: 4px;
            padding: 8px;
            font-size: 13px;
        }
        QLineEdit:focus {
            border: 1px solid %highlight%;
        }
        QPushButton {
            background-color: %highlight%;
            color: %background%;
            border: none;
            padding: 8px 20px;
            border-radius: 4px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: %highlight_hover%;
        }
        QPushButton[role="cancel"] {
            background-color: %border%;
            color: %text%;
        }
        QPushButton[role="cancel"]:hover {
            background-color: %background_hover%;
        }
    """

    def __init__(
        self,
        file: CloudFile,
        library_service: "LibraryService",
        parent=None
    ):
        """
        Initialize the media info dialog.

        Args:
            file: CloudFile to edit (must have local_path)
            library_service: Library service for database updates
            parent: Parent widget
        """
        super().__init__(parent)
        self._file = file
        self._library_service = library_service

        self.setWindowTitle(f"{t('edit_media_info_title')} - {file.name}")
        self.setMinimumWidth(450)

        # Register for theme change notifications
        from system.theme import ThemeManager
        ThemeManager.instance().register_widget(self)
        self._setup_ui()

    def _setup_ui(self):
        """Setup the dialog UI."""
        from system.theme import ThemeManager
        self.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TEMPLATE))

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        form_layout.setLabelAlignment(Qt.AlignRight)

        # Extract current metadata from file
        current_metadata = MetadataService.extract_metadata(self._file.local_path)

        # Title field
        self._title_input = QLineEdit(current_metadata.get("title") or self._file.name)
        self._title_input.setPlaceholderText(t("enter_title"))
        form_layout.addRow(t("title") + ":", self._title_input)

        # Artist field
        self._artist_input = QLineEdit(current_metadata.get("artist") or "")
        self._artist_input.setPlaceholderText(t("enter_artist"))
        form_layout.addRow(t("artist") + ":", self._artist_input)

        # Album field
        self._album_input = QLineEdit(current_metadata.get("album") or "")
        self._album_input.setPlaceholderText(t("enter_album"))
        form_layout.addRow(t("album") + ":", self._album_input)

        # File info section
        self._add_file_info(form_layout)

        layout.addLayout(form_layout)

        # Buttons
        buttons = QDialogButtonBox()
        ok_button = QPushButton(t("save"))
        cancel_button = QPushButton(t("cancel"))
        cancel_button.setProperty("role", "cancel")

        buttons.addButton(ok_button, QDialogButtonBox.AcceptRole)
        buttons.addButton(cancel_button, QDialogButtonBox.RejectRole)
        ok_button.clicked.connect(self._save_changes)
        cancel_button.clicked.connect(self.reject)

        layout.addWidget(buttons)

    def _add_file_info(self, form_layout: QFormLayout):
        """Add file information section to the form."""
        from system.theme import ThemeManager
        theme = ThemeManager.instance().current_theme

        try:
            track_file = Path(self._file.local_path)
            file_size = track_file.stat().st_size
            file_size_str = self._format_file_size(file_size)

            # Get audio codec info using mutagen
            import mutagen

            audio_info = mutagen.File(self._file.local_path)
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
                elif hasattr(audio_info, "type"):
                    media_info.append(audio_info.type)

            # Create info text
            file_info_text = file_size_str
            if media_info:
                file_info_text += f" | {' | '.join(media_info)}"

            info_label = QLabel(file_info_text)
            info_label.setStyleSheet(f"color: {theme.text_secondary}; font-size: 11px;")

            # File path
            path_label = QLabel(self._file.local_path)
            path_label.setStyleSheet(f"color: {theme.text_secondary}; font-size: 10px;")
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
            logger.error(f"Error showing file info: {e}", exc_info=True)
            path_label = QLabel(self._file.local_path)
            path_label.setStyleSheet(f"color: {theme.text_secondary}; font-size: 11px;")
            path_label.setWordWrap(True)
            form_layout.addRow(t("file") + ":", path_label)

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

    def _save_changes(self):
        """Save the changes to file and database."""
        new_title = self._title_input.text().strip() or self._file.name
        new_artist = self._artist_input.text().strip()
        new_album = self._album_input.text().strip()

        # Save to file
        success = MetadataService.save_metadata(
            self._file.local_path,
            title=new_title,
            artist=new_artist,
            album=new_album,
        )

        if success:
            # Update tracks table in database via LibraryService
            track = self._library_service.get_track_by_cloud_file_id(self._file.file_id)
            if track:
                self._library_service.update_track_metadata(
                    track.id,
                    title=new_title,
                    artist=new_artist,
                    album=new_album
                )
            else:
                # Check if track exists by path
                track = self._library_service.get_track_by_path(self._file.local_path)
                if track:
                    self._library_service.update_track_metadata(
                        track.id,
                        title=new_title,
                        artist=new_artist,
                        album=new_album
                    )

            self.accept()
        else:
            MessageDialog.warning(self, t("error"), t("failed_to_save_metadata"))

    def refresh_theme(self):
        """Apply themed styles using ThemeManager tokens."""
        from system.theme import ThemeManager
        self.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TEMPLATE))


def show_media_info_dialog(
    file: CloudFile,
    library_service: "LibraryService",
    parent=None
) -> bool:
    """
    Show the media info dialog and return True if changes were saved.

    Args:
        file: CloudFile to edit
        library_service: Library service for database updates
        parent: Parent widget

    Returns:
        True if changes were saved, False otherwise
    """
    if not file.local_path:
        MessageDialog.warning(parent, t("error"), t("file_not_downloaded"))
        return False

    dialog = CloudMediaInfoDialog(file, library_service, parent)
    return dialog.exec() == QDialog.Accepted
