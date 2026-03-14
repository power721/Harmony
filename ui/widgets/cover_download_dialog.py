"""
Cover download dialog for manually downloading album covers.
"""
import logging
from typing import Optional, List

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QProgressBar, QMessageBox, QScrollArea, QWidget
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QPixmap

from services.metadata import CoverService
from domain.track import Track
from system.i18n import t

logger = logging.getLogger(__name__)


class CoverDownloadThread(QThread):
    """Thread for downloading cover art."""
    cover_downloaded = Signal(bytes, str)  # Emits cover data and source
    download_failed = Signal(str)  # Emits error message
    finished = Signal()

    def __init__(self, cover_service: CoverService, title: str, artist: str, album: str, source: str):
        super().__init__()
        self.cover_service = cover_service
        self.title = title
        self.artist = artist
        self.album = album
        self.source = source

    def run(self):
        """Download cover from specified source."""
        try:
            cover_data = None

            if self.source == "NetEase":
                cover_data = self.cover_service._fetch_from_netease(self.artist, self.album or self.title)
            elif self.source == "iTunes":
                cover_data = self.cover_service._fetch_from_itunes(self.artist, self.album or self.title)
            elif self.source == "MusicBrainz":
                cover_data = self.cover_service._fetch_from_musicbrainz(self.artist, self.album or self.title)
            elif self.source == "Last.fm":
                cover_data = self.cover_service._fetch_from_lastfm(self.artist, self.album or self.title)

            if cover_data:
                self.cover_downloaded.emit(cover_data, self.source)
            else:
                self.download_failed.emit(t("cover_download_failed") + f" ({self.source})")
        except Exception as e:
            logger.error(f"Error downloading cover: {e}", exc_info=True)
            self.download_failed.emit(f"{t('error')}: {str(e)}")
        finally:
            self.finished.emit()


class CoverDownloadDialog(QDialog):
    """Dialog for manually downloading album covers."""

    def __init__(self, tracks: List[Track], cover_service: CoverService, parent=None, save_callback=None):
        super().__init__(parent)
        self.tracks = tracks
        self.current_track_index = 0
        self.cover_service = cover_service
        self.download_thread = None
        self.current_cover_data = None
        self._save_callback = save_callback  # Custom save callback for non-track items (e.g., cloud files)
        self._setup_ui()
        self._load_track_info()

    def _setup_ui(self):
        """Setup the dialog UI."""
        self.setWindowTitle(t("download_cover"))
        self.setMinimumSize(800, 700)
        self.resize(900, 750)  # Set a larger default size

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
                background-color: #3a3a3a;
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

        # Cover preview
        cover_layout = QVBoxLayout()
        cover_title = QLabel(t("album_art") + ":")
        cover_title.setStyleSheet("font-weight: bold;")
        cover_layout.addWidget(cover_title)

        self.cover_label = QLabel()
        self.cover_label.setMinimumSize(500, 500)
        self.cover_label.setMaximumSize(500, 500)
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setStyleSheet("""
            QLabel {
                border: 2px solid #404040;
                border-radius: 8px;
                background-color: #1a1a1a;
            }
        """)
        self.cover_label.setText(t("cover_load_failed"))

        # Wrap in scroll area for large covers
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.cover_label)
        scroll_area.setWidgetResizable(True)
        scroll_area.setMaximumHeight(550)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)
        cover_layout.addWidget(scroll_area)
        layout.addLayout(cover_layout)

        # Source selection
        source_layout = QHBoxLayout()
        source_label = QLabel(t("cover_source") + ":")
        source_label.setStyleSheet("font-weight: bold;")
        source_layout.addWidget(source_label)

        self.source_combo = QComboBox()
        self.source_combo.addItems(["NetEase", "iTunes", "MusicBrainz", "Last.fm"])
        source_layout.addWidget(self.source_combo)
        source_layout.addStretch()
        layout.addLayout(source_layout)

        # Download button
        self.download_btn = QPushButton(t("download"))
        self.download_btn.clicked.connect(self._download_cover)
        layout.addWidget(self.download_btn)

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
        self.details_label.setText(details_text)

        # Reset cover display
        self.current_cover_data = None
        self.save_btn.setEnabled(False)
        self._display_existing_cover(track)

    def _display_existing_cover(self, track: Track):
        """Display existing cover if available."""
        if track.cover_path:
            try:
                pixmap = QPixmap(track.cover_path)
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(
                        500, 500,
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

    def _download_cover(self):
        """Download cover from selected source."""
        if self.download_thread and self.download_thread.isRunning():
            return

        if not self.tracks or self.current_track_index >= len(self.tracks):
            return

        track = self.tracks[self.current_track_index]
        source = self.source_combo.currentText()

        # Update UI
        self.download_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # Indeterminate progress
        self.status_label.setText(f"{t('downloading')} ({source})...")
        self.cover_label.setText(t("downloading"))
        self.save_btn.setEnabled(False)

        # Start download thread
        self.download_thread = CoverDownloadThread(
            self.cover_service,
            track.title,
            track.artist,
            track.album,
            source
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
            from io import BytesIO
            from PySide6.QtGui import QImage

            image = QImage.fromData(cover_data)
            if not image.isNull():
                pixmap = QPixmap.fromImage(image)
                scaled_pixmap = pixmap.scaled(
                    500, 500,
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
        self.download_btn.setEnabled(True)
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
                    self.status_label.setText(t("cover_saved_success"))
                    self.save_btn.setEnabled(False)
                    QMessageBox.information(
                        self,
                        t("success"),
                        t("cover_saved_success")
                    )
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

            self.status_label.setText(t("cover_saved_success"))
            self.save_btn.setEnabled(False)

            # Notify listeners to refresh cover display
            from system.event_bus import EventBus
            bus = EventBus.instance()
            bus.cover_updated.emit(track.id, False)  # False = is_cloud (local track)

            QMessageBox.information(
                self,
                t("success"),
                t("cover_saved_success")
            )
        else:
            QMessageBox.warning(
                self,
                t("error"),
                t("cover_save_failed")
            )

    def closeEvent(self, event):
        """Clean up on close."""
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.terminate()
            self.download_thread.wait()
        super().closeEvent(event)
