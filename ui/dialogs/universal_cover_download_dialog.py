"""
Universal cover download dialog that works with any search strategy.
"""
import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImage, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QListWidgetItem, QListWidget, QComboBox, QLabel, QHBoxLayout, QVBoxLayout, QPushButton,
    QProgressBar, QSplitter, QWidget, QScrollArea
)

from services.metadata import CoverService
from system.i18n import t
from system.theme import ThemeManager
from ui.controllers.cover_controller import CoverController
from ui.dialogs.base_cover_download_dialog import BaseCoverDownloadDialog
from ui.dialogs.message_dialog import MessageDialog
from ui.strategies.cover_search_strategy import CoverSearchStrategy

logger = logging.getLogger(__name__)


class UniversalCoverDownloadDialog(BaseCoverDownloadDialog):
    """Universal dialog for downloading track/album/artist covers.

    Uses Strategy pattern to handle different domain types:
    - TrackSearchStrategy for tracks
    - AlbumSearchStrategy for albums
    - ArtistSearchStrategy for artists

    Features:
    - Single dialog adapts to any strategy
    - Multi-item navigation (for tracks)
    - Circular display (for artists)
    - Thread pool management via CoverController
    """

    def __init__(self, strategy: CoverSearchStrategy, cover_service: CoverService, parent=None):
        """Initialize universal dialog.

        Args:
            strategy: Search strategy (Track/Album/Artist)
            cover_service: CoverService instance
            parent: Parent widget
        """
        super().__init__(cover_service, parent)
        self._strategy = strategy
        self._items = strategy.get_items()
        self._current_index = 0
        self._current_result = None  # For lazy fetch

        # Create controller
        self._controller = CoverController(cover_service, self)

        # Setup UI
        self._setup_ui()
        self._load_items()

    def _setup_ui(self):
        """Setup UI based on strategy."""
        # Check if multi-item (Track)
        if len(self._items) > 1:
            self._setup_navigation_ui()
        else:
            # Single item
            info_text = self._strategy.get_display_text(self._items[0])
            circular = self._strategy.use_circular_display()
            self._setup_common_ui(info_text, cover_size=350, circular=circular)

    def _setup_navigation_ui(self):
        """Setup UI with track navigation for multi-item mode."""
        self.setWindowTitle(t("download_cover_manual"))
        self.setMinimumSize(900, 700)
        self.resize(1000, 750)
        self.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TEMPLATE))

        # Remove frameless window effects
        self.setWindowFlags(Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setGraphicsEffect(None)

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)

        # Item selection combo
        combo_header = QHBoxLayout()
        item_label = QLabel(t("track") + ":")
        item_label.setStyleSheet("font-weight: bold;")
        combo_header.addWidget(item_label)

        self._combo = QComboBox()
        self._combo.currentIndexChanged.connect(self._on_item_changed)
        combo_header.addWidget(self._combo)

        self._item_info_label = QLabel()
        self._item_info_label.setStyleSheet("color: #a0a0a0;")
        combo_header.addWidget(self._item_info_label)

        combo_header.addStretch()
        layout.addLayout(combo_header)

        # Item details
        self._details_label = QLabel()
        theme = ThemeManager.instance().current_theme
        self._details_label.setStyleSheet(f"""
            QLabel {{
                background-color: {theme.background_hover};
                border-radius: 6px;
                padding: 12px;
                color: {theme.text};
            }}
        """)
        layout.addWidget(self._details_label)

        # Add common UI components
        self._add_common_ui_components(layout)

        self.setLayout(layout)

    def _add_common_ui_components(self, layout):
        """Add common UI components (results list, preview, buttons)."""
        # Main content area with splitter
        splitter = QSplitter(Qt.Horizontal)

        # Left: Search results
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

        self._search_btn = QPushButton(t("search"))
        self._search_btn.setCursor(Qt.PointingHandCursor)
        self._search_btn.clicked.connect(self._search_covers)
        left_layout.addWidget(self._search_btn)

        splitter.addWidget(left_widget)

        # Right: Cover preview
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        cover_title = QLabel(t("album_art") + ":")
        cover_title.setStyleSheet("font-weight: bold;")
        right_layout.addWidget(cover_title)

        self._cover_label = QLabel()
        self._cover_label.setMinimumSize(400, 400)
        self._cover_label.setAlignment(Qt.AlignCenter)
        theme = ThemeManager.instance().current_theme
        self._cover_label.setStyleSheet(f"""
            QLabel {{
                border: 2px solid {theme.border};
                border-radius: 8px;
                background-color: {theme.background};
            }}
        """)
        self._cover_label.setText(t("searching"))

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

        self._score_label = QLabel()
        self._score_label.setAlignment(Qt.AlignCenter)
        theme = ThemeManager.instance().current_theme
        self._score_label.setStyleSheet(f"color: {theme.highlight}; font-weight: bold;")
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
        theme = ThemeManager.instance().current_theme
        self._status_label.setStyleSheet(f"color: {theme.text_secondary};")
        layout.addWidget(self._status_label)

        # Buttons
        button_layout = QHBoxLayout()

        self._save_btn = QPushButton(t("save"))
        self._save_btn.setCursor(Qt.PointingHandCursor)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save_cover)
        button_layout.addWidget(self._save_btn)

        close_btn = QPushButton(t("cancel"))
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _load_items(self):
        """Load items into UI."""
        if len(self._items) <= 1:
            # Single item - auto search
            self._search_covers()
            return

        # Multi-item - populate combo
        self._combo.clear()
        for item in self._items:
            self._combo.addItem(self._strategy.get_display_text(item))

        self._combo.setCurrentIndex(0)
        self._on_item_changed(0)

    def _on_item_changed(self, index: int):
        """Handle item selection change."""
        if index < 0 or index >= len(self._items):
            return

        self._current_index = index
        item = self._items[index]

        # Update info label
        total = len(self._items)
        self._item_info_label.setText(f"{index + 1} / {total}")

        # Update details label
        details = self._build_details_text(item)
        self._details_label.setText(details)

        # Reset state
        self._current_cover_data = None
        self._current_cover_url = None
        self._search_results = []
        self._results_list.clear()
        self._save_btn.setEnabled(False)
        self._score_label.setText("")

        # Display existing cover
        self._display_existing_cover(item)

        # Auto search
        self._search_covers()

    def _build_details_text(self, item) -> str:
        """Build details text for item."""
        # Get display text from strategy
        display_text = self._strategy.get_display_text(item)

        # Get additional info
        info = self._strategy.get_search_info(item)

        details = f"<b>{t('title')}</b>: {item.title if hasattr(item, 'title') else item.name}"
        if hasattr(item, 'artist') and item.artist:
            details += f"<br><b>{t('artist')}</b>: {item.artist}"
        if hasattr(item, 'album') and item.album:
            details += f"<br><b>{t('album')}</b>: {item.album}"
        if 'duration' in info:
            duration = info['duration']
            minutes = int(duration // 60)
            secs = int(duration % 60)
            details += f"<br><b>{t('duration')}</b>: {minutes}:{secs:02d}"
        if 'album_count' in info:
            details += f"<br><b>{t('albums')}</b>: {info['album_count']}"

        return details

    def _display_existing_cover(self, item):
        """Display existing cover if available."""
        cover_path = getattr(item, 'cover_path', None)
        if cover_path:
            try:
                pixmap = QPixmap(cover_path)
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

        self._cover_label.setText(t("searching"))
        self._status_label.setText("")

    def _search_covers(self):
        """Search for covers for current item."""
        if self._search_thread and self._search_thread.isRunning():
            logger.debug("Search already in progress")
            return

        item = self._items[self._current_index]

        self._search_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)
        self._status_label.setText(t("searching"))
        self._results_list.clear()
        self._search_results = []

        def task():
            return self._strategy.search(self._cover_service, item)

        self._controller.search(
            task,
            on_complete=self._on_search_completed,
            on_error=self._on_search_failed
        )

    def _on_search_completed(self, results: list):
        """Handle search completion."""
        self._progress.setVisible(False)
        self._search_btn.setEnabled(True)

        if not results:
            self._status_label.setText(t("no_results"))
            return

        self._search_results = results

        for result in results:
            display = self._strategy.format_result(result)
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, result)
            self._results_list.addItem(item)

        if self._results_list.count() > 0:
            self._results_list.setCurrentRow(0)

        self._status_label.setText(f"{t('found')} {len(results)} {t('results')}")

    def _on_search_failed(self, error_message: str):
        """Handle search failure."""
        self._progress.setVisible(False)
        self._search_btn.setEnabled(True)
        self._status_label.setText(error_message)
        self._cover_label.setText(t("no_results"))

    def _on_current_item_changed(self, current: QListWidgetItem, previous: QListWidgetItem):
        """Handle current item change in results list."""
        if current:
            self._on_result_selected(current)

    def _on_result_selected(self, item: QListWidgetItem):
        """Handle result selection."""
        result = item.data(Qt.UserRole)
        score = result.get('score', 0)
        self._score_label.setText(f"{t('match_score')}: {score:.0f}%")

        # Check if needs lazy fetch
        if self._strategy.needs_lazy_fetch(result):
            logger.info("Performing lazy fetch for QQ Music cover")
            self._current_result = result
            self._progress.setVisible(True)
            self._status_label.setText(t("downloading"))

            def task():
                return self._strategy.lazy_fetch(self._cover_service, result)

            self._controller.download_from_data(
                task,
                on_complete=self._on_download_completed,
                on_error=self._on_download_failed
            )
            return

        # Normal download
        cover_url = self._strategy.get_cover_url(result)
        if not cover_url:
            self._status_label.setText(t("cover_load_failed"))
            return

        self._progress.setVisible(True)
        self._status_label.setText(t("downloading"))

        source = result.get('source', '')
        self._controller.download(
            cover_url,
            on_complete=self._on_download_completed,
            on_error=self._on_download_failed,
            source=source
        )

    def _on_download_completed(self, cover_data: bytes, source: str):
        """Handle download completion."""
        self._progress.setVisible(False)
        self._current_cover_data = cover_data

        # Display cover
        circular = self._strategy.use_circular_display()
        self._display_cover(cover_data, circular)

        self._save_btn.setEnabled(True)
        self._status_label.setText(f"{t('success')} ({source})")

    def _on_download_failed(self, error_message: str):
        """Handle download failure."""
        self._progress.setVisible(False)
        self._status_label.setText(error_message)
        self._cover_label.setText(t("cover_load_failed"))

    def _display_cover(self, cover_data: bytes, circular: bool = False):
        """Display cover from data."""
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

    def _save_cover(self):
        """Save cover using strategy."""
        if not self._current_cover_data:
            return

        item = self._items[self._current_index]

        # Save to cache
        artist = getattr(item, 'artist', '')
        title = getattr(item, 'title', '')
        album = getattr(item, 'name', '')  # Album or artist name

        cover_path = self._cover_service.save_cover_data_to_cache(
            self._current_cover_data,
            artist,
            title,
            album
        )

        if not cover_path:
            MessageDialog.warning(self, t("error"), t("cover_save_failed"))
            return

        # Use strategy to save
        if self._strategy.save(item, self._current_cover_data, cover_path):
            self.accept()
        else:
            MessageDialog.warning(self, t("error"), t("cover_save_failed"))

    def closeEvent(self, event):
        """Cleanup on close."""
        self._controller.cancel_all()
        super().closeEvent(event)

    def reject(self):
        """Handle dialog rejection."""
        self._controller.cancel_all()
        super().reject()
