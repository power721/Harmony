"""
Track cover download dialog for downloading track/song covers.
"""
import logging
from typing import List

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox, QListWidgetItem, QListWidget, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QSplitter, QScrollArea, QProgressBar, QPushButton
)

from domain.track import Track
from services.metadata import CoverService
from system.event_bus import EventBus
from system.i18n import t
from ui.widgets.base_cover_download_dialog import (
    BaseCoverDownloadDialog, CoverDownloadThread, QQMusicCoverFetchThread
)

logger = logging.getLogger(__name__)


class CoverSearchThread(QThread):
    """Thread for searching covers."""
    search_completed = Signal(list)  # Emits list of search results
    search_failed = Signal(str)  # Emits error message

    def __init__(self, cover_service: CoverService, title: str, artist: str, album: str, duration: float = None):
        super().__init__()
        self.cover_service = cover_service
        self.title = title
        self.artist = artist
        self.album = album
        self.duration = duration

    def run(self):
        """Search for covers."""
        logger.info(f"=== CoverSearchThread.run() called: {self.title} - {self.artist} ===")
        try:
            results = self.cover_service.search_covers(
                self.title,
                self.artist,
                self.album,
                self.duration
            )
            logger.info(f"=== search_covers returned {len(results)} results ===")
            self.search_completed.emit(results)
        except Exception as e:
            logger.info(f"search_covers error: {e}")
            logger.error(f"Error searching covers: {e}", exc_info=True)
            self.search_failed.emit(f"{t('error')}: {str(e)}")


