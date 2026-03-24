"""
Artist rename dialog for renaming artists and merging duplicates.
"""

import logging

from PySide6.QtCore import Signal

from domain.artist import Artist
from services.library import LibraryService
from system.i18n import t
from ui.dialogs.base_rename_dialog import BaseRenameDialog, BaseRenameWorker

logger = logging.getLogger(__name__)


class RenameArtistWorker(BaseRenameWorker):
    """Worker thread for renaming artist."""

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


class ArtistRenameDialog(BaseRenameDialog):
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

        self._setup_ui()
        self._check_for_existing()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = self._setup_common_ui(t("rename_artist"))

        # Info label
        track_count = self._artist.song_count
        info_text = f"{t('rename_artist_info')}: {track_count} {t('tracks')}"
        self._add_info_label(layout, info_text)

        # Artist name input
        self._name_input = self._add_name_input(layout, t("artist_name") + ":", self._artist.name)

        # Warning label
        self._add_warning_label(layout)

        # Progress bar
        self._add_progress_bar(layout)

        # Buttons
        self._add_buttons(layout)

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

    def _get_original_name(self) -> str:
        return self._artist.name

    def _get_empty_warning(self) -> str:
        return t("enter_artist_name")

    def _get_merge_confirm_message(self) -> str:
        return t("artist_merge_confirm")

    def _get_rename_confirm_message(self, new_name: str) -> str:
        return (
            f"{t('rename_artist_confirm')}\n\n"
            f"{self._artist.name} → {new_name}\n\n"
            f"{self._artist.song_count} {t('tracks_affected')}"
        )

    def _create_worker(self, new_name: str) -> RenameArtistWorker:
        return RenameArtistWorker(
            self._library,
            self._artist.name,
            new_name
        )

    def _get_success_message(self, merged: bool) -> str:
        return t("artist_merged") if merged else t("artist_renamed")

    def _emit_success_signal(self):
        self.artist_renamed.emit(self._artist.name, self._name_input.text().strip())
