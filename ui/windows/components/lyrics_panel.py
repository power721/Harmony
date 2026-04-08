"""
Lyrics panel and controller for MainWindow.
"""

import logging
from typing import Optional, TYPE_CHECKING

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QMenu,
)
from shiboken6 import isValid

from services.lyrics import LyricsLoader
from services.lyrics.lyrics_loader import LyricsDownloadWorker
from system.i18n import t
from ui.dialogs.message_dialog import MessageDialog, Yes, No
from ui.widgets.lyrics_widget_pro import LyricsWidget

if TYPE_CHECKING:
    from services.playback import PlaybackService
    from services.library import LibraryService

logger = logging.getLogger(__name__)


class LyricsPanel(QWidget):
    """
    Lyrics display panel with download and edit capabilities.

    Signals:
        download_requested: Emitted when user wants to download lyrics
        edit_requested: Emitted when user wants to edit lyrics
        delete_requested: Emitted when user wants to delete lyrics
        refresh_requested: Emitted when user wants to refresh lyrics
        open_location_requested: Emitted when user wants to open lyrics file location
        seek_requested: Emitted when user clicks on a timestamp (position_ms)
    """

    download_requested = Signal()
    edit_requested = Signal()
    delete_requested = Signal()
    refresh_requested = Signal()
    open_location_requested = Signal()
    seek_requested = Signal(int)  # position in ms

    _MENU_STYLE = """
        QMenu {
            background-color: %background_alt%;
            color: %text%;
            border: 1px solid %border%;
        }
        QMenu::item {
            padding: 8px 20px;
        }
        QMenu::item:selected {
            background-color: %highlight%;
            color: %background%;
        }
    """

    def __init__(self, parent=None):
        """Initialize the lyrics panel."""
        super().__init__(parent)
        self._setup_ui()

        # Register with theme manager
        from system.theme import ThemeManager
        ThemeManager.instance().register_widget(self)

    def _setup_ui(self):
        """Setup the UI."""
        self.setObjectName("lyricsPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 20, 15, 20)

        # Title with download button
        title_layout = QHBoxLayout()

        self._title_label = QLabel(t("lyrics"))
        self._title_label.setObjectName("lyricsTitle")
        self._title_label.setAlignment(Qt.AlignLeft)
        title_layout.addWidget(self._title_label)

        title_layout.addStretch()

        # Download button
        self._download_btn = QPushButton(t("download"))
        self._download_btn.setObjectName("downloadLyricsBtn")
        self._download_btn.setFixedHeight(28)
        self._download_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._download_btn.clicked.connect(self.download_requested)
        title_layout.addWidget(self._download_btn)

        layout.addLayout(title_layout)

        # Lyrics widget
        self._lyrics_view = LyricsWidget()
        self._lyrics_view.setObjectName("lyricsContent")
        self._lyrics_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self._lyrics_view.customContextMenuRequested.connect(self._show_context_menu)
        self._lyrics_view.setFocusPolicy(Qt.NoFocus)
        self._lyrics_view.seekRequested.connect(self.seek_requested)

        layout.addWidget(self._lyrics_view, 1)

    def _show_context_menu(self, pos):
        """Show context menu for lyrics."""
        from system.theme import ThemeManager

        menu = QMenu(self)
        menu.setStyleSheet(ThemeManager.instance().get_qss(self._MENU_STYLE))

        download_action = menu.addAction(t("download_lyrics"))
        download_action.triggered.connect(self.download_requested)

        edit_action = menu.addAction(t("edit_lyrics"))
        edit_action.triggered.connect(self.edit_requested)

        delete_action = menu.addAction(t("delete_lyrics"))
        delete_action.triggered.connect(self.delete_requested)

        menu.addSeparator()

        open_location_action = menu.addAction(t("open_file_location"))
        open_location_action.triggered.connect(self.open_location_requested)

        refresh_action = menu.addAction(t("refresh"))
        refresh_action.triggered.connect(self.refresh_requested)

        menu.exec(self._lyrics_view.mapToGlobal(pos))

    def set_lyrics(self, lyrics: str):
        """Set the lyrics content."""
        self._lyrics_view.set_lyrics(lyrics)

    def set_no_lyrics(self):
        """Show no lyrics message."""
        self._lyrics_view.set_lyrics(t("no_lyrics"))

    def update_position(self, seconds: float):
        """Update the current playback position for lyrics highlighting.

        Args:
            seconds: Current playback position in seconds
        """
        self._lyrics_view.update_position(seconds)

    def refresh_texts(self):
        """Refresh UI texts with current language."""
        self._title_label.setText(t("lyrics"))
        self._download_btn.setText(t("download"))

    def refresh_theme(self):
        """Refresh theme colors when theme changes."""
        # Context menu is created on-demand, no need to update here
        pass


class LyricsController(QObject):
    """
    Controller for lyrics loading, downloading, and editing.

    This class handles all lyrics-related operations including:
    - Async lyrics loading with version control
    - Lyrics download from online sources
    - Lyrics editing and saving
    """

    # Signals for UI updates
    lyrics_loaded = Signal(str)
    lyrics_load_failed = Signal()

    def __init__(
            self,
            lyrics_panel: LyricsPanel,
            playback_service: "PlaybackService",
            library_service: "LibraryService" = None,
            parent=None
    ):
        """
        Initialize the lyrics controller.

        Args:
            lyrics_panel: LyricsPanel widget to control
            playback_service: Playback service for current track info
            library_service: Library service for track updates
            parent: Parent QObject
        """
        super().__init__(parent)

        self._panel = lyrics_panel
        self._playback = playback_service
        self._library_service = library_service

        # Thread management
        self._lyrics_thread: Optional[LyricsLoader] = None
        self._lyrics_download_thread: Optional[LyricsDownloadWorker] = None
        self._lyrics_load_version = 0

        # Store download info for lyric persistence
        self._lyrics_download_path: Optional[str] = None
        self._lyrics_download_title: Optional[str] = None
        self._lyrics_download_artist: Optional[str] = None

        # Connect panel signals
        self._panel.download_requested.connect(self.download_lyrics)
        self._panel.edit_requested.connect(self.edit_lyrics)
        self._panel.delete_requested.connect(self.delete_lyrics)
        self._panel.refresh_requested.connect(self.refresh_lyrics)
        self._panel.open_location_requested.connect(self.open_lyrics_file_location)
        self._panel.seek_requested.connect(self._playback.seek)

    def load_lyrics_async(
            self,
            path: str,
            title: str,
            artist: str,
            song_mid: str = None,
            is_online: bool = False,
            provider_id: str | None = None,
    ):
        """
        Load lyrics asynchronously with version control.

        Args:
            path: Path to the audio file
            title: Track title
            artist: Track artist
            song_mid: Provider-side song id (for online tracks)
            is_online: Whether this is an online track
            provider_id: Online provider id
        """
        # Increment version to invalidate pending results
        self._lyrics_load_version += 1
        current_version = self._lyrics_load_version

        # Clean up old thread
        self._stop_lyrics_loader_thread(wait_ms=500, cleanup_signals=True)

        # Create new loader
        self._lyrics_thread = LyricsLoader(
            path,
            title,
            artist,
            song_mid=song_mid,
            is_online=is_online,
            provider_id=provider_id,
        )
        self._lyrics_thread._load_version = current_version

        self._lyrics_thread.lyrics_ready.connect(
            lambda lyrics: self._on_lyrics_ready(lyrics, current_version)
        )
        self._lyrics_thread.finished.connect(self._on_lyrics_thread_finished)
        self._lyrics_thread.start()

    def _on_lyrics_ready(self, lyrics: str, version: int):
        """Handle lyrics loaded from thread."""
        if version != self._lyrics_load_version:
            return  # Stale result

        if lyrics:
            self._panel.set_lyrics(lyrics)
            self.lyrics_loaded.emit(lyrics)
        else:
            self._panel.set_no_lyrics()
            self.lyrics_load_failed.emit()

    def _on_lyrics_thread_finished(self):
        """Handle lyrics thread finished."""
        sender = self.sender()
        if sender:
            sender.deleteLater()
            if sender == self._lyrics_thread:
                self._lyrics_thread = None

    def download_lyrics(self):
        """Download lyrics for current track."""
        from ui.dialogs.lyrics_download_dialog import LyricsDownloadDialog

        current_item = self._playback.current_track
        if not current_item:
            return

        track_path = current_item.local_path
        track_title = current_item.title
        track_artist = current_item.artist
        track_album = current_item.album
        track_duration = current_item.duration

        if not track_path:
            MessageDialog.warning(
                None, t("error"), t("cloud_lyrics_download_not_supported")
            )
            return

        # Store info for later
        self._lyrics_download_path = track_path
        self._lyrics_download_title = track_title
        self._lyrics_download_artist = track_artist

        result = LyricsDownloadDialog.show_dialog(
            track_title, track_artist, track_path,
            track_album, track_duration, None
        )

        if result:
            self._download_lyrics_for_song(result)

    def _download_lyrics_for_song(self, song_info: dict):
        """Download lyrics for a specific song."""
        self._stop_lyrics_download_thread(wait_ms=500, cleanup_signals=True)

        self._lyrics_download_thread = LyricsDownloadWorker(
            self._lyrics_download_path,
            self._lyrics_download_title,
            self._lyrics_download_artist,
            song_id=song_info['id'],
            source=song_info['source'],
            accesskey=song_info.get('accesskey'),
            lyrics_data=song_info.get('lyrics')
        )

        self._lyrics_download_thread.lyrics_downloaded.connect(self._on_lyrics_downloaded)
        self._lyrics_download_thread.download_failed.connect(self._on_lyrics_download_failed)

        self._lyrics_download_thread.finished.connect(
            self._lyrics_download_thread.deleteLater
        )
        self._lyrics_download_thread.start()

    def _on_lyrics_downloaded(self, path: str, lyrics: str):
        """Handle lyrics download success."""
        self._panel.set_lyrics(lyrics)

    def _on_lyrics_download_failed(self, error: str):
        """Handle lyrics download failure."""
        self._panel.set_no_lyrics()

    def edit_lyrics(self):
        """Edit lyrics for current track."""
        from ui.dialogs.lyrics_edit_dialog import LyricsEditDialog

        current_track = self._playback.engine.current_track
        if not current_track:
            MessageDialog.information(None, t("info"), t("no_track_playing"))
            return

        is_cloud_file = not current_track.get("id")

        if is_cloud_file:
            track_path = current_track.get("path", "")
            track_title = current_track.get("title", "Unknown")
            track_artist = current_track.get("artist", "Unknown")

            if not track_path:
                MessageDialog.warning(
                    None, t("error"), t("cloud_lyrics_edit_not_supported")
                )
                return
        else:
            if not self._playback.current_track_id or not self._library_service:
                return

            track = self._library_service.get_track(self._playback.current_track_id)
            if not track:
                return

            track_path = track.path
            track_title = track.title
            track_artist = track.artist

        # Show edit dialog
        result = LyricsEditDialog.show_dialog(
            track_path, track_title, track_artist, None
        )

        if result is not None:
            if result.strip():
                self._panel.set_lyrics(result)
            else:
                self._panel.set_no_lyrics()

    def delete_lyrics(self):
        """Delete lyrics for current track."""
        from services import LyricsService

        current_track = self._playback.engine.current_track
        if not current_track:
            return

        track_path = current_track.get("path", "")
        if not track_path:
            return

        reply = MessageDialog.question(
            None,
            t("delete_lyrics"),
            t("confirm_delete_lyrics"),
            Yes | No,
            No
        )

        if reply == Yes:
            LyricsService.delete_lyrics(track_path)
            self._panel.set_no_lyrics()

    def open_lyrics_file_location(self):
        """Open lyrics file location in file manager."""
        import subprocess
        import sys

        current_track = self._playback.engine.current_track
        if not current_track:
            return

        track_path = current_track.get("path", "")
        source = current_track.get("source", "Local")

        # Check if this is a cloud/network track
        is_cloud_track = source in ("ONLINE", "QUARK", "BAIDU")

        if not track_path:
            if is_cloud_track:
                MessageDialog.information(
                    None, t("info"), t("cloud_track_no_local_file")
                )
            else:
                MessageDialog.information(
                    None, t("info"), t("lyrics_file_not_found")
                )
            return

        from pathlib import Path
        lyrics_path = Path(track_path).with_suffix('.lrc')

        # Also check for .yrc and .qrc formats
        if not lyrics_path.exists():
            lyrics_path = Path(track_path).with_suffix('.yrc')
        if not lyrics_path.exists():
            lyrics_path = Path(track_path).with_suffix('.qrc')

        if lyrics_path.exists():
            if sys.platform == "win32":
                subprocess.run(["explorer", "/select,", str(lyrics_path)])
            elif sys.platform == "darwin":
                subprocess.run(["open", "-R", str(lyrics_path)])
            else:
                subprocess.run(["xdg-open", str(lyrics_path.parent)])
        else:
            if is_cloud_track:
                MessageDialog.information(
                    None, t("info"), t("cloud_lyrics_file_not_found")
                )
            else:
                MessageDialog.information(
                    None, t("info"), t("lyrics_file_not_found")
                )

    def refresh_lyrics(self):
        """Refresh lyrics for current track."""
        current_track = self._playback.engine.current_track
        if current_track:
            track_path = current_track.get("path", "")
            track_title = current_track.get("title", "")
            track_artist = current_track.get("artist", "")

            if track_path:
                self.load_lyrics_async(track_path, track_title, track_artist)

    def on_track_changed(self, track_item):
        """Handle track change event."""
        from domain.playlist_item import PlaylistItem
        from domain.track import TrackSource

        if isinstance(track_item, PlaylistItem):
            path = track_item.local_path
            title = track_item.title
            artist = track_item.artist
            song_mid = track_item.cloud_file_id
            is_online = track_item.is_online
            provider_id = track_item.online_provider_id

            if path:
                self.load_lyrics_async(path, title, artist, song_mid, is_online, provider_id)
            else:
                self._panel.set_no_lyrics()
        elif isinstance(track_item, dict):
            path = track_item.get("path", "")
            title = track_item.get("title", "")
            artist = track_item.get("artist", "")

            if path:
                self.load_lyrics_async(path, title, artist)
            else:
                self._panel.set_no_lyrics()

    def cleanup(self):
        """Clean up worker threads before destruction."""
        self._stop_lyrics_loader_thread(wait_ms=1000, cleanup_signals=True)
        self._stop_lyrics_download_thread(wait_ms=1000, cleanup_signals=True)

    def _stop_lyrics_loader_thread(self, wait_ms: int = 1000, cleanup_signals: bool = False):
        """Stop lyrics loader thread cooperatively."""
        thread = getattr(self, "_lyrics_thread", None)
        if not thread or not isValid(thread):
            self._lyrics_thread = None
            return

        if thread.isRunning():
            logger.debug("[LyricsController] Stopping lyrics thread")
            thread.requestInterruption()
            thread.quit()
            if not thread.wait(wait_ms):
                logger.warning("[LyricsController] Lyrics thread did not stop in time")

        if cleanup_signals:
            try:
                thread.finished.disconnect()
                thread.lyrics_ready.disconnect()
            except RuntimeError:
                pass
            thread.deleteLater()
            self._lyrics_thread = None

    def _stop_lyrics_download_thread(self, wait_ms: int = 1000, cleanup_signals: bool = False):
        """Stop lyrics download thread cooperatively."""
        thread = getattr(self, "_lyrics_download_thread", None)
        if not thread or not isValid(thread):
            self._lyrics_download_thread = None
            return

        if thread.isRunning():
            logger.debug("[LyricsController] Stopping lyrics download thread")
            if hasattr(thread, "requestInterruption"):
                thread.requestInterruption()
            thread.quit()
            if not thread.wait(wait_ms):
                logger.warning("[LyricsController] Lyrics download thread did not stop in time")

        if cleanup_signals:
            try:
                thread.finished.disconnect()
                thread.lyrics_downloaded.disconnect()
                thread.download_failed.disconnect()
            except RuntimeError:
                pass
            thread.deleteLater()
            self._lyrics_download_thread = None
