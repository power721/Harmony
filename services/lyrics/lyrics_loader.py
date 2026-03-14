"""
Asynchronous lyrics loader to prevent UI blocking.
"""

import logging

from PySide6.QtCore import QThread, Signal

from .lyrics_service import LyricsService

# Configure logging
logger = logging.getLogger(__name__)


class LyricsLoader(QThread):
    """
    Asynchronous lyrics loader.

    Loads lyrics in a background thread to prevent UI blocking.
    Supports both local .lrc files and online sources.

    Signals:
        lyrics_ready: Emitted when lyrics are loaded (str)
        error_occurred: Emitted when an error occurs (str)
        loading_started: Emitted when loading starts
    """

    lyrics_ready = Signal(str)
    error_occurred = Signal(str)
    loading_started = Signal()

    def __init__(self, path: str, title: str, artist: str, parent=None):
        """
        Initialize the lyrics loader.

        Args:
            path: Path to the audio file
            title: Track title
            artist: Track artist
            parent: Optional parent QObject
        """
        super().__init__(parent)
        self._path = path
        self._title = title
        self._artist = artist

    def run(self):
        """Load lyrics in background thread."""
        import time
        start_time = time.time()

        
        # Check for interruption before starting
        if self.isInterruptionRequested():
            logger.debug("[LyricsLoader] Interruption requested, aborting")
            return

        self.loading_started.emit()

        try:
            lyrics = LyricsService.get_lyrics(self._path, self._title, self._artist)
            elapsed = time.time() - start_time
            
            # Check for interruption before emitting
            if self.isInterruptionRequested():
                logger.debug("[LyricsLoader] Interruption requested, not emitting result")
                return

            if lyrics:
                self.lyrics_ready.emit(lyrics)
            else:
                self.lyrics_ready.emit("")  # No lyrics found

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[LyricsLoader] Error loading lyrics: {e}")
            if not self.isInterruptionRequested():
                self.error_occurred.emit(str(e))


class LyricsDownloadWorker(QThread):
    """
    Worker for downloading lyrics from online sources.

    Signals:
        lyrics_downloaded: Emitted when lyrics are downloaded and saved (path, lyrics)
        download_failed: Emitted when download fails (error_message)
        search_results_ready: Emitted when search results are ready (list of dicts)
        cover_downloaded: Emitted when cover is downloaded (cover_path)
    """

    lyrics_downloaded = Signal(str, str)  # path, lyrics
    download_failed = Signal(str)  # error message
    search_results_ready = Signal(list)  # list of search results
    cover_downloaded = Signal(str)  # cover path

    def __init__(self, track_path: str, title: str, artist: str, parent=None,
                 song_id: str = None, source: str = None, accesskey: str = None,
                 download_cover: bool = True, cover_service: 'CoverService' = None):
        """
        Initialize the worker.

        Args:
            track_path: Path to the audio file
            title: Track title
            artist: Track artist
            parent: Optional parent QObject
            song_id: If provided, download specific song's lyrics
            source: Source name ('netease' or 'kugou')
            accesskey: Access key for Kugou
            download_cover: Whether to download cover art (default: True)
        """
        super().__init__(parent)
        self._path = track_path
        self._title = title
        self._artist = artist
        self._song_id = song_id
        self._source = source
        self._accesskey = accesskey
        self._should_download_cover = download_cover
        self._cover_service = cover_service

    def run(self):
        """Download lyrics in background."""
        try:
            if self._song_id and self._source:
                # Download specific song's lyrics
                lyrics = LyricsService.download_lyrics_by_id(
                    self._song_id, self._source, self._accesskey
                )
                if lyrics:
                    # Save to local file
                    LyricsService.save_lyrics(self._path, lyrics)
                    self.lyrics_downloaded.emit(self._path, lyrics)

                    # Try to download cover for NetEase songs if enabled
                    if self._should_download_cover and self._source == 'netease':
                        self._download_cover(self._song_id, self._source)
                else:
                    self.download_failed.emit("Failed to download lyrics for selected song")
            else:
                # Auto download (first result)
                success = LyricsService.download_and_save_lyrics(
                    self._path, self._title, self._artist
                )
                if success:
                    # Read the saved lyrics
                    lyrics = LyricsService._get_local_lyrics(self._path)
                    if lyrics:
                        self.lyrics_downloaded.emit(self._path, lyrics)
                    else:
                        self.download_failed.emit("Failed to read saved lyrics")
                else:
                    self.download_failed.emit("No lyrics found online")
        except Exception as e:
            logger.error(f"[LyricsDownloadWorker] Error: {e}")
            self.download_failed.emit(str(e))

    def _download_cover(self, song_id: str, source: str):
        """Download cover art for the song."""
        try:
            # Get cover URL
            cover_url = LyricsService.get_song_cover_url(song_id, source)
            if not cover_url:
                                return

            # Download cover image
            import requests
            from pathlib import Path

            response = requests.get(cover_url, headers=LyricsService.HEADERS, timeout=10)
            if response.status_code != 200:
                                return

            cover_data = response.content
            if not cover_data:
                return

            # Save cover to cache directory
            if self._cover_service:
                cover_path = self._cover_service.save_cover_data_to_cache(
                    cover_data, self._artist, self._title
                )
                if cover_path:
                    self.cover_downloaded.emit(cover_path)

        except Exception as e:
            logger.error(f"[LyricsDownloadWorker] Error downloading cover: {e}", exc_info=True)


class LyricsSearchWorker(QThread):
    """
    Worker for searching songs online.

    Signals:
        search_results_ready: Emitted when search results are ready (list of dicts)
        search_failed: Emitted when search fails (error_message)
    """

    search_results_ready = Signal(list)  # list of search results
    search_failed = Signal(str)  # error message

    def __init__(self, title: str, artist: str, limit: int = 10, parent=None):
        """
        Initialize the worker.

        Args:
            title: Track title
            artist: Track artist
            limit: Maximum number of results
            parent: Optional parent QObject
        """
        super().__init__(parent)
        self._title = title
        self._artist = artist
        self._limit = limit

    def run(self):
        """Search songs in background."""
        try:
            results = LyricsService.search_songs(self._title, self._artist, self._limit)
            if results:
                self.search_results_ready.emit(results)
            else:
                self.search_failed.emit("No songs found")
        except Exception as e:
            logger.error(f"[LyricsSearchWorker] Error: {e}")
            self.search_failed.emit(str(e))
