"""
Cover download dialog for manually downloading album covers.
"""
import logging
from typing import List

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QProgressBar, QMessageBox, QScrollArea, QWidget,
    QListWidget, QListWidgetItem, QSplitter
)

from domain.track import Track
from services.metadata import CoverService
from system.i18n import t

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
        try:
            results = self.cover_service.search_covers(
                self.title,
                self.artist,
                self.album,
                self.duration
            )
            self.search_completed.emit(results)
        except Exception as e:
            logger.error(f"Error searching covers: {e}", exc_info=True)
            self.search_failed.emit(f"{t('error')}: {str(e)}")


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


class CoverDownloadDialog(QDialog):
    """Dialog for manually downloading album covers with smart matching."""

    def __init__(self, tracks: List[Track], cover_service: CoverService, parent=None, save_callback=None):
        super().__init__(parent)
        self.tracks = tracks
        self.current_track_index = 0
        self.cover_service = cover_service
        self.search_thread = None
        self.download_thread = None
        self.current_cover_data = None
        self.current_cover_url = None
        self.search_results = []  # Store search results
        self._save_callback = save_callback  # Custom save callback for non-track items (e.g., cloud files)
        self._setup_ui()
        self._load_track_info()

    def _setup_ui(self):
        """Setup the dialog UI."""
        self.setWindowTitle(t("download_cover_manual"))
        self.setMinimumSize(900, 700)
        self.resize(1000, 750)

        # Apply dark theme styling
        self.setStyleSheet("""
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
            QComboBox {
                background-color: #3a3a3a;
                color: #ffffff;
                border: 1px solid #4a4a4a;
                border-radius: 4px;
                padding: 6px 12px;
                min-width: 150px;
            }
            QComboBox:hover {
                background-color: #4a4a4a;
            }
            QComboBox::drop-down {
                border: none;
                background-color: #3a3a3a;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #ffffff;
                width: 0;
                height: 0;
            }
            QComboBox QAbstractItemView {
                background-color: #2a2a2a;
                color: #ffffff;
                border: 1px solid #4a4a4a;
                selection-background-color: #1db954;
                selection-color: #ffffff;
                padding: 4px;
            }
            QComboBox QAbstractItemView::item {
                color: #ffffff;
                padding: 6px 12px;
                min-height: 24px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #3a3a2a;
                color: #ffffff;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #1db954;
                color: #ffffff;
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
        """)

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)

        # Track selection
        track_header = QHBoxLayout()
        track_label = QLabel(t("track") + ":")
        track_label.setStyleSheet("font-weight: bold;")
        track_header.addWidget(track_label)

        self.track_combo = QComboBox()
        self.track_combo.currentIndexChanged.connect(self._on_track_changed)
        track_header.addWidget(self.track_combo)

        self.track_info_label = QLabel()
        self.track_info_label.setStyleSheet("color: #a0a0a0;")
        track_header.addWidget(self.track_info_label)

        track_header.addStretch()
        layout.addLayout(track_header)

        # Track details
        self.details_label = QLabel()
        self.details_label.setStyleSheet("""
            QLabel {
                background-color: #2a2a2a;
                border-radius: 6px;
                padding: 12px;
                color: #e0e0e0;
            }
        """)
        layout.addWidget(self.details_label)

        # Main content area with splitter
        splitter = QSplitter(Qt.Horizontal)

        # Left side: Search results list
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        results_label = QLabel(t("search_results") + ":")
        results_label.setStyleSheet("font-weight: bold;")
        left_layout.addWidget(results_label)

        self.results_list = QListWidget()
        self.results_list.setMinimumWidth(350)
        self.results_list.setFocusPolicy(Qt.NoFocus)  # Prevent automatic focus
        self.results_list.itemClicked.connect(self._on_result_selected)
        left_layout.addWidget(self.results_list)

        # Search button
        self.search_btn = QPushButton(t("search"))
        self.search_btn.clicked.connect(self._search_covers)
        left_layout.addWidget(self.search_btn)

        splitter.addWidget(left_widget)

        # Right side: Cover preview
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        cover_title = QLabel(t("album_art") + ":")
        cover_title.setStyleSheet("font-weight: bold;")
        right_layout.addWidget(cover_title)

        self.cover_label = QLabel()
        self.cover_label.setMinimumSize(400, 400)
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setStyleSheet("""
            QLabel {
                border: 2px solid #404040;
                border-radius: 8px;
                background-color: #1a1a1a;
            }
        """)
        self.cover_label.setText(t("cover_load_failed"))

        # Wrap in scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.cover_label)
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)
        right_layout.addWidget(scroll_area)

        # Match score display
        self.score_label = QLabel()
        self.score_label.setAlignment(Qt.AlignCenter)
        self.score_label.setStyleSheet("color: #1db954; font-weight: bold;")
        right_layout.addWidget(self.score_label)

        splitter.addWidget(right_widget)

        # Set splitter sizes
        splitter.setSizes([350, 550])

        layout.addWidget(splitter)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # Status label
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #a0a0a0;")
        layout.addWidget(self.status_label)

        # Buttons
        button_layout = QHBoxLayout()

        self.save_btn = QPushButton(t("save"))
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._save_cover)
        button_layout.addWidget(self.save_btn)

        close_btn = QPushButton(t("cancel"))
        close_btn.clicked.connect(self.reject)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def _load_track_info(self):
        """Load track information into UI."""
        # Populate track combo
        self.track_combo.clear()
        for track in self.tracks:
            display_text = f"{track.title}"
            if track.artist:
                display_text += f" - {track.artist}"
            self.track_combo.addItem(display_text)

        if self.tracks:
            self.track_combo.setCurrentIndex(0)
            self._update_track_details()

    def _update_track_details(self):
        """Update track details display."""
        if not self.tracks or self.current_track_index >= len(self.tracks):
            return

        track = self.tracks[self.current_track_index]

        # Update track info label
        total = len(self.tracks)
        self.track_info_label.setText(f"{self.current_track_index + 1} / {total}")

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
        self.details_label.setText(details_text)

        # Reset cover display
        self.current_cover_data = None
        self.current_cover_url = None
        self.search_results = []
        self.results_list.clear()
        self.save_btn.setEnabled(False)
        self.score_label.setText("")
        self._display_existing_cover(track)

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
                    self.cover_label.setPixmap(scaled_pixmap)
                    self.status_label.setText(t("cover_already_exists"))
                    return
            except Exception as e:
                logger.debug(f"Error loading existing cover: {e}")

        self.cover_label.setText(t("cover_load_failed"))
        self.status_label.setText("")

    def _on_track_changed(self, index: int):
        """Handle track selection change."""
        if index >= 0 and index < len(self.tracks):
            self.current_track_index = index
            self._update_track_details()

    def _search_covers(self):
        """Search for covers from NetEase."""
        if self.search_thread and self.search_thread.isRunning():
            return

        if not self.tracks or self.current_track_index >= len(self.tracks):
            return

        track = self.tracks[self.current_track_index]

        # Update UI
        self.search_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # Indeterminate progress
        self.status_label.setText(t("searching"))
        self.results_list.clear()
        self.search_results = []

        # Get duration if available
        duration = getattr(track, 'duration', None)

        # Start search thread
        self.search_thread = CoverSearchThread(
            self.cover_service,
            track.title,
            track.artist,
            track.album,
            duration
        )
        self.search_thread.search_completed.connect(self._on_search_completed)
        self.search_thread.search_failed.connect(self._on_search_failed)
        self.search_thread.start()

    def _on_search_completed(self, results: list):
        """Handle search completion."""
        self.search_results = results
        self.progress.setVisible(False)
        self.search_btn.setEnabled(True)

        if not results:
            self.status_label.setText(t("no_results"))
            return

        # Populate results list
        for result in results:
            title = result.get('title', '')
            artist = result.get('artist', '')
            album = result.get('album', '')
            source = result.get('source', '')
            score = result.get('score', 0)

            # Format display text
            display = f"{title}"
            if artist:
                display += f" - {artist}"
            if album:
                display += f" ({album})"
            display += f" [{source}] [{score:.0f}%]"

            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, result)  # Store full result data
            self.results_list.addItem(item)

        # Auto-select first result
        if self.results_list.count() > 0:
            self.results_list.setCurrentRow(0)
            self._on_result_selected(self.results_list.item(0))

        self.status_label.setText(f"{t('found')} {len(results)} {t('results')}")

    def _on_search_failed(self, error_message: str):
        """Handle search failure."""
        self.progress.setVisible(False)
        self.search_btn.setEnabled(True)
        self.status_label.setText(error_message)

    def _on_result_selected(self, item: QListWidgetItem):
        """Handle result selection - download and display cover."""
        result = item.data(Qt.UserRole)
        cover_url = result.get('cover_url')

        if not cover_url:
            return

        self.current_cover_url = cover_url
        score = result.get('score', 0)

        # Update score display
        self.score_label.setText(f"{t('match_score')}: {score:.0f}%")

        # Download cover preview
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.terminate()
            self.download_thread.wait()

        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.status_label.setText(t("downloading"))

        self.download_thread = CoverDownloadThread(
            self.cover_service,
            cover_url,
            result.get('source', '')
        )
        self.download_thread.cover_downloaded.connect(self._on_cover_downloaded)
        self.download_thread.download_failed.connect(self._on_download_failed)
        self.download_thread.finished.connect(self._on_download_finished)
        self.download_thread.start()

    def _on_cover_downloaded(self, cover_data: bytes, source: str):
        """Handle successful cover download."""
        self.current_cover_data = cover_data
        self.status_label.setText(f"{t('success')} ({source})")

        # Display cover
        try:
            image = QImage.fromData(cover_data)
            if not image.isNull():
                pixmap = QPixmap.fromImage(image)
                scaled_pixmap = pixmap.scaled(
                    400, 400,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.cover_label.setPixmap(scaled_pixmap)
                self.save_btn.setEnabled(True)
            else:
                self.cover_label.setText(t("cover_load_failed"))
        except Exception as e:
            logger.error(f"Error displaying cover: {e}", exc_info=True)
            self.cover_label.setText(t("cover_load_failed"))

    def _on_download_failed(self, error_message: str):
        """Handle cover download failure."""
        self.status_label.setText(error_message)
        self.cover_label.setText(t("cover_load_failed"))

    def _on_download_finished(self):
        """Handle download thread completion."""
        self.progress.setVisible(False)

    def _save_cover(self):
        """Save cover to database."""
        if not self.current_cover_data:
            return

        if not self.tracks or self.current_track_index >= len(self.tracks):
            return

        track = self.tracks[self.current_track_index]

        # Save cover to cache
        cover_path = self.cover_service.save_cover_data_to_cache(
            self.current_cover_data,
            track.artist,
            track.title,
            track.album
        )

        if cover_path:
            # Use custom save callback if provided (for cloud files, etc.)
            if self._save_callback:
                success = self._save_callback(track, cover_path, self.current_cover_data)
                if success:
                    self.accept()
                else:
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
            from system.event_bus import EventBus
            bus = EventBus.instance()
            bus.cover_updated.emit(track.id, False)  # False = is_cloud (local track)

            self.accept()
        else:
            QMessageBox.warning(
                self,
                t("error"),
                t("cover_save_failed")
            )

    def closeEvent(self, event):
        """Clean up on close."""
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.terminate()
            self.search_thread.wait()
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.terminate()
            self.download_thread.wait()
        super().closeEvent(event)
