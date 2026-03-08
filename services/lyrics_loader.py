"""
Asynchronous lyrics loader to prevent UI blocking.
"""

import logging
from typing import Optional

from PySide6.QtCore import QThread, Signal

from .lyrics_service import LyricsService

# Configure logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(levelname)s] %(name)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)


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

        logger.debug(f"[LyricsLoader] Loading lyrics for: {self._title} - {self._artist}")

        # Check for interruption before starting
        if self.isInterruptionRequested():
            logger.debug("[LyricsLoader] Interruption requested, aborting")
            return

        self.loading_started.emit()

        try:
            lyrics = LyricsService.get_lyrics(self._path, self._title, self._artist)
            elapsed = time.time() - start_time
            logger.debug(f"[LyricsLoader] Lyrics loaded in {elapsed:.3f}s")

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
    """

    lyrics_downloaded = Signal(str, str)  # path, lyrics
    download_failed = Signal(str)  # error message

    def __init__(self, track_path: str, title: str, artist: str, parent=None):
        """
        Initialize the worker.

        Args:
            track_path: Path to the audio file
            title: Track title
            artist: Track artist
            parent: Optional parent QObject
        """
        super().__init__(parent)
        self._path = track_path
        self._title = title
        self._artist = artist

    def run(self):
        """Download lyrics in background."""
        try:
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
