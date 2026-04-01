"""
Genre rename dialog for renaming genres and merging duplicates.
"""

import logging

from PySide6.QtCore import Signal

from domain.genre import Genre
from services.library import LibraryService
from system.i18n import t
from ui.dialogs.base_rename_dialog import BaseRenameDialog, BaseRenameWorker

logger = logging.getLogger(__name__)


class RenameGenreWorker(BaseRenameWorker):
    """Worker thread for renaming genre."""

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
        result = self._library.rename_genre(self._old_name, self._new_name)
        self.finished.emit(result)


class GenreRenameDialog(BaseRenameDialog):
    """
    Dialog for renaming a genre.

    Features:
    - Shows current genre name with editable input
    - Displays track count that will be affected
    - Warns about merge scenario if new name already exists
    - Progress bar during operation
    """

    genre_renamed = Signal(str, str)  # old_name, new_name

    def __init__(
            self,
            genre: Genre,
            library_service: LibraryService,
            parent=None
    ):
        super().__init__(parent)
        self._genre = genre
        self._library = library_service

        self._setup_ui()
        self._check_for_existing()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = self._setup_common_ui(t("rename_genre"))

        # Info label
        track_count = self._genre.song_count
        info_text = f"{t('rename_genre_info')}: {track_count} {t('tracks')}"
        self._add_info_label(layout, info_text)

        # Genre name input
        self._name_input = self._add_name_input(layout, t("genre_name") + ":", self._genre.name)

        # Warning label
        self._add_warning_label(layout)

        # Progress bar
        self._add_progress_bar(layout)

        # Buttons
        self._add_buttons(layout)

    def _check_for_existing(self):
        """Check if the new name already exists."""
        current_name = self._name_input.text().strip()
        if current_name and current_name != self._genre.name:
            existing = self._library.get_genre_by_name(current_name)
            if existing:
                self._warning_label.setText(
                    f"{t('genre_merge_warning')}: {existing.song_count} {t('tracks')}"
                )
                self._warning_label.setVisible(True)
                return
        self._warning_label.setVisible(False)

    def _get_original_name(self) -> str:
        return self._genre.name

    def _get_empty_warning(self) -> str:
        return t("enter_genre_name")

    def _get_merge_confirm_message(self) -> str:
        return t("genre_merge_confirm")

    def _get_rename_confirm_message(self, new_name: str) -> str:
        return (
            f"{t('rename_genre_confirm')}\n\n"
            f"{self._genre.name} → {new_name}\n\n"
            f"{self._genre.song_count} {t('tracks_affected')}"
        )

    def _create_worker(self, new_name: str) -> RenameGenreWorker:
        return RenameGenreWorker(
            self._library,
            self._genre.name,
            new_name
        )

    def _get_success_message(self, merged: bool) -> str:
        return t("genre_merged") if merged else t("genre_renamed")

    def _emit_success_signal(self):
        self.genre_renamed.emit(self._genre.name, self._name_input.text().strip())
