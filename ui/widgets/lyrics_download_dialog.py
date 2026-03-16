"""
Lyrics download dialog for searching and downloading lyrics from online sources.
"""
import logging
from typing import Optional, List

from PySide6.QtCore import Qt, Signal, QThread
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
)

from services.lyrics.lyrics_service import LyricsService
from system.i18n import t
from utils.match_scorer import MatchScorer, TrackInfo, SearchResult

logger = logging.getLogger(__name__)


class LyricsSearchThread(QThread):
    """Thread for searching lyrics."""

    search_completed = Signal(list)  # Emits list of search results
    search_failed = Signal(str)  # Emits error message

    def __init__(self, title: str, artist: str, limit: int = 10):
        super().__init__()
        self._title = title
        self._artist = artist
        self._limit = limit

    def run(self):
        """Search for songs."""
        try:
            results = LyricsService.search_songs(self._title, self._artist, self._limit)
            self.search_completed.emit(results)
        except Exception as e:
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

        self._setup_ui()
        self._start_search()

    def _setup_ui(self):
        """Setup the dialog UI."""
        self.setWindowTitle(t("select_song"))
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self.setStyleSheet("""
            QDialog {
                background-color: #2a2a2a;
                color: #e0e0e0;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 13px;
            }
            QListWidget {
                background-color: #1a1a1a;
                color: #e0e0e0;
                border: 1px solid #404040;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #303030;
            }
            QListWidget::item:selected {
                background-color: #1db954;
                color: #000000;
            }
            QPushButton {
                background-color: #1db954;
                color: #000000;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1ed760;
            }
            QPushButton:disabled {
                background-color: #404040;
                color: #808080;
            }
            QPushButton[role="cancel"] {
                background-color: #404040;
                color: #e0e0e0;
            }
            QCheckBox {
                color: #e0e0e0;
                font-size: 13px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 3px;
                border: 2px solid #404040;
                background-color: #1a1a1a;
            }
            QCheckBox::indicator:checked {
                background-color: #1db954;
                border-color: #1db954;
            }
            QProgressBar {
                background-color: #3a3a3a;
                border: 1px solid #4a4a4a;
                border-radius: 4px;
                text-align: center;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #1db954;
                border-radius: 3px;
            }
        """)

        layout = QVBoxLayout(self)

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
        self._status_label.setStyleSheet("color: #a0a0a0;")
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
        cancel_btn = QPushButton(t("cancel"))
        cancel_btn.setProperty("role", "cancel")
        cancel_btn.clicked.connect(self.reject)

        self._download_btn = QPushButton(t("download"))
        self._download_btn.setEnabled(False)  # Disabled until search completes and selection made
        self._download_btn.clicked.connect(self.accept)

        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(self._download_btn)
        layout.addLayout(button_layout)

    def _start_search(self):
        """Start the search thread."""
        self._search_thread = LyricsSearchThread(self._track_title, self._track_artist)
        self._search_thread.search_completed.connect(self._on_search_completed)
        self._search_thread.search_failed.connect(self._on_search_failed)
        self._search_thread.finished.connect(self._search_thread.deleteLater)
        self._search_thread.start()

    def _on_search_completed(self, results: list):
        """Handle search completion."""
        self._progress_bar.setVisible(False)
        self._status_label.setVisible(False)

        if not results:
            self._status_label.setVisible(True)
            self._status_label.setText(t("no_results"))
            return

        # Calculate match scores and sort by score descending
        track_info = TrackInfo(
            title=self._track_title,
            artist=self._track_artist,
            album=self._track_album,
            duration=self._track_duration
        )

        scored_results = []
        for result in results:
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

        # Sort by score descending (highest first)
        scored_results.sort(key=lambda x: x.get('_score', 0), reverse=True)

        # Populate song list
        for result in scored_results:
            item_text = self._format_result_text(result)
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, result)
            self._song_list.addItem(item)

        # Auto-select first result
        if self._song_list.count() > 0:
            self._song_list.setCurrentRow(0)
            self._download_btn.setEnabled(True)

    def _on_search_failed(self, error_message: str):
        """Handle search failure."""
        self._progress_bar.setVisible(False)
        self._status_label.setText(error_message)

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
        if album and album.strip() and album.strip() != '-':
            item_text += f" ({album})"

        # Add duration for LRCLIB and NetEase results (if available)
        if result.get('duration') and result.get('duration') > 0:
            duration = result['duration']
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            item_text += f" [{minutes}:{seconds:02d}]"

        # Source name with YRC indicator
        source = result['source']
        if result.get('supports_yrc'):
            source = f"{source} YRC"  # Indicate YRC (word-by-word) support
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
        super().accept()

    def closeEvent(self, event):
        """Clean up on close."""
        if self._search_thread and self._search_thread.isRunning():
            self._search_thread.terminate()
            self._search_thread.wait()
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

        if dialog.exec_() == QDialog.Accepted:
            selected_song = dialog.get_selected_song()
            download_cover = dialog.get_download_cover()
            if selected_song:
                return (selected_song, download_cover)

        return None
