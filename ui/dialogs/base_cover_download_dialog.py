"""
Base class for cover download dialogs.
"""
import logging
from abc import abstractmethod
from typing import List

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QImage, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QScrollArea, QWidget,
    QListWidget, QListWidgetItem, QSplitter
)

from services.metadata import CoverService
from system.i18n import t

logger = logging.getLogger(__name__)


# ============================================================================
# Thread Classes (Shared by all dialogs)
# ============================================================================

class CoverDownloadThread(QThread):
    """Thread for downloading cover art."""
    cover_downloaded = Signal(bytes, str)  # Emits cover data and source
    download_failed = Signal(str)  # Emits error message
    finished = Signal()

    def __init__(self, cover_service: CoverService, cover_url: str, source: str = ""):
        super().__init__()
        self.cover_service = cover_service
        self.cover_url = cover_url
        self.source = source

    def run(self):
        """Download cover from URL."""
        try:
            from infrastructure.network import HttpClient
            http_client = HttpClient()
            cover_data = http_client.get_content(self.cover_url, timeout=10)

            if cover_data:
                self.cover_downloaded.emit(cover_data, self.source)
            else:
                self.download_failed.emit(t("cover_download_failed"))
        except Exception as e:
            logger.error(f"Error downloading cover: {e}", exc_info=True)
            self.download_failed.emit(f"{t('error')}: {str(e)}")
        finally:
            self.finished.emit()


class QQMusicCoverFetchThread(QThread):
    """Thread for fetching QQ Music cover URL and downloading."""
    cover_fetched = Signal(bytes, str, float)  # Emits cover data, source, and score
    fetch_failed = Signal(str)  # Emits error message
    finished = Signal()

    def __init__(self, album_mid: str = None, song_mid: str = None, score: float = 0):
        super().__init__()
        self.album_mid = album_mid
        self.song_mid = song_mid
        self.score = score

    def run(self):
        """Fetch QQ Music cover URL and download."""
        try:
            from services.lyrics.qqmusic_lyrics import get_qqmusic_cover_url
            from infrastructure.network import HttpClient

            logger.info(f"QQMusicCoverFetchThread: album_mid={self.album_mid}, song_mid={self.song_mid}")

            # Check if we have any ID to fetch
            if not self.album_mid and not self.song_mid:
                logger.warning("QQMusicCoverFetchThread: No album_mid or song_mid provided")
                self.fetch_failed.emit(t("cover_load_failed"))
                return

            # Get cover URL
            cover_url = None
            if self.album_mid:
                logger.info(f"Fetching cover URL with album_mid={self.album_mid}")
                cover_url = get_qqmusic_cover_url(album_mid=self.album_mid, size=500)
                logger.info(f"Got cover_url={cover_url}")
            elif self.song_mid:
                logger.info(f"Fetching cover URL with song_mid={self.song_mid}")
                cover_url = get_qqmusic_cover_url(mid=self.song_mid, size=500)
                logger.info(f"Got cover_url={cover_url}")

            if cover_url:
                # Download cover data
                logger.info(f"Downloading cover from {cover_url}")
                http_client = HttpClient()
                cover_data = http_client.get_content(cover_url, timeout=10)
                if cover_data:
                    logger.info(f"Downloaded cover data: {len(cover_data)} bytes")
                    self.cover_fetched.emit(cover_data, 'qqmusic', self.score)
                else:
                    logger.warning("Failed to download cover data")
                    self.fetch_failed.emit(t("cover_download_failed"))
            else:
                logger.warning("No cover URL obtained")
                self.fetch_failed.emit(t("cover_load_failed"))
        except Exception as e:
            logger.warning(f"Error fetching QQ Music cover: {e}")
            logger.error(f"Error fetching QQ Music cover: {e}", exc_info=True)
            self.fetch_failed.emit(f"{t('error')}: {str(e)}")
        finally:
            self.finished.emit()


