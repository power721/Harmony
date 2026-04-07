"""
Lyrics download dialog for searching and downloading lyrics from online sources.
"""
import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QCursor, QColor, QPainterPath, QRegion
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLabel,
    QCheckBox,
    QProgressBar,
    QWidget,
    QGraphicsDropShadowEffect,
)
from shiboken6.Shiboken import isValid

from services.lyrics.lyrics_service import LyricsService
from system.i18n import t
from system.theme import ThemeManager
from ui.dialogs.dialog_title_bar import setup_equalizer_title_layout
from utils.match_scorer import MatchScorer, TrackInfo, SearchResult

logger = logging.getLogger(__name__)

_ACTIVE_LYRICS_SEARCH_THREADS: set[QThread] = set()


class LyricsSearchThread(QThread):
    """Thread for searching lyrics with progressive updates."""

    search_completed = Signal(list)  # Emits list of search results
    search_failed = Signal(str)  # Emits error message
    search_progress = Signal(list, str)  # Emits (new_results, source_name) as each source completes

    def __init__(self, title: str, artist: str, limit: int = 10):
        super().__init__()
        self._title = title
        self._artist = artist
        self._limit = limit
        self._is_cancelled = False

    def cancel(self):
        """Cancel the search."""
        self._is_cancelled = True
        # Don't use terminate() - it's dangerous and can cause UI to freeze
        # The flag will be checked in the run() method

    def run(self):
        """Search for songs with progressive updates."""
        try:
            # Use progress callback for progressive updates
            def progress_callback(results, source_name):
                if not self._is_cancelled:
                    self.search_progress.emit(results, source_name)

            results = LyricsService.search_songs(
                self._title,
                self._artist,
                self._limit,
                progress_callback=progress_callback
            )

            if not self._is_cancelled:
                self.search_completed.emit(results)
        except Exception as e:
            if not self._is_cancelled:
                logger.error(f"Error searching lyrics: {e}", exc_info=True)
                self.search_failed.emit(f"{t('error')}: {str(e)}")


