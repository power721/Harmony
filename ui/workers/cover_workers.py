"""
Workers for cover search / fetch / download.

Production-grade rules:
- No UI access in worker threads
- Cooperative cancellation via requestInterruption()
- Result delivery guarded by generation/token on dialog side
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QThread, Signal

from services.metadata import CoverService
from system.i18n import t

logger = logging.getLogger(__name__)


class BaseWorkerThread(QThread):
    """Base worker with cooperative interruption helpers."""

    failed = Signal(str)

    def _is_cancelled(self) -> bool:
        return self.isInterruptionRequested()

    def _emit_error(self, exc: Exception):
        logger.error("Worker failed: %s", exc, exc_info=True)
        self.failed.emit(f"{t('error')}: {str(exc)}")


class CoverSearchThread(BaseWorkerThread):
    """Search covers by metadata."""

    completed = Signal(list)

    def __init__(
        self,
        cover_service: CoverService,
        title: str = "",
        artist: str = "",
        album: str = "",
        duration: Optional[float] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._cover_service = cover_service
        self._title = title or ""
        self._artist = artist or ""
        self._album = album or ""
        self._duration = duration

    def run(self):
        try:
            if self._is_cancelled():
                return

            results = self._cover_service.search_covers(
                self._title,
                self._artist,
                self._album,
                self._duration,
            )

            if self._is_cancelled():
                return

            self.completed.emit(results or [])
        except Exception as e:
            self._emit_error(e)


class CoverDownloadThread(BaseWorkerThread):
    """Download cover bytes from direct cover URL."""

    completed = Signal(bytes, str)  # cover_data, source

    def __init__(self, cover_url: str, source: str = "", parent=None):
        super().__init__(parent)
        self._cover_url = cover_url
        self._source = source or ""

    def run(self):
        try:
            if self._is_cancelled():
                return

            from infrastructure.network import HttpClient

            http_client = HttpClient()
            cover_data = http_client.get_content(self._cover_url, timeout=10)

            if self._is_cancelled():
                return

            if cover_data:
                self.completed.emit(cover_data, self._source)
            else:
                self.failed.emit(t("cover_download_failed"))
        except Exception as e:
            self._emit_error(e)


class QQMusicCoverFetchThread(BaseWorkerThread):
    """Fetch QQ Music album/song cover URL lazily, then download bytes."""

    completed = Signal(bytes, str, float)  # cover_data, source, score

    def __init__(
        self,
        album_mid: str | None = None,
        song_mid: str | None = None,
        score: float = 0,
        parent=None,
    ):
        super().__init__(parent)
        self._album_mid = album_mid
        self._song_mid = song_mid
        self._score = score

    def run(self):
        try:
            from services.lyrics.qqmusic_lyrics import get_qqmusic_cover_url
            from infrastructure.network import HttpClient

            if self._is_cancelled():
                return

            if not self._album_mid and not self._song_mid:
                self.failed.emit(t("cover_load_failed"))
                return

            cover_url = None
            if self._album_mid:
                cover_url = get_qqmusic_cover_url(album_mid=self._album_mid, size=500)
            elif self._song_mid:
                cover_url = get_qqmusic_cover_url(mid=self._song_mid, size=500)

            if self._is_cancelled():
                return

            if not cover_url:
                self.failed.emit(t("cover_load_failed"))
                return

            http_client = HttpClient()
            cover_data = http_client.get_content(cover_url, timeout=10)

            if self._is_cancelled():
                return

            if cover_data:
                self.completed.emit(cover_data, "qqmusic", self._score)
            else:
                self.failed.emit(t("cover_download_failed"))
        except Exception as e:
            self._emit_error(e)


class QQMusicArtistCoverFetchThread(BaseWorkerThread):
    """Fetch QQ Music artist cover URL lazily, then download bytes."""

    completed = Signal(bytes, str, float)  # cover_data, source, score

    def __init__(self, singer_mid: str, score: float = 0, parent=None):
        super().__init__(parent)
        self._singer_mid = singer_mid
        self._score = score

    def run(self):
        try:
            from services.lyrics.qqmusic_lyrics import get_qqmusic_artist_cover_url
            from infrastructure.network import HttpClient

            if self._is_cancelled():
                return

            if not self._singer_mid:
                self.failed.emit(t("cover_load_failed"))
                return

            cover_url = get_qqmusic_artist_cover_url(self._singer_mid, size=500)

            if self._is_cancelled():
                return

            if not cover_url:
                self.failed.emit(t("cover_load_failed"))
                return

            http_client = HttpClient()
            cover_data = http_client.get_content(cover_url, timeout=10)

            if self._is_cancelled():
                return

            if cover_data:
                self.completed.emit(cover_data, "qqmusic", self._score)
            else:
                self.failed.emit(t("cover_download_failed"))
        except Exception as e:
            self._emit_error(e)