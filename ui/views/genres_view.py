"""
Genres view widget for browsing genres in a grid layout.
Uses QListView + Model/Delegate for high-performance rendering.
"""

import logging
from collections import OrderedDict
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import (
    Qt, Signal, QTimer, QThread,
    QAbstractListModel, QModelIndex, QSize, QRect
)
from PySide6.QtGui import QPixmap, QColor, QPainter, QFont, QPen, QAction
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListView,
    QFrame,
    QLineEdit,
    QProgressBar,
    QStyledItemDelegate,
    QStyle,
    QMenu,
)
from shiboken6 import isValid

from domain.genre import Genre
from services.library import LibraryService
from services.metadata import CoverService
from system.event_bus import EventBus
from system.i18n import t

logger = logging.getLogger(__name__)


class LoadGenresWorker(QThread):
    """Background worker to load genres."""
    finished = Signal(list)

    def __init__(self, library_service: LibraryService, parent=None):
        super().__init__(parent)
        self._library = library_service

    def run(self):
        genres = self._library.get_genres()
        self.finished.emit(genres)


class FillGenreCoversWorker(QThread):
    """Background worker to fill missing genre covers."""
    finished = Signal(int)

    def __init__(self, library_service: LibraryService, parent=None):
        super().__init__(parent)
        self._library = library_service

    def run(self):
        try:
            filled = self._library.fill_missing_genre_covers()
        except Exception:
            filled = 0
        self.finished.emit(filled)


