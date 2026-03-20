"""
Artist card widget for displaying artist information in a grid.
"""

import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QFrame,
    QMenu,
)
from PySide6.QtCore import Qt, Signal, QRect
from PySide6.QtGui import QPixmap, QColor, QPainter, QFont, QAction

from domain.artist import Artist

logger = logging.getLogger(__name__)


class ArtistCard(QWidget):
    """
    Card widget for displaying artist information.

    Features:
        - Circular artist avatar
        - Artist name and song count
        - Click signal for navigation
        - Right-click context menu for cover download
    """

    clicked = Signal(object)  # Emits Artist object
    download_cover_requested = Signal(object)  # Emits Artist object

    # Card size constants
    AVATAR_SIZE = 160
    CARD_WIDTH = 180
    CARD_HEIGHT = 220
    BORDER_RADIUS = 80  # Circular

    def __init__(self, artist: Artist, parent=None):
        super().__init__(parent)
        self._artist = artist
        self._is_hovering = False

        self._setup_ui()
        self._load_avatar()

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

        # Avatar container
        self._avatar_container = QFrame()
        self._avatar_container.setFixedSize(self.AVATAR_SIZE, self.AVATAR_SIZE)
        self._avatar_container.setStyleSheet(f"""
            QFrame {{
                background-color: #2a2a2a;
                border-radius: {self.BORDER_RADIUS}px;
            }}
        """)

        # Avatar label
        self._avatar_label = QLabel(self._avatar_container)
        self._avatar_label.setFixedSize(self.AVATAR_SIZE, self.AVATAR_SIZE)
        self._avatar_label.setAlignment(Qt.AlignCenter)
        self._avatar_label.setStyleSheet(f"""
            QLabel {{
                border-radius: {self.BORDER_RADIUS}px;
            }}
        """)

        # Info container
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(4, 0, 4, 0)
        info_layout.setSpacing(2)

        # Artist name
        self._name_label = QLabel(self._artist.display_name)
        self._name_label.setAlignment(Qt.AlignCenter)
        self._name_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
                background: transparent;
            }
        """)
        self._name_label.setWordWrap(True)

        # Song count
        song_count_text = f"{self._artist.song_count} songs"
        self._count_label = QLabel(song_count_text)
        self._count_label.setAlignment(Qt.AlignCenter)
        self._count_label.setStyleSheet("""
            QLabel {
                color: #b3b3b3;
                font-size: 12px;
                background: transparent;
            }
        """)

        info_layout.addWidget(self._name_label)
        info_layout.addWidget(self._count_label)

        layout.addWidget(self._avatar_container, 0, Qt.AlignHCenter)
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
        download_action = QAction("下载封面", self)
        download_action.triggered.connect(lambda: self.download_cover_requested.emit(self._artist))
        menu.addAction(download_action)

        # View artist action
        view_action = QAction("查看歌手", self)
        view_action.triggered.connect(lambda: self.clicked.emit(self._artist))
        menu.addAction(view_action)

        menu.exec_(self.mapToGlobal(pos))

    def _load_avatar(self):
        """Load artist avatar image."""
        cover_path = self._artist.cover_path

        if cover_path and Path(cover_path).exists():
            try:
                pixmap = QPixmap(cover_path)
                if not pixmap.isNull():
                    # Create circular mask
                    scaled = pixmap.scaled(
                        self.AVATAR_SIZE, self.AVATAR_SIZE,
                        Qt.KeepAspectRatioByExpanding,
                        Qt.SmoothTransformation
                    )
                    circular = self._make_circular(scaled)
                    self._avatar_label.setPixmap(circular)
                    return
            except Exception as e:
                logger.debug(f"Error loading avatar: {e}")

        # Default avatar
        self._set_default_avatar()

    def _make_circular(self, pixmap: QPixmap) -> QPixmap:
        """Make a pixmap circular."""
        size = min(pixmap.width(), pixmap.height())
        result = QPixmap(size, size)
        result.fill(Qt.transparent)

        painter = QPainter(result)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # Draw circular clip
        path = QPainter()
        painter.setClipRect(0, 0, size, size)

        # Create circular path
        from PySide6.QtGui import QPainterPath
        clip_path = QPainterPath()
        clip_path.addEllipse(0, 0, size, size)
        painter.setClipPath(clip_path)

        # Draw the pixmap
        painter.drawPixmap(0, 0, pixmap)
        painter.end()

        return result.scaled(
            self.AVATAR_SIZE, self.AVATAR_SIZE,
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation
        )

    def _set_default_avatar(self):
        """Set default avatar when no image is available."""
        pixmap = QPixmap(self.AVATAR_SIZE, self.AVATAR_SIZE)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw circular background
        painter.setBrush(QColor("#3d3d3d"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, self.AVATAR_SIZE, self.AVATAR_SIZE)

        # Draw person icon
        painter.setPen(QColor("#666666"))
        font = QFont()
        font.setPixelSize(60)
        painter.setFont(font)
        painter.drawText(
            QRect(0, 0, self.AVATAR_SIZE, self.AVATAR_SIZE),
            Qt.AlignCenter, "\u265A"  # Crown symbol for artist
        )
        painter.end()

        self._avatar_label.setPixmap(pixmap)

    def enterEvent(self, event):
        """Handle mouse enter for hover effect."""
        self._is_hovering = True
        self._avatar_container.setStyleSheet(f"""
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
        self._avatar_container.setStyleSheet(f"""
            QFrame {{
                background-color: #2a2a2a;
                border-radius: {self.BORDER_RADIUS}px;
            }}
        """)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        """Handle mouse click."""
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._artist)
        super().mousePressEvent(event)

    def get_artist(self) -> Artist:
        """Get the artist object."""
        return self._artist

    def update_avatar(self, cover_path: str):
        """Update avatar after download."""
        self._artist.cover_path = cover_path
        self._load_avatar()
