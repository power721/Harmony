"""
Album card widget for displaying album information in a grid.
"""

import logging
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QRect, QTimer
from PySide6.QtGui import QPixmap, QColor, QPainter, QFont, QAction
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QFrame,
    QMenu,
)

from domain.album import Album
from system.i18n import t
from ui.widgets.cover_loader import CoverLoader
from ui.widgets.hover_effect_mixin import HoverEffectMixin

logger = logging.getLogger(__name__)


class AlbumCard(HoverEffectMixin, QWidget):
    """
    Card widget for displaying album information.

    Features:
        - Album cover with hover effect
        - Album name and artist
        - Click signal for navigation
        - Right-click context menu for cover download
        - Lazy cover loading for performance (local + online URLs)
    """

    clicked = Signal(object)  # Emits Album object
    download_cover_requested = Signal(object)  # Emits Album object

    _STYLE_TEMPLATE = """
        QMenu {
            background-color: %background_hover%;
            color: %text%;
            border: 1px solid %border%;
            border-radius: 6px;
            padding: 4px;
        }
        QMenu::item {
            padding: 8px 24px;
            border-radius: 4px;
        }
        QMenu::item:selected {
            background-color: %highlight%;
            color: %background%;
        }
    """

    # Card size constants
    COVER_SIZE = 180
    CARD_WIDTH = 180
    CARD_HEIGHT = 240
    BORDER_RADIUS = 8

    def __init__(self, album: Album, parent=None):
        super().__init__(parent)
        self._album = album
        self._is_hovering = False
        self._cover_loaded = False
        self._downloading = False

        self._setup_ui()
        # Set default cover immediately, load actual cover lazily
        self._set_default_cover()
        QTimer.singleShot(10, self._load_cover)

    def _setup_ui(self):
        """Set up the card UI."""
        from system.theme import ThemeManager

        self.setFixedSize(self.CARD_WIDTH, self.CARD_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Cover container
        self._cover_container = QFrame()
        self._cover_container.setFixedSize(self.COVER_SIZE, self.COVER_SIZE)

        # Pre-computed stylesheets for hover (H-08 optimization)
        theme = ThemeManager.instance().current_theme
        radius = self.BORDER_RADIUS
        self._set_hover_target(self._cover_container)
        self._style_normal, self._style_hover = self._build_hover_styles(theme, radius)
        self._apply_hover_style()

        # Cover label
        self._cover_label = QLabel(self._cover_container)
        self._cover_label.setFixedSize(self.COVER_SIZE, self.COVER_SIZE)
        self._cover_label.setAlignment(Qt.AlignCenter)
        self._cover_label.setStyleSheet(f"""
            QLabel {{
                border-radius: {self.BORDER_RADIUS}px;
            }}
        """)

        # Info container
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(4, 0, 4, 0)
        info_layout.setSpacing(2)

        # Album name
        self._name_label = QLabel(self._album.display_name)
        self._name_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._name_label.setStyleSheet(ThemeManager.instance().get_qss("""
            QLabel {
                color: %text%;
                font-size: 13px;
                font-weight: bold;
                background: transparent;
            }
        """))
        self._name_label.setWordWrap(True)
        self._name_label.setMaximumHeight(36)

        # Artist name
        self._artist_label = QLabel(self._album.display_artist)
        self._artist_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._artist_label.setStyleSheet(ThemeManager.instance().get_qss("""
            QLabel {
                color: %text_secondary%;
                font-size: 12px;
                background: transparent;
            }
        """))

        info_layout.addWidget(self._name_label)
        info_layout.addWidget(self._artist_label)

        layout.addWidget(self._cover_container, 0, Qt.AlignHCenter)
        layout.addWidget(info_widget)
        layout.addStretch()

    def _show_context_menu(self, pos):
        """Show context menu."""
        from system.theme import ThemeManager

        menu = QMenu(self)
        menu.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TEMPLATE))

        # Download cover action
        download_action = QAction(t("download_cover_manual"), self)
        download_action.triggered.connect(lambda: self.download_cover_requested.emit(self._album))
        menu.addAction(download_action)

        # Play album action
        play_action = QAction(t("view_details"), self)
        play_action.triggered.connect(lambda: self.clicked.emit(self._album))
        menu.addAction(play_action)

        menu.exec_(self.mapToGlobal(pos))

    def _load_cover(self, force: bool = False):
        """Load album cover image lazily. Supports local files and online URLs.

        Args:
            force: If True, reload even if already loaded
        """
        if self._cover_loaded and not force:
            return

        cover_path = self._album.cover_path
        if not cover_path:
            return

        # Online URL
        if cover_path.startswith(('http://', 'https://')):
            from infrastructure.cache import ImageCache
            cached_data = ImageCache.get(cover_path)
            if cached_data:
                pixmap = CoverLoader.pixmap_from_bytes(cached_data, self.COVER_SIZE, self.COVER_SIZE)
                if pixmap is not None:
                    self._cover_label.setPixmap(pixmap)
                    self._cover_loaded = True
                    return

            # Download async
            if not self._downloading:
                self._downloading = True
                self._download_cover_async(cover_path)
            return

        # Local file
        if Path(cover_path).exists():
            try:
                pixmap = CoverLoader.load_scaled_pixmap(cover_path, self.COVER_SIZE, self.COVER_SIZE)
                if pixmap is not None:
                    self._cover_label.setPixmap(pixmap)
                    self._cover_loaded = True
                    return
            except Exception as e:
                logger.debug(f"Error loading cover: {e}")

    def _download_cover_async(self, url: str):
        """Download cover image asynchronously with disk caching."""
        from infrastructure.cache import ImageCache
        from infrastructure.network import HttpClient

        try:
            http_client = HttpClient()

            def download():
                try:
                    return http_client.get_content(url, timeout=5)
                except Exception as e:
                    logger.warning(f"Failed to download cover: {e}")
                    return None

            future = CoverLoader.get_download_executor().submit(download)

            def check_download():
                if future.done():
                    image_data = future.result()
                    if image_data:
                        ImageCache.set(url, image_data)
                        pixmap = CoverLoader.pixmap_from_bytes(
                            image_data, self.COVER_SIZE, self.COVER_SIZE
                        )
                        if pixmap is not None:
                            self._cover_label.setPixmap(pixmap)
                            self._cover_loaded = True
                    self._downloading = False
                else:
                    QTimer.singleShot(100, check_download)

            QTimer.singleShot(100, check_download)
        except Exception as e:
            logger.warning(f"Failed to start cover download: {e}")
            self._downloading = False

    def _set_default_cover(self):
        """Set default cover when no cover is available."""
        pixmap = QPixmap(self.COVER_SIZE, self.COVER_SIZE)
        pixmap.fill(QColor("#3d3d3d"))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw music note icon
        painter.setPen(QColor("#666666"))
        font = QFont()
        font.setPixelSize(60)
        painter.setFont(font)
        painter.drawText(
            QRect(0, 0, self.COVER_SIZE, self.COVER_SIZE),
            Qt.AlignCenter, "\u266B"  # Music note
        )
        painter.end()

        self._cover_label.setPixmap(pixmap)

    def mousePressEvent(self, event):
        """Handle mouse click."""
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._album)
        super().mousePressEvent(event)

    def get_album(self) -> Album:
        """Get the album object."""
        return self._album

    def update_cover(self, cover_path: str):
        """Update cover after download."""
        self._album.cover_path = cover_path
        self._load_cover(force=True)

    def refresh_theme(self):
        """Refresh theme colors when theme changes."""
        from system.theme import ThemeManager

        theme = ThemeManager.instance().current_theme
        radius = self.BORDER_RADIUS

        # Update pre-computed stylesheets
        self._style_normal, self._style_hover = self._build_hover_styles(theme, radius)
        self._apply_hover_style()

        # Update text labels
        self._name_label.setStyleSheet(ThemeManager.instance().get_qss("""
            QLabel {
                color: %text%;
                font-size: 13px;
                font-weight: bold;
                background: transparent;
            }
        """))
        self._artist_label.setStyleSheet(ThemeManager.instance().get_qss("""
            QLabel {
                color: %text_secondary%;
                font-size: 12px;
                background: transparent;
            }
        """))
