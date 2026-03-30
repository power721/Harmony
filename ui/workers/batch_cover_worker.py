"""
Worker threads for batch downloading artist and album covers.
"""
import logging
import time

from PySide6.QtCore import QThread, Signal

from infrastructure.network import HttpClient

logger = logging.getLogger(__name__)


class BatchArtistCoverWorker(QThread):
    """Worker thread for batch downloading artist covers."""

    progress = Signal(int, int)  # current, total
    item_progress = Signal(str)  # current artist name
    finished_signal = Signal(int, int)  # success_count, failed_count

    def __init__(self, cover_service, library_service, artists):
        super().__init__()
        self._cover_service = cover_service
        self._library_service = library_service
        self._artists = artists
        self._cancelled = False

    def run(self):
        if not self._artists:
            self.finished_signal.emit(0, 0)
            return

        self.progress.emit(0, len(self._artists))
        success = 0
        failed = 0

        for i, artist in enumerate(self._artists):
            if self._cancelled:
                break

            self.item_progress.emit(artist.name)
            self.progress.emit(i, len(self._artists))

            try:
                cover_path = self._fetch_artist_cover(artist.name)
                if cover_path:
                    self._library_service.update_artist_cover(
                        artist.name, cover_path
                    )
                    success += 1
                else:
                    failed += 1
            except Exception as e:
                logger.warning(f"Failed to download cover for artist '{artist.name}': {e}")
                failed += 1

            time.sleep(0.5)

        self.progress.emit(len(self._artists), len(self._artists))
        self.finished_signal.emit(success, failed)

    def cancel(self):
        self._cancelled = True

    def _fetch_artist_cover(self, artist_name: str):
        """Search and download artist cover using dedicated artist search."""
        results = self._cover_service.search_artist_covers(artist_name, limit=5)
        if not results:
            return None

        best = results[0]  # Already sorted by score descending
        cover_url = best.get('cover_url')
        source = best.get('source', '')
        singer_mid = best.get('singer_mid')

        # QQ Music: cover_url may be empty, construct from singer_mid
        if not cover_url and source == 'qqmusic' and singer_mid:
            from services.lyrics.qqmusic_lyrics import get_qqmusic_artist_cover_url
            cover_url = get_qqmusic_artist_cover_url(singer_mid, size=500)

        if not cover_url:
            return None

        # Download cover data
        http_client = HttpClient()
        cover_data = http_client.get_content(cover_url, timeout=10)
        if not cover_data:
            return None

        return self._cover_service.save_cover_data_to_cache(
            cover_data, artist_name, "", ""
        )


class BatchAlbumCoverWorker(QThread):
    """Worker thread for batch downloading album covers."""

    progress = Signal(int, int)  # current, total
    item_progress = Signal(str)  # current album name
    finished_signal = Signal(int, int)  # success_count, failed_count

    def __init__(self, cover_service, library_service, albums):
        super().__init__()
        self._cover_service = cover_service
        self._library_service = library_service
        self._albums = albums
        self._cancelled = False

    def run(self):
        if not self._albums:
            self.finished_signal.emit(0, 0)
            return

        self.progress.emit(0, len(self._albums))
        success = 0
        failed = 0

        for i, album in enumerate(self._albums):
            if self._cancelled:
                break

            label = f"{album.artist} - {album.name}"
            self.item_progress.emit(label)
            self.progress.emit(i, len(self._albums))

            try:
                cover_path = self._cover_service.fetch_online_cover(
                    title="", artist=album.artist, album=album.name
                )
                if cover_path:
                    self._library_service.update_album_cover(
                        album.name, album.artist, cover_path
                    )
                    success += 1
                else:
                    failed += 1
            except Exception as e:
                logger.warning(f"Failed to download cover for album '{label}': {e}")
                failed += 1

            time.sleep(0.5)

        self.progress.emit(len(self._albums), len(self._albums))
        self.finished_signal.emit(success, failed)

    def cancel(self):
        self._cancelled = True
