"""
Album cover download dialog for downloading album covers.
"""
import logging
from typing import List

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QMessageBox, QScrollArea, QWidget,
    QListWidget, QListWidgetItem, QSplitter
)

from domain.album import Album
from services.metadata import CoverService
from system.event_bus import EventBus
from system.i18n import t

logger = logging.getLogger(__name__)


class AlbumCoverSearchThread(QThread):
    """Thread for searching album covers."""
    search_completed = Signal(list)  # Emits list of search results
    search_failed = Signal(str)  # Emits error message

    def __init__(self, cover_service: CoverService, album: Album):
        super().__init__()
        self.cover_service = cover_service
        self.album = album

    def run(self):
        """Search for album covers."""
        try:
            # Search using album name and artist
            results = self.cover_service.search_covers(
                title="",  # Empty title for album search
                artist=self.album.artist,
                album=self.album.name,
                duration=None
            )
            self.search_completed.emit(results)
        except Exception as e:
            logger.error(f"Error searching album covers: {e}", exc_info=True)
            self.search_failed.emit(f"{t('error')}: {str(e)}")


class AlbumCoverDownloadThread(QThread):
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


class AlbumCoverDownloadDialog(QDialog):
    """Dialog for downloading album covers."""

    cover_saved = Signal(str)  # Emits cover path

    def __init__(self, album: Album, cover_service: CoverService, parent=None):
        super().__init__(parent)
        self._album = album
        self._cover_service = cover_service
        self._search_thread = None
        self._download_thread = None
        self._current_cover_data = None
        self._current_cover_url = None
        self._search_results = []

        self._setup_ui()
        self._search_covers()

    def _setup_ui(self):
        """Setup the dialog UI."""
        self.setWindowTitle(t("download_cover_manual"))
        self.setMinimumSize(800, 600)
        self.resize(900, 650)

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

        # Album info
        info_label = QLabel(f"<b>{self._album.display_name}</b> - {self._album.display_artist}")
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
        self._results_list.setFocusPolicy(Qt.NoFocus)  # Prevent automatic focus
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
        self._cover_label.setMinimumSize(350, 350)
        self._cover_label.setAlignment(Qt.AlignCenter)
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

        # Set splitter sizes
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

    def _search_covers(self):
        """Search for album covers."""
        if self._search_thread and self._search_thread.isRunning():
            return

        # Update UI
        self._search_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)  # Indeterminate progress
        self._status_label.setText(t("searching"))
        self._results_list.clear()
        self._search_results = []
        self._save_btn.setEnabled(False)

        # Start search thread
        self._search_thread = AlbumCoverSearchThread(
            self._cover_service,
            self._album
        )
        self._search_thread.search_completed.connect(self._on_search_completed)
        self._search_thread.search_failed.connect(self._on_search_failed)
        self._search_thread.start()

    def _on_search_completed(self, results: list):
        """Handle search completion."""
        self._search_results = results
        self._progress.setVisible(False)
        self._search_btn.setEnabled(True)

        if not results:
            self._status_label.setText(t("no_results"))
            self._cover_label.setText(t("no_results"))
            return

        # Populate results list
        for result in results:
            title = result.get('title', '')
            artist = result.get('artist', '')
            album = result.get('album', '')
            source = result.get('source', '')
            score = result.get('score', 0)

            # Format display text
            display = f"{album or title}"
            if artist:
                display += f" - {artist}"
            display += f" [{source}] [{score:.0f}%]"

            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, result)  # Store full result data
            self._results_list.addItem(item)

        # Auto-select first result
        if self._results_list.count() > 0:
            self._results_list.setCurrentRow(0)
            self._on_result_selected(self._results_list.item(0))

        self._status_label.setText(f"{t('found')} {len(results)} {t('results')}")

    def _on_search_failed(self, error_message: str):
        """Handle search failure."""
        self._progress.setVisible(False)
        self._search_btn.setEnabled(True)
        self._status_label.setText(error_message)
        self._cover_label.setText(t("no_results"))

    def _on_result_selected(self, item: QListWidgetItem):
        """Handle result selection - download and display cover."""
        result = item.data(Qt.UserRole)
        cover_url = result.get('cover_url')

        if not cover_url:
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

        self._download_thread = AlbumCoverDownloadThread(
            self._cover_service,
            cover_url,
            result.get('source', '')
        )
        self._download_thread.cover_downloaded.connect(self._on_cover_downloaded)
        self._download_thread.download_failed.connect(self._on_download_failed)
        self._download_thread.finished.connect(self._on_download_finished)
        self._download_thread.start()

    def _on_cover_downloaded(self, cover_data: bytes, source: str):
        """Handle successful cover download."""
        self._current_cover_data = cover_data
        self._status_label.setText(f"{t('success')} ({source})")

        # Display cover
        try:
            image = QImage.fromData(cover_data)
            if not image.isNull():
                pixmap = QPixmap.fromImage(image)
                scaled_pixmap = pixmap.scaled(
                    350, 350,
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

    def _on_download_failed(self, error_message: str):
        """Handle cover download failure."""
        self._status_label.setText(error_message)
        self._cover_label.setText(t("cover_load_failed"))

    def _on_download_finished(self):
        """Handle download thread completion."""
        self._progress.setVisible(False)

    def _save_cover(self):
        """Save cover to cache and update database."""
        if not self._current_cover_data:
            return

        # Save cover to cache
        cover_path = self._cover_service.save_cover_data_to_cache(
            self._current_cover_data,
            self._album.artist,
            "",  # title
            self._album.name
        )

        if cover_path:
            # Update albums in database
            from app import Application
            app = Application.instance()
            if app and app.bootstrap:
                db = app.bootstrap.db
                conn = db._get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE albums
                    SET cover_path = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE name = ? AND artist = ?
                """, (cover_path, self._album.name, self._album.artist))
                conn.commit()

            # Emit signal
            self.cover_saved.emit(cover_path)

            # Notify listeners to refresh cover display
            bus = EventBus.instance()
            bus.cover_updated.emit(f"{self._album.name}:{self._album.artist}", False)

            # Close dialog after successful save
            self.accept()
        else:
            QMessageBox.warning(
                self,
                t("error"),
                t("cover_save_failed")
            )

    def closeEvent(self, event):
        """Clean up on close."""
        if self._search_thread and self._search_thread.isRunning():
            self._search_thread.terminate()
            self._search_thread.wait()
        if self._download_thread and self._download_thread.isRunning():
            self._download_thread.terminate()
            self._download_thread.wait()
        super().closeEvent(event)
