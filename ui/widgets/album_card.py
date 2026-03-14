"""
Album card widget for displaying album information in a grid.
"""

import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QFrame,
    QGraphicsDropShadowEffect,
    QMenu,
)
from PySide6.QtCore import Qt, Signal, QSize, QPropertyAnimation, QRect, QEasingCurve, QTimer
from PySide6.QtGui import QPixmap, QColor, QPainter, QFont, QAction

from domain.album import Album

logger = logging.getLogger(__name__)


class AlbumCard(QWidget):
    """
    Card widget for displaying album information.

    Features:
        - Album cover with hover effect
        - Album name and artist
        - Click signal for navigation
        - Right-click context menu for cover download
        - Lazy cover loading for performance
    """

    clicked = Signal(object)  # Emits Album object
    download_cover_requested = Signal(object)  # Emits Album object

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

        self._setup_ui()
        # Set default cover immediately, load actual cover lazily
        self._set_default_cover()
        QTimer.singleShot(10, self._load_cover)

    def _setup_ui(self):
        """Set up the card UI."""
        self.setFixedSize(self.CARD_WIDTH, self.CARD_HEIGHT)
        self.setCursor(Qt.PointingHandCursor)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Cover container
        self._cover_container = QFrame()
        self._cover_container.setFixedSize(self.COVER_SIZE, self.COVER_SIZE)
        self._cover_container.setStyleSheet(f"""
            QFrame {{
                background-color: #2a2a2a;
                border-radius: {self.BORDER_RADIUS}px;
            }}
        """)

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
        self._name_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 13px;
                font-weight: bold;
                background: transparent;
            }
        """)
        self._name_label.setWordWrap(True)
        self._name_label.setMaximumHeight(36)

        # Artist name
        self._artist_label = QLabel(self._album.display_artist)
        self._artist_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._artist_label.setStyleSheet("""
            QLabel {
                color: #b3b3b3;
                font-size: 12px;
                background: transparent;
            }
        """)

        info_layout.addWidget(self._name_label)
        info_layout.addWidget(self._artist_label)

        layout.addWidget(self._cover_container, 0, Qt.AlignHCenter)
        layout.addWidget(info_widget)
        layout.addStretch()

    def _show_context_menu(self, pos):
        """Show context menu."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2a2a2a;
                color: #ffffff;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 24px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #1db954;
                color: #000000;
            }
        """)

        # Download cover action
        download_action = QAction("⬇️ 下载封面", self)
        download_action.triggered.connect(lambda: self.download_cover_requested.emit(self._album))
        menu.addAction(download_action)

        # Play album action
        play_action = QAction("▶️ 播放专辑", self)
        play_action.triggered.connect(lambda: self.clicked.emit(self._album))
        menu.addAction(play_action)

        menu.exec_(self.mapToGlobal(pos))

    def _load_cover(self, force: bool = False):
        """Load album cover image lazily.

        Args:
            force: If True, reload even if already loaded
        """
        if self._cover_loaded and not force:
            return

        cover_path = self._album.cover_path

        if cover_path and Path(cover_path).exists():
            try:
                pixmap = QPixmap(cover_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        self.COVER_SIZE, self.COVER_SIZE,
                        Qt.KeepAspectRatioByExpanding,
                        Qt.SmoothTransformation
                    )
                    self._cover_label.setPixmap(scaled)
                    self._cover_loaded = True
                    return
            except Exception as e:
                logger.debug(f"Error loading cover: {e}")

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

    def enterEvent(self, event):
        """Handle mouse enter for hover effect."""
        self._is_hovering = True
        self._cover_container.setStyleSheet(f"""
            QFrame {{
                background-color: #2a2a2a;
                border-radius: {self.BORDER_RADIUS}px;
                border: 2px solid #1db954;
            }}
        """)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Handle mouse leave for hover effect."""
        self._is_hovering = False
        self._cover_container.setStyleSheet(f"""
            QFrame {{
                background-color: #2a2a2a;
                border-radius: {self.BORDER_RADIUS}px;
            }}
        """)
        super().leaveEvent(event)

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