class TrackCoverDownloadDialog(BaseCoverDownloadDialog):
    """Dialog for downloading track/song covers with smart matching."""

    def __init__(self, tracks: List[Track], cover_service: CoverService, parent=None, save_callback=None):
        super().__init__(cover_service, parent)
        self._tracks = tracks
        self._current_track_index = 0
        self._save_callback = save_callback  # Custom save callback for non-track items (e.g., cloud files)
        self._setup_ui()
        self._load_track_info()

    # ========================================================================
    # Properties for backward compatibility
    # ========================================================================

    @property
    def tracks(self) -> List[Track]:
        return self._tracks

    @property
    def current_track_index(self) -> int:
        return self._current_track_index

    @property
    def track_combo(self):
        return self._track_combo

    @property
    def track_info_label(self):
        return self._track_info_label

    @property
    def details_label(self):
        return self._details_label

    @property
    def search_btn(self):
        return self._search_btn

    @property
    def results_list(self):
        return self._results_list

    def _setup_ui(self):
        """Setup the dialog UI with track selection."""
        self.setWindowTitle(t("download_cover_manual"))
        self.setMinimumSize(900, 700)
        self.resize(1000, 750)
        self.setStyleSheet(self.DARK_STYLE)

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)

        # Track selection
        track_header = QHBoxLayout()
        track_label = QLabel(t("track") + ":")
        track_label.setStyleSheet("font-weight: bold;")
        track_header.addWidget(track_label)

        self._track_combo = QComboBox()
        self._track_combo.currentIndexChanged.connect(self._on_track_changed)
        track_header.addWidget(self._track_combo)

        self._track_info_label = QLabel()
        self._track_info_label.setStyleSheet("color: #a0a0a0;")
        track_header.addWidget(self._track_info_label)

        track_header.addStretch()
        layout.addLayout(track_header)

        # Track details
        self._details_label = QLabel()
        self._details_label.setStyleSheet("""
            QLabel {
                background-color: #2a2a2a;
                border-radius: 6px;
                padding: 12px;
                color: #e0e0e0;
            }
        """)
        layout.addWidget(self._details_label)

        # Add common UI components (search results list, cover preview, etc.)
        self._add_common_ui_components(layout)

        self.setLayout(layout)

    def _add_common_ui_components(self, layout):
        """Add common UI components from base class."""
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
        self._results_list.setMinimumWidth(350)
        self._results_list.setFocusPolicy(Qt.NoFocus)
        self._results_list.itemClicked.connect(self._on_result_selected)
        self._results_list.currentItemChanged.connect(self._on_current_item_changed)
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
        self._cover_label.setMinimumSize(400, 400)
        self._cover_label.setAlignment(Qt.AlignCenter)
        self._cover_label.setStyleSheet("""
            QLabel {
                border: 2px solid #404040;
                border-radius: 8px;
                background-color: #1a1a1a;
            }
        """)
        self._cover_label.setText(t("cover_load_failed"))

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
        splitter.setSizes([350, 550])

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

    def _load_track_info(self):
        """Load track information into UI."""
        # Populate track combo
        self._track_combo.clear()
        for track in self._tracks:
            display_text = f"{track.title}"
            if track.artist:
                display_text += f" - {track.artist}"
            self._track_combo.addItem(display_text)

        if self._tracks:
            self._track_combo.setCurrentIndex(0)
            self._update_track_details()

    def _update_track_details(self):
        """Update track details display."""
        if not self._tracks or self._current_track_index >= len(self._tracks):
            return

        track = self._tracks[self._current_track_index]

        # Update track info label
        total = len(self._tracks)
        self._track_info_label.setText(f"{self._current_track_index + 1} / {total}")

        # Update details label
        details_text = f"<b>{t('title')}</b>: {track.title}"
        if track.artist:
            details_text += f"<br><b>{t('artist')}</b>: {track.artist}"
        if track.album:
            details_text += f"<br><b>{t('album')}</b>: {track.album}"
        # Show duration if available
        if hasattr(track, 'duration') and track.duration:
            duration_str = self._format_duration(track.duration)
            details_text += f"<br><b>{t('duration')}</b>: {duration_str}"
        self._details_label.setText(details_text)

        # Reset cover display
        self._current_cover_data = None
        self._current_cover_url = None
        self._search_results = []
        self._results_list.clear()
        self._save_btn.setEnabled(False)
        self._score_label.setText("")
        self._display_existing_cover(track)
        self._search_covers()

    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to MM:SS."""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}:{secs:02d}"

    def _display_existing_cover(self, track: Track):
        """Display existing cover if available."""
        if track.cover_path:
            try:
                pixmap = QPixmap(track.cover_path)
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(
                        400, 400,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                    self._cover_label.setPixmap(scaled_pixmap)
                    self._status_label.setText(t("cover_already_exists"))
                    return
            except Exception as e:
                logger.debug(f"Error loading existing cover: {e}")

        self._cover_label.setText(t("cover_load_failed"))
        self._status_label.setText("")

    def _on_track_changed(self, index: int):
        """Handle track selection change."""
        if index >= 0 and index < len(self._tracks):
            self._current_track_index = index
            self._update_track_details()

    def _search_covers(self):
        """Search for covers from NetEase."""
        logger.debug("_search_covers called")
        if self._search_thread and self._search_thread.isRunning():
            logger.debug("Search thread already running")
            return

        if not self._tracks or self._current_track_index >= len(self._tracks):
            logger.debug("No tracks selected")
            return

        track = self._tracks[self._current_track_index]
        logger.debug(f"Searching for: {track.title} - {track.artist}")

        # Update UI
        self._search_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)  # Indeterminate progress
        self._status_label.setText(t("searching"))
        self._results_list.clear()
        self._search_results = []

        # Get duration if available
        duration = getattr(track, 'duration', None)

        # Start search thread
        self._search_thread = CoverSearchThread(
            self._cover_service,
            track.title,
            track.artist,
            track.album,
            duration
        )
        self._search_thread.search_completed.connect(self._on_search_completed)
        self._search_thread.search_failed.connect(self._on_search_failed)
        logger.debug("Starting search thread")
        self._search_thread.start()

    def _on_search_completed(self, results: list):
        """Handle search completion."""
        logger.info(f"=== _on_search_completed called with {len(results)} results ===")
        self._search_results = results
        self._progress.setVisible(False)
        self._search_btn.setEnabled(True)

        if not results:
            self._status_label.setText(t("no_results"))
            return

        # Populate results list
        for i, result in enumerate(results):
            display = self._format_result_display(result)
            logger.info(f"Result {i}: source={result.get('source')}, cover_url={result.get('cover_url')}, album_mid={result.get('album_mid')}")

            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, result)  # Store full result data
            self._results_list.addItem(item)

        # Auto-select first result (will trigger currentItemChanged signal)
        if self._results_list.count() > 0:
            self._results_list.setCurrentRow(0)

        self._status_label.setText(f"{t('found')} {len(results)} {t('results')}")

    def _on_search_failed(self, error_message: str):
        """Handle search failure."""
        self._progress.setVisible(False)
        self._search_btn.setEnabled(True)
        self._status_label.setText(error_message)

    def _format_result_display(self, result: dict) -> str:
        """Format search result for display in list."""
        title = result.get('title', '')
        artist = result.get('artist', '')
        album = result.get('album', '')
        source = result.get('source', '')
        score = result.get('score', 0)

        display = f"{title}"
        if artist:
            display += f" - {artist}"
        if album:
            display += f" ({album})"
        display += f" [{source}] [{score:.0f}%]"
        return display

    def _on_current_item_changed(self, current: QListWidgetItem, previous: QListWidgetItem):
        """Handle current item change - download and display cover."""
        logger.info(f"=== _on_current_item_changed: current={current} ===")
        if current:
            self._on_result_selected(current)

    def _on_result_selected(self, item: QListWidgetItem):
        """Handle result selection - download and display cover."""
        result = item.data(Qt.UserRole)
        cover_url = result.get('cover_url')
        source = result.get('source', '')
        album_mid = result.get('album_mid')
        song_mid = result.get('id')
        logger.info(f"=== Result selected: source={source}, cover_url={cover_url}, album_mid={album_mid}, song_mid={song_mid} ===")

        # For QQ Music, fetch cover URL lazily
        if not cover_url and source == 'qqmusic':
            logger.info(f"QQ Music lazy fetch triggered: album_mid={album_mid}, song_mid={song_mid}")
            if album_mid or song_mid:
                self._fetch_qqmusic_cover(album_mid, song_mid, result)
                return
            else:
                logger.warning("QQ Music result has no album_mid or song_mid")
                self._status_label.setText(t("cover_load_failed"))
                return

        if not cover_url:
            logger.warning(f"No cover_url for source={source}")
            self._status_label.setText(t("cover_load_failed"))
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
        score = result.get('score', 0)
        logger.info(f"=== _fetch_qqmusic_cover called: album_mid={album_mid}, song_mid={song_mid} ===")

        # Update score display
        self._score_label.setText(f"{t('match_score')}: {score:.0f}%")

        # Stop any running download thread
        if self._download_thread and self._download_thread.isRunning():
            self._download_thread.terminate()
            self._download_thread.wait()

        self._progress.setVisible(True)
        self._progress.setRange(0, 0)
        self._status_label.setText(t("downloading"))

        # Use QQMusicCoverFetchThread for lazy fetch
        self._download_thread = QQMusicCoverFetchThread(
            album_mid=album_mid,
            song_mid=song_mid,
            score=score
        )
        self._download_thread.cover_fetched.connect(self._on_qqmusic_cover_fetched)
        self._download_thread.fetch_failed.connect(self._on_qqmusic_cover_failed)
        self._download_thread.finished.connect(self._on_download_finished)
        self._download_thread.start()
        logger.info(f"Thread started, isRunning={self._download_thread.isRunning()}")

    def _on_qqmusic_cover_fetched(self, cover_data: bytes, source: str, score: float):
        """Handle QQ Music cover fetch success."""
        logger.info(f"=== _on_qqmusic_cover_fetched: {len(cover_data)} bytes ===")
        self._on_cover_downloaded(cover_data, source)
        self._score_label.setText(f"{t('match_score')}: {score:.0f}%")

    def _on_qqmusic_cover_failed(self, error_message: str):
        """Handle QQ Music cover fetch failure."""
        logger.warning(f"_on_qqmusic_cover_failed: {error_message}")
        self._progress.setVisible(False)
        self._status_label.setText(error_message)
        self._cover_label.setText(t("cover_load_failed"))

    def _on_cover_downloaded(self, cover_data: bytes, source: str):
        """Handle successful cover download."""
        self._on_cover_downloaded_base(cover_data, source, circular=False)

    def _save_cover(self):
        """Save cover to database."""
        if not self._current_cover_data:
            return

        if not self._tracks or self._current_track_index >= len(self._tracks):
            return

        track = self._tracks[self._current_track_index]

        # Save cover to cache
        cover_path = self._cover_service.save_cover_data_to_cache(
            self._current_cover_data,
            track.artist,
            track.title,
            track.album
        )

        if cover_path:
            # Use custom save callback if provided (for cloud files, etc.)
            if self._save_callback:
                success = self._save_callback(track, cover_path, self._current_cover_data)
                if success:
                    self.accept()
                else:
                    from PySide6.QtWidgets import QMessageBox
                    QMessageBox.warning(
                        self,
                        t("error"),
                        t("cover_save_failed")
                    )
                return

            # Default behavior: Update track in database
            from app import Application
            app = Application.instance()
            if app and app.bootstrap:
                track_repo = app.bootstrap.track_repo
                track.cover_path = cover_path
                track_repo.update(track)

            # Notify listeners to refresh cover display
            bus = EventBus.instance()
            bus.cover_updated.emit(track.id, False)  # False = is_cloud (local track)

            self.accept()
        else:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                t("error"),
                t("cover_save_failed")
            )


# Backward compatibility alias
CoverDownloadDialog = TrackCoverDownloadDialog
