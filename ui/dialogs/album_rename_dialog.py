"""
Album rename dialog for renaming albums and merging duplicates.
"""

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFormLayout, QLineEdit

from domain.album import Album
from services.library import LibraryService
from system.i18n import t
from ui.dialogs.base_rename_dialog import BaseRenameDialog, BaseRenameWorker

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class RenameAlbumWorker(BaseRenameWorker):
    """Worker thread for renaming album."""

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


class AlbumRenameDialog(BaseRenameDialog):
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

        self._setup_ui()
        self._check_for_existing()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = self._setup_common_ui(t("rename_album"))

        # Info label
        track_count = self._album.song_count
        info_text = f"{t('rename_album_info')}: {track_count} {t('tracks')}"
        self._add_info_label(layout, info_text)

        # Form layout for inputs
        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        form_layout.setLabelAlignment(Qt.AlignRight)

        # Album name input
        self._name_input = self._add_name_input(layout, t("album_name") + ":", self._album.name)

        # Artist name (read-only)
        artist_input = QLineEdit(self._album.artist)
        artist_input.setReadOnly(True)
        form_layout.addRow(t("artist") + ":", artist_input)

        layout.addLayout(form_layout)

        # Warning label
        self._add_warning_label(layout)

        # Progress bar
        self._add_progress_bar(layout)

        # Buttons
        self._add_buttons(layout)

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

    def _get_original_name(self) -> str:
        return self._album.name

    def _get_empty_warning(self) -> str:
        return t("enter_album_name")

    def _get_merge_confirm_message(self) -> str:
        return t("album_merge_confirm")

    def _get_rename_confirm_message(self, new_name: str) -> str:
        return (
            f"{t('rename_album_confirm')}\n\n"
            f"{self._album.name} → {new_name}\n"
            f"({self._album.artist})\n\n"
            f"{self._album.song_count} {t('tracks_affected')}"
        )

    def _create_worker(self, new_name: str) -> RenameAlbumWorker:
        return RenameAlbumWorker(
            self._library,
            self._album.name,
            self._album.artist,
            new_name
        )

    def _get_success_message(self, merged: bool) -> str:
        return t("album_merged") if merged else t("album_renamed")

    def _emit_success_signal(self):
        self.album_renamed.emit(
            self._album.name,
            self._album.artist,
            self._name_input.text().strip()
        )
