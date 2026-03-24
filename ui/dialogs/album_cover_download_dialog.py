"""
Album cover download dialog for downloading album covers.
"""
import logging
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem

from domain.album import Album
from services.metadata import CoverService
from system.event_bus import EventBus
from system.i18n import t
from ui.dialogs.base_cover_download_dialog import (
    BaseCoverDownloadDialog, CoverDownloadThread
)

logger = logging.getLogger(__name__)


class AlbumCoverSearchThread(BaseCoverDownloadDialog):
    """Thread for searching album covers."""
    # Note: Using inline thread definition for simplicity

    pass


class AlbumCoverDownloadDialog(BaseCoverDownloadDialog):
    """Dialog for downloading album covers."""

    def __init__(self, album: Album, cover_service: CoverService, parent=None):
        super().__init__(cover_service, parent)
        self._album = album
        self._setup_ui()
        self._search_covers()

    def _setup_ui(self):
        """Setup the dialog UI."""
        info_text = f"<b>{self._album.display_name}</b> - {self._album.display_artist}"
        self._setup_common_ui(info_text, cover_size=350, circular=False)

    def _search_covers(self):
        """Search for album covers."""
        if self._search_thread and self._search_thread.isRunning():
            return

        # Update UI
        self._search_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)  # Indeterminate progress
        self._status_label.setText(t("searching"))
        self._results_list.clear()
        self._search_results = []
        self._save_btn.setEnabled(False)

        # Start search thread
        from PySide6.QtCore import QThread, Signal

        class AlbumCoverSearchThread(QThread):
            search_completed = Signal(list)
            search_failed = Signal(str)

            def __init__(self, cover_service: CoverService, album: Album):
                super().__init__()
                self.cover_service = cover_service
                self.album = album

            def run(self):
                try:
                    results = self.cover_service.search_covers(
                        title="",  # Empty title for album search
                        artist=self.album.artist,
                        album=self.album.name,
                        duration=None
                    )
                    self.search_completed.emit(results)
                except Exception as e:
                    logger.error(f"Error searching album covers: {e}", exc_info=True)
                    self.search_failed.emit(f"{t('error')}: {str(e)}")

        self._search_thread = AlbumCoverSearchThread(
            self._cover_service,
            self._album
        )
        self._search_thread.search_completed.connect(self._on_search_completed)
        self._search_thread.search_failed.connect(self._on_search_failed)
        self._search_thread.start()

    def _on_search_completed(self, results: list):
        """Handle search completion."""
        self._on_search_completed_base(results)

    def _on_search_failed(self, error_message: str):
        """Handle search failure."""
        self._on_search_failed_base(error_message)

    def _format_result_display(self, result: dict) -> str:
        """Format search result for display in list."""
        title = result.get('title', '')
        artist = result.get('artist', '')
        album = result.get('album', '')
        source = result.get('source', '')
        score = result.get('score', 0)

        display = f"{album or title}"
        if artist:
            display += f" - {artist}"
        display += f" [{source}] [{score:.0f}%]"
        return display

    def _on_result_selected(self, item: QListWidgetItem):
        """Handle result selection - download and display cover."""
        result = item.data(Qt.UserRole)
        cover_url = result.get('cover_url')
        source = result.get('source', '')
        album_mid = result.get('album_mid')
        song_mid = result.get('id')

        # For QQ Music, fetch cover URL lazily
        if not cover_url and source == 'qqmusic':
            if album_mid or song_mid:
                self._fetch_qqmusic_cover(album_mid, song_mid, result)
                return
            else:
                logger.warning("QQ Music result has no album_mid or song_mid")
                self._status_label.setText(t("cover_load_failed"))
                return

        if not cover_url:
            return

        self._current_cover_url = cover_url
        score = result.get('score', 0)

        # Update score display
        self._score_label.setText(f"{t('match_score')}: {score:.0f}%")

        # Download cover preview
        if self._download_thread and self._download_thread.isRunning():
            self._download_thread.terminate()
            self._download_thread.wait()

        self._progress.setVisible(True)
        self._progress.setRange(0, 0)
        self._status_label.setText(t("downloading"))

        self._download_thread = CoverDownloadThread(
            self._cover_service,
            cover_url,
            source
        )
        self._download_thread.cover_downloaded.connect(self._on_cover_downloaded)
        self._download_thread.download_failed.connect(self._on_download_failed)
        self._download_thread.finished.connect(self._on_download_finished)
        self._download_thread.start()

    def _fetch_qqmusic_cover(self, album_mid: str, song_mid: str, result: dict):
        """Fetch QQ Music cover URL lazily and download."""
        self._fetch_qqmusic_cover_base(album_mid=album_mid, song_mid=song_mid, result=result)

    def _on_cover_downloaded(self, cover_data: bytes, source: str):
        """Handle successful cover download."""
        self._on_cover_downloaded_base(cover_data, source, circular=False)

    def _save_cover(self):
        """Save cover to cache and update database."""
        if not self._current_cover_data:
            return

        # Save cover to cache
        cover_path = self._cover_service.save_cover_data_to_cache(
            self._current_cover_data,
            self._album.artist,
            "",  # title
            self._album.name
        )

        if cover_path:
            # Update albums in database via LibraryService
            from app import Application
            app = Application.instance()
            if app and app.bootstrap:
                app.bootstrap.library_service.update_album_cover(
                    self._album.name, self._album.artist, cover_path
                )

            # Emit signal
            self.cover_saved.emit(cover_path)

            # Notify listeners to refresh cover display
            bus = EventBus.instance()
            bus.cover_updated.emit(f"{self._album.name}:{self._album.artist}", False)

            # Close dialog after successful save
            self.accept()
        else:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                t("error"),
                t("cover_save_failed")
            )