class QQMusicArtistCoverFetchThread(QThread):
    """Thread for fetching QQ Music artist cover URL and downloading."""
    cover_fetched = Signal(bytes, str, float)  # Emits cover data, source, and score
    fetch_failed = Signal(str)  # Emits error message
    finished = Signal()

    def __init__(self, singer_mid: str, score: float = 0):
        super().__init__()
        self.singer_mid = singer_mid
        self.score = score

    def run(self):
        """Fetch QQ Music artist cover URL and download."""
        try:
            from services.lyrics.qqmusic_lyrics import get_qqmusic_artist_cover_url
            from infrastructure.network import HttpClient

            logger.info(f"QQMusicArtistCoverFetchThread: singer_mid={self.singer_mid}")

            if not self.singer_mid:
                logger.warning("QQMusicArtistCoverFetchThread: No singer_mid provided")
                self.fetch_failed.emit(t("cover_load_failed"))
                return

            # Get artist cover URL (direct construction)
            cover_url = get_qqmusic_artist_cover_url(self.singer_mid, size=500)
            logger.info(f"Artist cover URL: {cover_url}")

            if cover_url:
                # Download cover data
                http_client = HttpClient()
                cover_data = http_client.get_content(cover_url, timeout=10)
                if cover_data:
                    logger.info(f"Downloaded artist cover data: {len(cover_data)} bytes")
                    self.cover_fetched.emit(cover_data, 'qqmusic', self.score)
                else:
                    logger.warning("Failed to download artist cover data")
                    self.fetch_failed.emit(t("cover_download_failed"))
            else:
                logger.warning("No artist cover URL obtained")
                self.fetch_failed.emit(t("cover_load_failed"))
        except Exception as e:
            logger.warning(f"Error fetching QQ Music artist cover: {e}")
            logger.error(f"Error fetching QQ Music artist cover: {e}", exc_info=True)
            self.fetch_failed.emit(f"{t('error')}: {str(e)}")
        finally:
            self.finished.emit()


# ============================================================================
# Base Dialog Class
# ============================================================================