class GenreModel(QAbstractListModel):
    """Model for genre data."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._genres: List[Genre] = []

    def rowCount(self, parent=QModelIndex()):
        return len(self._genres)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._genres):
            return None

        genre = self._genres[index.row()]

        if role == Qt.DisplayRole:
            return genre.name
        elif role == Qt.UserRole:
            return genre

        return None

    def set_genres(self, genres: List[Genre]):
        self.beginResetModel()
        self._genres = genres
        self.endResetModel()

    def get_genre(self, row: int) -> Optional[Genre]:
        if 0 <= row < len(self._genres):
            return self._genres[row]
        return None


class GenreDelegate(QStyledItemDelegate):
    """Delegate for rendering genre cards."""

    # Card size constants
    COVER_SIZE = 180
    CARD_WIDTH = 180
    CARD_HEIGHT = 240
    BORDER_RADIUS = 4
    SPACING = 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cover_cache = OrderedDict()  # LRU cache for loaded covers
        self._cache_max_size = 500
        self._pending_downloads = set()  # Track URLs being downloaded
        self._executor = None  # ThreadPoolExecutor for async downloads
        self._default_cover = self._create_default_cover()

    def _create_default_cover(self) -> QPixmap:
        """Create default cover pixmap."""
        from system.theme import ThemeManager

        theme = ThemeManager.instance().current_theme

        pixmap = QPixmap(self.COVER_SIZE, self.COVER_SIZE)
        pixmap.fill(QColor(theme.text_secondary))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QColor(theme.text))
        font = QFont()
        font.setPixelSize(60)
        painter.setFont(font)
        painter.drawText(
            QRect(0, 0, self.COVER_SIZE, self.COVER_SIZE),
            Qt.AlignCenter, "\u266B"
        )
        painter.end()
        return pixmap

    def _load_cover(self, cover_path: str) -> QPixmap:
        """Load cover from path with LRU caching. Supports local files and online URLs."""
        if not cover_path:
            return self._default_cover

        if cover_path in self._cover_cache:
            self._cover_cache.move_to_end(cover_path)
            return self._cover_cache[cover_path]

        # Online URL
        if cover_path.startswith(('http://', 'https://')):
            from infrastructure.cache import ImageCache
            cached_data = ImageCache.get(cover_path)
            if cached_data:
                pixmap = QPixmap()
                if pixmap.loadFromData(cached_data):
                    scaled = pixmap.scaled(
                        self.COVER_SIZE, self.COVER_SIZE,
                        Qt.KeepAspectRatioByExpanding,
                        Qt.SmoothTransformation
                    )
                    self._cover_cache[cover_path] = scaled
                    if len(self._cover_cache) > self._cache_max_size:
                        self._cover_cache.popitem(last=False)
                    return scaled

            # Start async download
            if cover_path not in self._pending_downloads:
                self._pending_downloads.add(cover_path)
                self._download_cover_async(cover_path)
            return self._default_cover

        if Path(cover_path).exists():
            try:
                pixmap = QPixmap(cover_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        self.COVER_SIZE, self.COVER_SIZE,
                        Qt.KeepAspectRatioByExpanding,
                        Qt.SmoothTransformation
                    )
                    self._cover_cache[cover_path] = scaled
                    if len(self._cover_cache) > self._cache_max_size:
                        self._cover_cache.popitem(last=False)
                    return scaled
            except Exception:
                pass

        return self._default_cover

    def _download_cover_async(self, url: str):
        """Download cover image asynchronously with disk caching."""
        from concurrent.futures import ThreadPoolExecutor
        from infrastructure.cache import ImageCache
        from infrastructure.network import HttpClient

        try:
            http_client = HttpClient()

            request_url, request_headers = self._prepare_cover_request(url)

            def download():
                try:
                    return http_client.get_content(
                        request_url,
                        headers=request_headers,
                        timeout=5
                    )
                except Exception as e:
                    logger.warning(f"Failed to download cover: {e}")
                    return None

            if self._executor is None:
                self._executor = ThreadPoolExecutor(max_workers=1)

            future = self._executor.submit(download)

            def check_download():
                if future.done():
                    image_data = future.result()
                    if image_data:
                        ImageCache.set(url, image_data)
                        pixmap = QPixmap()
                        if pixmap.loadFromData(image_data):
                            scaled = pixmap.scaled(
                                self.COVER_SIZE, self.COVER_SIZE,
                                Qt.KeepAspectRatioByExpanding,
                                Qt.SmoothTransformation
                            )
                            self._cover_cache[url] = scaled
                            if len(self._cover_cache) > self._cache_max_size:
                                self._cover_cache.popitem(last=False)
                            parent = self.parent()
                            if parent and hasattr(parent, 'viewport'):
                                parent.viewport().update()
                    self._pending_downloads.discard(url)
                else:
                    QTimer.singleShot(100, check_download)

            QTimer.singleShot(100, check_download)
        except Exception as e:
            logger.warning(f"Failed to start cover download: {e}")
            self._pending_downloads.discard(url)

    def _prepare_cover_request(self, url: str) -> tuple[str, dict | None]:
        """Prepare request URL/headers for cover hosts with special requirements."""
        request_url = url
        request_headers = None

        # Legacy QQ URLs in database should use y.gtimg.cn for stable image access.
        if url.startswith("https://y.qq.com/music/photo_new/"):
            request_url = url.replace("https://y.qq.com/music/photo_new/", "https://y.gtimg.cn/music/photo_new/", 1)
            request_headers = {"Referer": "https://y.qq.com/"}
        elif url.startswith("http://y.qq.com/music/photo_new/"):
            request_url = url.replace("http://y.qq.com/music/photo_new/", "https://y.gtimg.cn/music/photo_new/", 1)
            request_headers = {"Referer": "https://y.qq.com/"}
        elif "y.gtimg.cn" in url:
            request_headers = {"Referer": "https://y.qq.com/"}

        return request_url, request_headers

    def sizeHint(self, option, index):
        return QSize(self.CARD_WIDTH, self.CARD_HEIGHT)

    def paint(self, painter, option, index):
        genre = index.data(Qt.UserRole)
        if not genre:
            return

        from system.theme import ThemeManager
        theme = ThemeManager.instance().current_theme

        rect = option.rect
        is_hovered = option.state & QStyle.State_MouseOver

        # Draw cover
        cover = self._load_cover(genre.cover_path)
        cover_rect = QRect(
            rect.x() + (rect.width() - self.COVER_SIZE) // 2,
            rect.y(),
            self.COVER_SIZE,
            self.COVER_SIZE
        )

        # Draw highlight background on hover
        if is_hovered:
            bg_rect = QRect(
                cover_rect.x() - 4,
                cover_rect.y() - 4,
                self.COVER_SIZE + 8,
                self.CARD_HEIGHT - 40
            )
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(Qt.NoPen)
            hover_bg = QColor(theme.background_hover)
            hover_bg.setAlpha(200)
            painter.setBrush(hover_bg)
            painter.drawRoundedRect(bg_rect, 12, 12)

            # Draw border
            painter.setPen(QPen(QColor(theme.highlight), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(cover_rect, self.BORDER_RADIUS, self.BORDER_RADIUS)

        painter.drawPixmap(cover_rect, cover)

        # Draw genre name
        painter.setPen(QColor(theme.text))
        font = QFont()
        font.setPixelSize(13)
        font.setBold(True)
        painter.setFont(font)

        name_rect = QRect(
            rect.x() + 4,
            rect.y() + self.COVER_SIZE + 8,
            rect.width() - 8,
            36
        )
        painter.drawText(name_rect, Qt.AlignLeft | Qt.TextWordWrap, genre.display_name)

        # Draw song count and album count as stats
        painter.setPen(QColor(theme.text_secondary))
        font.setBold(False)
        font.setPixelSize(12)
        painter.setFont(font)

        stats_text = t("genre_stats").format(
            songs=genre.song_count,
            albums=genre.album_count
        )
        stats_rect = QRect(
            rect.x() + 4,
            rect.y() + self.COVER_SIZE + 44,
            rect.width() - 8,
            20
        )
        painter.drawText(stats_rect, Qt.AlignLeft, stats_text)

    def clear_cache(self):
        """Clear cover cache."""
        self._cover_cache.clear()

    def refresh_theme(self):
        """Refresh default cover when theme changes."""
        self._default_cover = self._create_default_cover()


class GenresView(QWidget):
    """
    Genres page displaying a scrollable grid of genre cards.
    Uses QListView with custom delegate for high performance.
    """

    genre_clicked = Signal(object)  # Emits Genre object
    play_genre = Signal(list)  # Emits list of Track objects
    rename_genre_requested = Signal(object)  # Emits Genre object
    download_cover_requested = Signal(object)  # Emits Genre object

    MARGIN = 20

    def __init__(
            self,
            library_service: LibraryService,
            cover_service: CoverService = None,
            parent=None
    ):
        super().__init__(parent)
        self._library = library_service
        self._cover_service = cover_service
        self._genres: List[Genre] = []
        self._filtered_genres: List[Genre] = []
        self._data_loaded = False
        self._load_worker = None
        self._fill_worker = None
        self._is_filling_covers = False
        self._hovered_index = -1

        self._setup_ui()
        self._connect_signals()

        # Register with theme manager
        from system.theme import ThemeManager
        ThemeManager.instance().register_widget(self)

    def showEvent(self, event):
        """Load data when view is first shown."""
        super().showEvent(event)
        if not self._data_loaded:
            self._load_genres()

    def _setup_ui(self):
        """Set up the genres view UI."""
        from system.theme import ThemeManager
        theme = ThemeManager.instance().current_theme

        self.setStyleSheet(f"background-color: {theme.background};")
        self.setMouseTracking(True)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = self._create_header()
        layout.addWidget(header)

        # List view
        self._list_view = QListView()
        self._list_view.setViewMode(QListView.IconMode)
        self._list_view.setResizeMode(QListView.Adjust)
        self._list_view.setMovement(QListView.Static)
        self._list_view.setSelectionMode(QListView.SingleSelection)
        self._list_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list_view.setVerticalScrollMode(QListView.ScrollPerPixel)
        self._list_view.setMouseTracking(True)
        self._list_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self._list_view.customContextMenuRequested.connect(self._show_context_menu)
        self._list_view.setStyleSheet(f"""
            QListView {{
                background-color: {theme.background};
                border: none;
            }}
            QListView::item {{
                background: transparent;
            }}
            QScrollBar:vertical {{
                background-color: {theme.background};
                width: 12px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {theme.background_alt};
                border-radius: 6px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {theme.background_hover};
            }}
        """)

        # Model and delegate
        self._model = GenreModel(self)
        self._delegate = GenreDelegate(self)
        self._list_view.setModel(self._model)
        self._list_view.setItemDelegate(self._delegate)

        # Set grid size
        self._list_view.setGridSize(QSize(
            GenreDelegate.CARD_WIDTH + GenreDelegate.SPACING,
            GenreDelegate.CARD_HEIGHT + GenreDelegate.SPACING
        ))

        layout.addWidget(self._list_view)

        # Loading indicator
        self._loading = self._create_loading_indicator()
        layout.addWidget(self._loading)
        self._loading.hide()

    def _create_header(self) -> QWidget:
        """Create the header with title and search."""
        from system.theme import ThemeManager
        theme = ThemeManager.instance().current_theme

        header = QFrame()
        header.setFixedHeight(80)
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {theme.background};
                border-bottom: 1px solid {theme.border};
            }}
        """)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 10, 20, 10)

        # Title
        self._title_label = QLabel(t("genres"))
        self._title_label.setStyleSheet(f"""
            QLabel {{
                color: {theme.highlight};
                font-size: 28px;
                font-weight: bold;
                padding: 10px;
            }}
        """)
        layout.addWidget(self._title_label)

        # Genre count
        self._count_label = QLabel("")
        self._count_label.setStyleSheet(f"""
            QLabel {{
                color: {theme.text_secondary};
                font-size: 14px;
            }}
        """)
        layout.addWidget(self._count_label)
        layout.addStretch()

        # Search box
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(t("search"))
        self._search_input.setFixedWidth(300)
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {theme.background_hover};
                color: {theme.text};
                border: 2px solid {theme.border};
                border-radius: 20px;
                padding: 10px 15px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border: 2px solid {theme.highlight};
                background-color: {theme.background_hover};
            }}
            QLineEdit::placeholder {{
                color: {theme.text_secondary};
            }}
            QLineEdit::clear-button {{
                subcontrol-origin: padding;
                subcontrol-position: right;
                width: 18px;
                height: 18px;
                margin-right: 8px;
                border-radius: 9px;
                background-color: {theme.border};
            }}
            QLineEdit::clear-button:hover {{
                background-color: {theme.background_hover};
                border: 1px solid {theme.border};
            }}
            QLineEdit::clear-button:pressed {{
                background-color: {theme.background_alt};
            }}
        """)
        layout.addWidget(self._search_input)

        return header

    def _create_loading_indicator(self) -> QWidget:
        """Create loading indicator."""
        from system.theme import ThemeManager
        theme = ThemeManager.instance().current_theme

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignCenter)

        progress = QProgressBar()
        progress.setRange(0, 0)  # Indeterminate
        progress.setFixedSize(200, 4)
        progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: {theme.background_hover};
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {theme.highlight};
                border-radius: 2px;
            }}
        """)
        layout.addWidget(progress)

        self._loading_label = QLabel(t("loading"))
        self._loading_label.setStyleSheet(f"color: {theme.text_secondary}; font-size: 14px;")
        layout.addWidget(self._loading_label)

        return widget

    def _connect_signals(self):
        """Connect signals."""
        self._search_input.textChanged.connect(self._on_search_text_changed)
        self._list_view.clicked.connect(self._on_genre_clicked)
        self._list_view.doubleClicked.connect(self._on_genre_double_clicked)
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._on_search_changed)
        self._list_view.entered.connect(self._on_item_entered)
        EventBus.instance().tracks_added.connect(self._on_tracks_added)

    @staticmethod
    def _disconnect_signal(signal, slot):
        """Best-effort signal disconnection for shutdown cleanup."""
        try:
            signal.disconnect(slot)
        except (RuntimeError, TypeError):
            pass

    def closeEvent(self, event):
        """Release event bus subscriptions and background work on close."""
        self._disconnect_signal(EventBus.instance().tracks_added, self._on_tracks_added)
        if hasattr(self, "_search_timer"):
            self._search_timer.stop()
        self._stop_load_worker(wait_ms=1000, clear_ref=True)
        super().closeEvent(event)

    def refresh_theme(self):
        """Refresh theme colors when theme changes."""
        from system.theme import ThemeManager
        theme = ThemeManager.instance().current_theme

        # Update main background
        self.setStyleSheet(f"background-color: {theme.background};")

        # Update list view
        if hasattr(self, '_list_view'):
            self._list_view.setStyleSheet(f"""
                QListView {{
                    background-color: {theme.background};
                    border: none;
                }}
                QListView::item {{
                    background: transparent;
                }}
                QScrollBar:vertical {{
                    background-color: {theme.background};
                    width: 12px;
                }}
                QScrollBar::handle:vertical {{
                    background-color: {theme.background_alt};
                    border-radius: 6px;
                    min-height: 30px;
                }}
                QScrollBar::handle:vertical:hover {{
                    background-color: {theme.background_hover};
                }}
            """)

        # Update header (find it in children)
        header = self.findChild(QFrame)
        if header:
            header.setStyleSheet(f"""
                QFrame {{
                    background-color: {theme.background};
                    border-bottom: 1px solid {theme.border};
                }}
            """)

        # Update title label
        if hasattr(self, '_title_label'):
            self._title_label.setStyleSheet(f"""
                QLabel {{
                    color: {theme.highlight};
                    font-size: 28px;
                    font-weight: bold;
                    padding: 10px;
                }}
            """)

        # Update count label
        if hasattr(self, '_count_label'):
            self._count_label.setStyleSheet(f"""
                QLabel {{
                    color: {theme.text_secondary};
                    font-size: 14px;
                }}
            """)

        # Update search input
        if hasattr(self, '_search_input'):
            self._search_input.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {theme.background_hover};
                    color: {theme.text};
                    border: 2px solid {theme.border};
                    border-radius: 20px;
                    padding: 10px 15px;
                    font-size: 14px;
                }}
                QLineEdit:focus {{
                    border: 2px solid {theme.highlight};
                    background-color: {theme.background_hover};
                }}
                QLineEdit::placeholder {{
                    color: {theme.text_secondary};
                }}
                QLineEdit::clear-button {{
                    subcontrol-origin: padding;
                    subcontrol-position: right;
                    width: 18px;
                    height: 18px;
                    margin-right: 8px;
                    border-radius: 9px;
                    background-color: {theme.border};
                }}
                QLineEdit::clear-button:hover {{
                    background-color: {theme.background_hover};
                    border: 1px solid {theme.border};
                }}
                QLineEdit::clear-button:pressed {{
                    background-color: {theme.background_alt};
                }}
            """)

        # Update loading label
        if hasattr(self, '_loading_label'):
            self._loading_label.setStyleSheet(f"color: {theme.text_secondary}; font-size: 14px;")

        # Refresh delegate's default cover
        self._delegate.refresh_theme()

    def _on_item_entered(self, index):
        """Handle item entered for hover effect."""
        self._hovered_index = index.row()
        self._list_view.viewport().setCursor(Qt.PointingHandCursor)

    def _show_context_menu(self, pos):
        """Show context menu for genre."""
        index = self._list_view.indexAt(pos)
        if not index.isValid():
            return

        genre = index.data(Qt.UserRole)
        if not genre:
            return

        from system.theme import ThemeManager
        theme = ThemeManager.instance().current_theme

        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {theme.background_hover};
                color: {theme.text};
                border: 1px solid {theme.border};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 8px 24px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {theme.highlight};
                color: {theme.background};
            }}
        """)

        # View details action
        view_action = QAction(t("view_details"), self)
        view_action.triggered.connect(lambda: self.genre_clicked.emit(genre))
        menu.addAction(view_action)

        # Play genre action
        play_action = QAction(t("play"), self)
        play_action.triggered.connect(lambda: self._play_genre_tracks(genre))
        menu.addAction(play_action)

        # Rename action
        rename_action = QAction(t("rename"), self)
        rename_action.triggered.connect(lambda: self.rename_genre_requested.emit(genre))
        menu.addAction(rename_action)

        menu.addSeparator()

        # Download cover action
        download_action = QAction(t("download_cover_manual"), self)
        download_action.triggered.connect(lambda: self.download_cover_requested.emit(genre))
        menu.addAction(download_action)

        menu.exec_(self._list_view.mapToGlobal(pos))

    def _play_genre_tracks(self, genre: Genre):
        """Load tracks for a genre and emit play_genre signal."""
        tracks = self._library.get_genre_tracks(genre.name)
        if tracks:
            self.play_genre.emit(tracks)

    def _load_genres(self, force: bool = False):
        """Load genres from library in background thread.

        Args:
            force: If True, reload even if data is already loaded
        """
        if self._data_loaded and not force:
            return

        if force:
            self._do_load_genres()
        else:
            self._loading.show()
            self._list_view.hide()
            self._do_load_genres()

    def _do_load_genres(self):
        """Actually load genres in background."""
        self._stop_load_worker(wait_ms=1000, clear_ref=True)

        self._load_worker = LoadGenresWorker(self._library)
        self._load_worker.finished.connect(self._on_genres_loaded)
        self._load_worker.start()

    def _on_genres_loaded(self, genres: List[Genre]):
        """Handle genres loaded from background thread."""
        self._genres = genres
        self._filtered_genres = genres.copy()
        self._data_loaded = True

        self._update_count_label()
        self._model.set_genres(self._filtered_genres)

        self._loading.hide()
        self._list_view.show()

        self._stop_load_worker(wait_ms=1000, clear_ref=True)

        # self._fill_missing_covers_async()

    def _stop_load_worker(self, wait_ms: int = 1000, clear_ref: bool = False):
        """Stop and cleanup the background load worker cooperatively."""
        worker = self._load_worker
        if worker and isValid(worker):
            if worker.isRunning():
                worker.requestInterruption()
                worker.quit()
                if not worker.wait(wait_ms):
                    logger.warning(
                        "[GenresView] Load worker did not stop in time via cooperative shutdown"
                    )
            worker.deleteLater()
        if clear_ref:
            self._load_worker = None

    def _fill_missing_covers_async(self):
        """Fill missing genre covers in background and refresh when done."""
        if not self._cover_service or self._is_filling_covers:
            return

        if not any(not g.cover_path for g in self._genres):
            return

        self._is_filling_covers = True

        if self._fill_worker and isValid(self._fill_worker):
            if self._fill_worker.isRunning():
                return
            self._fill_worker.deleteLater()
            self._fill_worker = None

        self._fill_worker = FillGenreCoversWorker(self._library, self)
        self._fill_worker.finished.connect(self._on_fill_covers_finished)
        self._fill_worker.start()

    def _on_fill_covers_finished(self, filled_count: int):
        """Handle completion of missing cover fill task."""
        self._is_filling_covers = False

        if self._fill_worker:
            self._fill_worker.deleteLater()
            self._fill_worker = None

        if filled_count > 0:
            self._delegate.clear_cache()
            self._load_genres(force=True)

    def _update_count_label(self):
        """Update the genre count label."""
        total = len(self._genres)
        if self._search_input.text():
            showing = len(self._filtered_genres)
            self._count_label.setText(f"{showing}/{total} {t('genres')}")
        else:
            self._count_label.setText(f"{total} {t('genres')}")

    def _on_search_text_changed(self, text: str):
        """Debounce search - restart timer on each keystroke."""
        self._search_timer.start()

    def _on_search_changed(self, text: str = ""):
        """Handle search text change (debounced)."""
        text = text or self._search_input.text()
        text = text.lower().strip()
        if text:
            self._filtered_genres = [
                g for g in self._genres
                if text in g.name.lower()
            ]
        else:
            self._filtered_genres = self._genres.copy()

        self._update_count_label()
        self._model.set_genres(self._filtered_genres)

    def _on_genre_clicked(self, index: QModelIndex):
        """Handle genre single click."""
        genre = index.data(Qt.UserRole)
        if genre:
            self.genre_clicked.emit(genre)

    def _on_genre_double_clicked(self, index: QModelIndex):
        """Handle genre double click - load tracks and emit play_genre."""
        genre = index.data(Qt.UserRole)
        if genre:
            tracks = self._library.get_genre_tracks(genre.name)
            if tracks:
                self.play_genre.emit(tracks)

    def _on_tracks_added(self, count: int):
        """Handle tracks added to library."""
        self._data_loaded = False
        self._load_genres()

    def refresh(self):
        """Refresh the genres view."""
        self._data_loaded = False
        self._load_genres()

    def refresh_ui(self):
        """Refresh UI texts after language change."""
        # Update title
        self._title_label.setText(t("genres"))

        # Update search placeholder
        self._search_input.setPlaceholderText(t("search"))

        # Update loading indicator label
        self._loading_label.setText(t("loading"))

        # Update count label
        self._update_count_label()

        # Force repaint to update delegate text
        self._list_view.viewport().update()