class LyricsDownloadDialog(QDialog):
    """Dialog for selecting and downloading lyrics from search results.

    This dialog displays search results from online lyrics sources and allows
    the user to select a song to download lyrics (and optionally cover art).
    Results are sorted by match score (highest first).
    """

    # Signals
    download_requested = Signal(dict, bool)  # Emits (song_info, download_cover)

    _STYLE_TEMPLATE = """
        QListWidget {
            background-color: %background%;
            color: %text%;
            border: 1px solid %border%;
            border-radius: 4px;
        }
        QListWidget::item {
            padding: 8px;
            border-bottom: 1px solid #303030;
        }
        QListWidget::item:selected {
            background-color: %highlight%;
            color: %background%;
        }
    """

    def __init__(
            self,
            track_title: str,
            track_artist: str,
            track_path: str = "",
            track_album: str = "",
            track_duration: float = None,
            parent=None
    ):
        """Initialize the lyrics download dialog.

        Args:
            track_title: The track title to search
            track_artist: The track artist to search
            track_path: Path to the audio file (for saving lyrics)
            track_album: Album name (for better matching)
            track_duration: Track duration in seconds (for better matching)
            parent: Parent widget
        """
        super().__init__(parent)
        self._track_title = track_title
        self._track_artist = track_artist
        self._track_path = track_path
        self._track_album = track_album
        self._track_duration = track_duration
        self._selected_song: Optional[dict] = None
        self._download_cover = False
        self._search_thread: Optional[LyricsSearchThread] = None
        self._drag_pos = None

        # Make dialog frameless
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setProperty("shell", True)

        self._setup_shadow()
        self._setup_ui()
        self._start_search()
        ThemeManager.instance().register_widget(self)

    def _setup_shadow(self):
        """Setup drop shadow effect."""
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

    def _setup_ui(self):
        """Setup the dialog UI."""
        self.setWindowTitle(t("select_song"))
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TEMPLATE))

        # Outer layout with 0 margins — container fills the dialog
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Container widget for rounded corners
        container = QWidget()
        container.setObjectName("dialogContainer")
        outer.addWidget(container)

        container_layout = QVBoxLayout(container)
        layout, self._title_bar_controller = setup_equalizer_title_layout(
            self,
            container_layout,
            t("select_song"),
        )

        # Info label
        self._info_label = QLabel(
            f"{t('search_results_for')}: {self._track_title} - {self._track_artist}"
        )
        layout.addWidget(self._info_label)

        # Progress bar for searching state
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)  # Indeterminate progress
        layout.addWidget(self._progress_bar)

        # Status label
        self._status_label = QLabel(t("searching"))
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet(f"color: {ThemeManager.instance().current_theme.text_secondary};")
        layout.addWidget(self._status_label)

        # Song list
        self._song_list = QListWidget()
        self._song_list.setFocusPolicy(Qt.NoFocus)  # Prevent automatic focus
        self._song_list.itemDoubleClicked.connect(self.accept)
        layout.addWidget(self._song_list)

        # Checkbox for downloading cover
        self._download_cover_checkbox = QCheckBox(t("download_cover"))
        self._download_cover_checkbox.setChecked(False)
        self._download_cover_checkbox.setToolTip(t("download_cover_tooltip"))
        layout.addWidget(self._download_cover_checkbox)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton(t("cancel"))
        cancel_btn.setProperty("role", "cancel")
        cancel_btn.setCursor(QCursor(Qt.PointingHandCursor))
        cancel_btn.clicked.connect(self._on_cancel_clicked)

        self._download_btn = QPushButton(t("download"))
        self._download_btn.setProperty("role", "primary")
        self._download_btn.setEnabled(False)  # Disabled until search completes and selection made
        self._download_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._download_btn.clicked.connect(self.accept)

        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(self._download_btn)
        layout.addLayout(button_layout)

    def _on_cancel_clicked(self):
        """Handle cancel button click."""
        self.reject()

    def _start_search(self):
        """Start the search thread with progressive updates."""
        LyricsDownloadDialog._stop_search_thread(self, wait_ms=100, cleanup_signals=True)

        thread = LyricsSearchThread(self._track_title, self._track_artist)
        self._search_thread = thread
        _ACTIVE_LYRICS_SEARCH_THREADS.add(thread)

        thread.search_completed.connect(self._on_search_completed)
        thread.search_failed.connect(self._on_search_failed)
        thread.search_progress.connect(self._on_search_progress)
        thread.finished.connect(self._on_search_thread_finished)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda thread=thread: _ACTIVE_LYRICS_SEARCH_THREADS.discard(thread))
        thread.start()

    @staticmethod
    def _disconnect_signal(signal, slot):
        """Disconnect a specific slot, ignoring already-disconnected signals."""
        if signal is None or slot is None:
            return
        try:
            signal.disconnect(slot)
        except (RuntimeError, TypeError):
            pass

    def _disconnect_search_thread_signals(self, thread: LyricsSearchThread):
        """Disconnect dialog-owned slots from a search thread."""
        on_search_completed = getattr(self, "_on_search_completed", None)
        on_search_failed = getattr(self, "_on_search_failed", None)
        on_search_progress = getattr(self, "_on_search_progress", None)
        on_search_thread_finished = getattr(self, "_on_search_thread_finished", None)

        LyricsDownloadDialog._disconnect_signal(
            getattr(thread, "search_completed", None),
            on_search_completed,
        )
        LyricsDownloadDialog._disconnect_signal(
            getattr(thread, "search_failed", None),
            on_search_failed,
        )
        LyricsDownloadDialog._disconnect_signal(
            getattr(thread, "search_progress", None),
            on_search_progress,
        )
        LyricsDownloadDialog._disconnect_signal(
            getattr(thread, "finished", None),
            on_search_thread_finished,
        )

    def _stop_search_thread(self, wait_ms: int = 1000, cleanup_signals: bool = False):
        """Stop the search thread and detach it from the dialog if needed."""
        thread = getattr(self, "_search_thread", None)
        if not thread or not isValid(thread):
            self._search_thread = None
            return

        if cleanup_signals:
            LyricsDownloadDialog._disconnect_search_thread_signals(self, thread)

        if thread.isRunning():
            thread.cancel()
            thread.requestInterruption()
            thread.quit()
            if not thread.wait(wait_ms):
                logger.warning(
                    "[LyricsDownloadDialog] Search thread still running after close request; "
                    "detaching cleanup from dialog lifecycle"
                )
                _ACTIVE_LYRICS_SEARCH_THREADS.add(thread)
                self._search_thread = None
                return

        _ACTIVE_LYRICS_SEARCH_THREADS.discard(thread)
        thread.deleteLater()
        self._search_thread = None

    def _on_search_progress(self, new_results: list, source_name: str):
        """Handle progressive search updates from each source."""
        # Update status to show which source completed
        self._status_label.setText(f"{t('searching')}... {source_name} ✓")

        # Calculate match scores and sort by score descending
        track_info = TrackInfo(
            title=self._track_title,
            artist=self._track_artist,
            album=self._track_album,
            duration=self._track_duration
        )

        scored_results = []
        for result in new_results:
            search_result = SearchResult(
                title=result.get('title', ''),
                artist=result.get('artist', ''),
                album=result.get('album', ''),
                duration=result.get('duration'),
                source=result.get('source', ''),
                id=result.get('id', ''),
                cover_url=result.get('cover_url'),
                lyrics=result.get('lyrics'),
                accesskey=result.get('accesskey')
            )
            score = MatchScorer.calculate_score(track_info, search_result, mode='lyrics')
            result['_score'] = score
            scored_results.append(result)

        # Define source priority (lower number = higher priority)
        source_priority = {
            'qqmusic': 0,  # QQ Music first
            'netease': 1,
            'kugou': 2,
            'lrclib': 3,
        }

        # Sort by score descending, then by source priority (QQ Music first for same score)
        scored_results.sort(key=lambda x: (
            -x.get('_score', 0),  # Negative for descending score
            source_priority.get(x.get('source', ''), 99)  # Lower priority number first
        ))

        # Add new results to the list (clear existing and rebuild to maintain sorting)
        # Get all existing items
        existing_results = []
        for i in range(self._song_list.count()):
            item = self._song_list.item(i)
            existing_results.append(item.data(Qt.UserRole))

        # Combine existing results with new results
        all_results = existing_results + scored_results

        # Remove duplicates (by source + id)
        seen = set()
        unique_results = []
        for result in all_results:
            key = (result.get('source', ''), result.get('id', ''))
            if key not in seen:
                seen.add(key)
                unique_results.append(result)

        # Sort all results by score, then by source priority
        unique_results.sort(key=lambda x: (
            -x.get('_score', 0),
            source_priority.get(x.get('source', ''), 99)
        ))

        # Clear and repopulate the list
        self._song_list.clear()
        for result in unique_results:
            item_text = self._format_result_text(result)
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, result)
            self._song_list.addItem(item)

        # Auto-select first result and enable download button
        if self._song_list.count() > 0 and self._song_list.currentRow() < 0:
            self._song_list.setCurrentRow(0)
            self._download_btn.setEnabled(True)

    def _on_search_completed(self, results: list):
        """Handle final search completion."""
        self._progress_bar.setVisible(False)
        self._status_label.setVisible(False)

        if not results and self._song_list.count() == 0:
            self._status_label.setVisible(True)
            self._status_label.setText(t("no_results"))
            return

    def _on_search_failed(self, error_message: str):
        """Handle search failure."""
        self._progress_bar.setVisible(False)
        self._status_label.setText(error_message)

    def _on_search_thread_finished(self):
        """Clear the dialog reference once the current search thread fully stops."""
        sender = self.sender()
        if sender and sender == self._search_thread:
            self._search_thread = None

    def _format_result_text(self, result: dict) -> str:
        """Format a search result for display in the list.

        Args:
            result: Search result dictionary

        Returns:
            Formatted display string
        """
        item_text = f"{result['title']} - {result['artist']}"

        # Only show album if it exists, is not empty, and is not "-"
        album = result.get('album', '')
        # Handle case where album might be a dict
        if isinstance(album, dict):
            album = album.get('name', '')
        if album and isinstance(album, str) and album.strip() and album.strip() != '-':
            item_text += f" ({album})"

        # Add duration for LRCLIB and NetEase results (if available)
        if result.get('duration') and result.get('duration') > 0:
            duration = result['duration']
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            item_text += f" [{minutes}:{seconds:02d}]"

        # Source name with YRC/QRC indicator
        source = result['source']
        if result.get('supports_yrc'):
            source = f"{source} YRC"  # Indicate YRC (word-by-word) support
        elif result.get('supports_qrc'):
            source = f"{source} QRC"  # Indicate QRC (word-by-word) support for QQ Music
        item_text += f" [{source}]"

        # Score at the end
        score = result.get('_score', 0)
        item_text += f" [{score:.0f}%]"

        return item_text

    def get_selected_song(self) -> Optional[dict]:
        """Get the selected song info.

        Returns:
            Selected song dictionary or None if no selection
        """
        return self._selected_song

    def get_download_cover(self) -> bool:
        """Get whether to download cover art.

        Returns:
            True if cover should be downloaded
        """
        return self._download_cover

    def accept(self):
        """Handle dialog acceptance."""
        current_item = self._song_list.currentItem()
        if current_item:
            self._selected_song = current_item.data(Qt.UserRole)
            self._download_cover = self._download_cover_checkbox.isChecked()
        LyricsDownloadDialog._stop_search_thread(self, wait_ms=100, cleanup_signals=True)
        super().accept()

    def reject(self):
        """Handle dialog rejection."""
        LyricsDownloadDialog._stop_search_thread(self, wait_ms=100, cleanup_signals=True)
        super().reject()

    def closeEvent(self, event):
        """Clean up on close."""
        LyricsDownloadDialog._stop_search_thread(self, wait_ms=100, cleanup_signals=True)
        super().closeEvent(event)

    @staticmethod
    def show_dialog(
            track_title: str,
            track_artist: str,
            track_path: str = "",
            track_album: str = "",
            track_duration: float = None,
            parent=None
    ) -> Optional[tuple]:
        """Static method to show the dialog and get the result.

        Args:
            track_title: The track title to search
            track_artist: The track artist to search
            track_path: Path to the audio file (for saving lyrics)
            track_album: Album name (for better matching)
            track_duration: Track duration in seconds (for better matching)
            parent: Parent widget

        Returns:
            Tuple of (selected_song, download_cover) or None if cancelled
        """
        dialog = LyricsDownloadDialog(
            track_title,
            track_artist,
            track_path,
            track_album,
            track_duration,
            parent
        )

        if dialog.exec() == QDialog.Accepted:
            selected_song = dialog.get_selected_song()
            download_cover = dialog.get_download_cover()
            if selected_song:
                return (selected_song, download_cover)

        return None

    def refresh_theme(self):
        """Refresh theme when changed."""
        self.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TEMPLATE))
        self._title_bar_controller.refresh_theme()
        if self._status_label:
            self._status_label.setStyleSheet(f"color: {ThemeManager.instance().current_theme.text_secondary};")

    def resizeEvent(self, event):
        """Apply rounded corner mask."""
        path = QPainterPath()
        path.addRoundedRect(self.rect(), 12, 12)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        """Handle mouse press for drag to move."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        """Handle mouse move for drag to move."""
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        """Handle mouse release."""
        self._drag_pos = None