class BaseCoverDownloadDialog(QDialog):
    """Base class for cover download dialogs."""

    cover_saved = Signal(str)  # Emits cover path

    # Common stylesheet for all dialogs
    DARK_STYLE = """
        QDialog {
            background-color: #282828;
            color: #ffffff;
        }
        QLabel {
            color: #ffffff;
        }
        QPushButton {
            background-color: #3a3a3a;
            color: #ffffff;
            border: 1px solid #4a4a4a;
            border-radius: 4px;
            padding: 8px 16px;
            min-width: 80px;
        }
        QPushButton:hover {
            background-color: #4a4a4a;
        }
        QPushButton:pressed {
            background-color: #2a2a2a;
        }
        QPushButton:disabled {
            background-color: #2a2a2a;
            color: #606060;
            border-color: #3a3a3a;
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
        QListWidget {
            background-color: #2a2a2a;
            color: #ffffff;
            border: 1px solid #4a4a4a;
            border-radius: 4px;
        }
        QListWidget::item {
            padding: 8px;
            border-bottom: 1px solid #3a3a3a;
        }
        QListWidget::item:hover {
            background-color: #3a3a3a;
        }
        QListWidget::item:selected {
            background-color: #1db954;
            color: #ffffff;
        }
    """

    def __init__(self, cover_service: CoverService, parent=None):
        super().__init__(parent)
        self._cover_service = cover_service
        self._search_thread = None
        self._download_thread = None
        self._current_cover_data = None
        self._current_cover_url = None
        self._search_results = []

    # ========================================================================
    # Properties
    # ========================================================================

    @property
    def cover_service(self) -> CoverService:
        return self._cover_service

    @property
    def current_cover_data(self) -> bytes:
        return self._current_cover_data

    @current_cover_data.setter
    def current_cover_data(self, value: bytes):
        self._current_cover_data = value

    @property
    def search_results(self) -> list:
        return self._search_results

    @search_results.setter
    def search_results(self, value: list):
        self._search_results = value

    # ========================================================================
    # UI Setup Methods
    # ========================================================================

    def _setup_common_ui(self, info_text: str, cover_size: int = 350, circular: bool = False):
        """Setup common UI components.

        Args:
            info_text: Text to display at the top (e.g., track/album/artist name)
            cover_size: Size of the cover preview
            circular: If True, display cover as circular (for artists)
        """
        self.setWindowTitle(t("download_cover_manual"))
        self.setMinimumSize(800, 600)
        self.resize(900, 650)
        self.setStyleSheet(self.DARK_STYLE)

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)

        # Info label at top
        info_label = QLabel(info_text)
        info_label.setStyleSheet("font-size: 16px; padding: 10px;")
        layout.addWidget(info_label)

        # Main content area with splitter
        splitter = QSplitter(Qt.Horizontal)

        # Left side: Search results list
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        results_label = QLabel(t("search_results") + ":")
        results_label.setStyleSheet("font-weight: bold;")
        left_layout.addWidget(results_label)

        self._results_list = QListWidget()
        self._results_list.setMinimumWidth(300)
        self._results_list.setFocusPolicy(Qt.NoFocus)
        self._results_list.itemClicked.connect(self._on_result_selected)
        left_layout.addWidget(self._results_list)

        # Search button
        self._search_btn = QPushButton(t("search"))
        self._search_btn.clicked.connect(self._search_covers)
        left_layout.addWidget(self._search_btn)

        splitter.addWidget(left_widget)

        # Right side: Cover preview
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        cover_title = QLabel(t("album_art") + ":")
        cover_title.setStyleSheet("font-weight: bold;")
        right_layout.addWidget(cover_title)

        self._cover_label = QLabel()
        self._cover_label.setMinimumSize(cover_size, cover_size)
        self._cover_label.setAlignment(Qt.AlignCenter)

        # Set border style based on circular flag
        if circular:
            border_radius = cover_size // 2
            self._cover_label.setStyleSheet(f"""
                QLabel {{
                    border: 2px solid #404040;
                    border-radius: {border_radius}px;
                    background-color: #1a1a1a;
                }}
            """)
        else:
            self._cover_label.setStyleSheet("""
                QLabel {
                    border: 2px solid #404040;
                    border-radius: 8px;
                    background-color: #1a1a1a;
                }
            """)
        self._cover_label.setText(t("searching"))

        # Wrap in scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidget(self._cover_label)
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)
        right_layout.addWidget(scroll_area)

        # Match score display
        self._score_label = QLabel()
        self._score_label.setAlignment(Qt.AlignCenter)
        self._score_label.setStyleSheet("color: #1db954; font-weight: bold;")
        right_layout.addWidget(self._score_label)

        splitter.addWidget(right_widget)
        splitter.setSizes([300, 500])

        layout.addWidget(splitter)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # Status label
        self._status_label = QLabel()
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet("color: #a0a0a0;")
        layout.addWidget(self._status_label)

        # Buttons
        button_layout = QHBoxLayout()

        self._save_btn = QPushButton(t("save"))
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save_cover)
        button_layout.addWidget(self._save_btn)

        close_btn = QPushButton(t("cancel"))
        close_btn.clicked.connect(self.reject)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    # ========================================================================
    # Common Event Handlers
    # ========================================================================

    def _on_download_failed(self, error_message: str):
        """Handle cover download failure."""
        self._status_label.setText(error_message)
        self._cover_label.setText(t("cover_load_failed"))

    def _on_download_finished(self):
        """Handle download thread completion."""
        self._progress.setVisible(False)

    def _on_cover_downloaded_base(self, cover_data: bytes, source: str, circular: bool = False):
        """Handle successful cover download - base implementation.

        Args:
            cover_data: The downloaded cover data
            source: The source of the cover
            circular: If True, display as circular image
        """
        self._current_cover_data = cover_data
        self._status_label.setText(f"{t('success')} ({source})")

        try:
            image = QImage.fromData(cover_data)
            if not image.isNull():
                pixmap = QPixmap.fromImage(image)
                size = self._cover_label.minimumSize().width()

                if circular:
                    scaled_pixmap = self._make_circular(pixmap.scaled(
                        size, size,
                        Qt.KeepAspectRatioByExpanding,
                        Qt.SmoothTransformation
                    ))
                else:
                    scaled_pixmap = pixmap.scaled(
                        size, size,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                self._cover_label.setPixmap(scaled_pixmap)
                self._save_btn.setEnabled(True)
            else:
                self._cover_label.setText(t("cover_load_failed"))
        except Exception as e:
            logger.error(f"Error displaying cover: {e}", exc_info=True)
            self._cover_label.setText(t("cover_load_failed"))

    def _make_circular(self, pixmap: QPixmap) -> QPixmap:
        """Make a pixmap circular."""
        size = min(pixmap.width(), pixmap.height())
        result = QPixmap(size, size)
        result.fill(Qt.transparent)

        painter = QPainter(result)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # Create circular clip path
        clip_path = QPainterPath()
        clip_path.addEllipse(0, 0, size, size)
        painter.setClipPath(clip_path)

        # Draw the pixmap
        painter.drawPixmap(0, 0, pixmap)
        painter.end()

        return result

    # ========================================================================
    # Abstract Methods (Subclasses must implement)
    # ========================================================================

    @abstractmethod
    def _search_covers(self):
        """Search for covers - subclass implementation."""
        pass

    @abstractmethod
    def _format_result_display(self, result: dict) -> str:
        """Format search result for display in list.

        Args:
            result: Search result dictionary

        Returns:
            Formatted string for display
        """
        pass

    @abstractmethod
    def _on_result_selected(self, item: QListWidgetItem):
        """Handle result selection - download and display cover.

        Args:
            item: Selected list item
        """
        pass

    @abstractmethod
    def _save_cover(self):
        """Save cover - subclass implementation."""
        pass

    # ========================================================================
    # Shared Search Result Handlers
    # ========================================================================

    def _on_search_completed_base(self, results: list):
        """Handle search completion - shared implementation."""
        self._search_results = results
        self._progress.setVisible(False)
        self._search_btn.setEnabled(True)

        if not results:
            self._status_label.setText(t("no_results"))
            self._cover_label.setText(t("no_results"))
            return

        # Populate results list
        for result in results:
            display = self._format_result_display(result)
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, result)
            self._results_list.addItem(item)

        # Auto-select first result
        if self._results_list.count() > 0:
            self._results_list.setCurrentRow(0)
            self._on_result_selected(self._results_list.item(0))

        self._status_label.setText(f"{t('found')} {len(results)} {t('results')}")

    def _on_search_failed_base(self, error_message: str):
        """Handle search failure - shared implementation."""
        self._progress.setVisible(False)
        self._search_btn.setEnabled(True)
        self._status_label.setText(error_message)
        self._cover_label.setText(t("no_results"))

    # ========================================================================
    # QQ Music Cover Fetch (Shared)
    # ========================================================================

    def _fetch_qqmusic_cover_base(self, album_mid: str = None, song_mid: str = None,
                                   singer_mid: str = None, result: dict = None,
                                   is_artist: bool = False):
        """Fetch QQ Music cover URL lazily and download - shared implementation.

        Args:
            album_mid: Album mid (for album/track covers)
            song_mid: Song mid (for track covers)
            singer_mid: Singer mid (for artist covers)
            result: Search result dict with score
            is_artist: True for artist covers (uses QQMusicArtistCoverFetchThread)
        """
        if result is None:
            result = {}
        score = result.get('score', 0)
        logger.info(f"QQ Music lazy fetch: album_mid={album_mid}, song_mid={song_mid}, singer_mid={singer_mid}")

        # Update score display
        self._score_label.setText(f"{t('match_score')}: {score:.0f}%")

        # Stop any running download thread
        if self._download_thread and self._download_thread.isRunning():
            self._download_thread.terminate()
            self._download_thread.wait()

        self._progress.setVisible(True)
        self._progress.setRange(0, 0)
        self._status_label.setText(t("downloading"))

        if is_artist and singer_mid:
            # Use QQMusicArtistCoverFetchThread for artist covers
            self._download_thread = QQMusicArtistCoverFetchThread(
                singer_mid=singer_mid,
                score=score
            )
        else:
            # Use QQMusicCoverFetchThread for album/track covers
            self._download_thread = QQMusicCoverFetchThread(
                album_mid=album_mid,
                song_mid=song_mid,
                score=score
            )

        self._download_thread.cover_fetched.connect(self._on_qqmusic_cover_fetched)
        self._download_thread.fetch_failed.connect(self._on_qqmusic_cover_failed)
        self._download_thread.finished.connect(self._on_download_finished)
        self._download_thread.start()

    def _on_qqmusic_cover_fetched(self, cover_data: bytes, source: str, score: float):
        """Handle QQ Music cover fetch success - shared implementation."""
        logger.info(f"QQ Music cover fetched: {len(cover_data)} bytes")
        # Call subclass _on_cover_downloaded which calls _on_cover_downloaded_base
        self._on_cover_downloaded(cover_data, source)
        self._score_label.setText(f"{t('match_score')}: {score:.0f}%")

    def _on_qqmusic_cover_failed(self, error_message: str):
        """Handle QQ Music cover fetch failure - shared implementation."""
        logger.warning(f"QQ Music cover fetch failed: {error_message}")
        self._progress.setVisible(False)
        self._status_label.setText(error_message)
        self._cover_label.setText(t("cover_load_failed"))

    @abstractmethod
    def _on_cover_downloaded(self, cover_data: bytes, source: str):
        """Handle successful cover download - subclass calls _on_cover_downloaded_base."""
        pass

    # ========================================================================
    # Cleanup
    # ========================================================================

    def closeEvent(self, event):
        """Clean up on close."""
        if self._search_thread and self._search_thread.isRunning():
            self._search_thread.terminate()
            self._search_thread.wait()
        if self._download_thread and self._download_thread.isRunning():
            self._download_thread.terminate()
            self._download_thread.wait()
        super().closeEvent(event)
