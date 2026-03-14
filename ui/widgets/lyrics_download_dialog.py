"""
Lyrics download dialog for searching and downloading lyrics from online sources.
"""
import logging
from typing import Optional, Callable

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLabel,
    QCheckBox,
)
from PySide6.QtCore import Qt, Signal

from system.i18n import t

logger = logging.getLogger(__name__)


class LyricsDownloadDialog(QDialog):
    """Dialog for selecting and downloading lyrics from search results.

    This dialog displays search results from online lyrics sources and allows
    the user to select a song to download lyrics (and optionally cover art).
    """

    # Signals
    download_requested = Signal(dict, bool)  # Emits (song_info, download_cover)

    def __init__(
        self,
        results: list,
        track_title: str,
        track_artist: str,
        parent=None
    ):
        """Initialize the lyrics download dialog.

        Args:
            results: List of search result dictionaries with keys:
                     - id: Song ID
                     - title: Song title
                     - artist: Artist name
                     - album: Album name (optional)
                     - source: Source name (e.g., 'NetEase', 'LRCLIB')
                     - duration: Duration in seconds (optional)
                     - accesskey: Access key for some sources (optional)
            track_title: The track title that was searched
            track_artist: The track artist that was searched
            parent: Parent widget
        """
        super().__init__(parent)
        self._results = results
        self._track_title = track_title
        self._track_artist = track_artist
        self._selected_song: Optional[dict] = None
        self._download_cover = False

        self._setup_ui()

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
        """)

        layout = QVBoxLayout(self)

        # Info label
        info_label = QLabel(
            f"{t('search_results_for')}: {self._track_title} - {self._track_artist}"
        )
        layout.addWidget(info_label)

        # Song list
        self._song_list = QListWidget()
        for result in self._results:
            item_text = self._format_result_text(result)
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, result)
            self._song_list.addItem(item)

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
        download_btn = QPushButton(t("download"))
        download_btn.clicked.connect(self.accept)
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(download_btn)
        layout.addLayout(button_layout)

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

        item_text += f" [{result['source']}]"

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

    @staticmethod
    def show_dialog(
        results: list,
        track_title: str,
        track_artist: str,
        parent=None
    ) -> Optional[tuple]:
        """Static method to show the dialog and get the result.

        Args:
            results: List of search results
            track_title: The track title that was searched
            track_artist: The track artist that was searched
            parent: Parent widget

        Returns:
            Tuple of (selected_song, download_cover) or None if cancelled
        """
        if not results:
            return None

        dialog = LyricsDownloadDialog(
            results,
            track_title,
            track_artist,
            parent
        )

        if dialog.exec_() == QDialog.Accepted:
            selected_song = dialog.get_selected_song()
            download_cover = dialog.get_download_cover()
            if selected_song:
                return (selected_song, download_cover)

        return None
