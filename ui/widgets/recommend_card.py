"""
Recommendation card widgets for QQ Music recommendations.
"""

import logging
from typing import Dict, Any, Optional, List

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QScrollArea,
    QProgressBar,
)
from PySide6.QtCore import Qt, Signal, QThread, QSize, QRect
from PySide6.QtGui import QPixmap, QColor, QPainter, QFont

from system.i18n import t

logger = logging.getLogger(__name__)


class CoverLoader(QThread):
    """Background worker for loading cover images."""

    cover_loaded = Signal(str, QPixmap)  # (cover_url, pixmap)

    def __init__(self, cover_url: str, size: int = 150, parent=None):
        super().__init__(parent)
        self._cover_url = cover_url
        self._size = size

    def run(self):
        try:
            from infrastructure.cache import ImageCache
            import requests

            # Check disk cache first
            image_data = ImageCache.get(self._cover_url)
            if not image_data:
                # Download from network
                response = requests.get(self._cover_url, timeout=10)
                response.raise_for_status()
                image_data = response.content
                # Save to cache
                ImageCache.set(self._cover_url, image_data)

            pixmap = QPixmap()
            if pixmap.loadFromData(image_data):
                scaled = pixmap.scaled(
                    self._size, self._size,
                    Qt.KeepAspectRatioByExpanding,
                    Qt.SmoothTransformation
                )
                self.cover_loaded.emit(self._cover_url, scaled)
        except Exception as e:
            logger.debug(f"Error loading cover: {e}")

    def __del__(self):
        """Ensure thread is properly stopped before deletion."""
        if self.isRunning():
            self.wait(100)  # Wait up to 100ms for thread to finish


class RecommendCard(QWidget):
    """Card widget for displaying a recommendation."""

    clicked = Signal(dict)  # Emits recommendation data

    COVER_SIZE = 120
    CARD_WIDTH = 140
    CARD_HEIGHT = 180
    BORDER_RADIUS = 8

    def __init__(self, data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self._data = data
        self._is_hovering = False
        self._cover_loader: Optional[CoverLoader] = None

        self._setup_ui()
        self._set_default_cover()
        self._load_cover()

    def _setup_ui(self):
        """Set up the card UI."""
        self.setFixedSize(self.CARD_WIDTH, self.CARD_HEIGHT)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Cover container
        self._cover_container = QFrame()
        self._cover_container.setFixedSize(self.COVER_SIZE, self.COVER_SIZE)

        # Pre-computed stylesheets for hover (H-08 optimization)
        radius = self.BORDER_RADIUS
        self._style_normal = f"QFrame {{ background-color: #2a2a2a; border-radius: {radius}px; }}"
        self._style_hover = f"QFrame {{ background-color: #2a2a2a; border-radius: {radius}px; border: 2px solid #1db954; }}"
        self._cover_container.setStyleSheet(self._style_normal)

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

        # Name label
        title = self._data.get('title', '') or self._data.get('name', '')
        self._name_label = QLabel(title)
        self._name_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._name_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 12px;
                font-weight: bold;
                background: transparent;
            }
        """)
        self._name_label.setWordWrap(True)
        self._name_label.setMaximumHeight(32)

        info_layout.addWidget(self._name_label)
        info_layout.addStretch()

        layout.addWidget(self._cover_container, 0, Qt.AlignHCenter)
        layout.addWidget(info_widget)

    def _load_cover(self):
        """Load cover image asynchronously."""
        cover_url = self._data.get('cover_url', '')
        if not cover_url:
            return

        self._cover_loader = CoverLoader(cover_url, self.COVER_SIZE)
        self._cover_loader.cover_loaded.connect(self._on_cover_loaded)
        self._cover_loader.start()

    def _on_cover_loaded(self, url: str, pixmap: QPixmap):
        """Handle cover loaded."""
        if not pixmap.isNull():
            self._cover_label.setPixmap(pixmap)

    def _set_default_cover(self):
        """Set default cover when no cover is available."""
        pixmap = QPixmap(self.COVER_SIZE, self.COVER_SIZE)
        pixmap.fill(QColor("#3d3d3d"))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QColor("#666666"))
        font = QFont()
        font.setPixelSize(36)
        painter.setFont(font)
        painter.drawText(
            QRect(0, 0, self.COVER_SIZE, self.COVER_SIZE),
            Qt.AlignCenter, "\u266B"
        )
        painter.end()

        self._cover_label.setPixmap(pixmap)

    def enterEvent(self, event):
        """Handle mouse enter for hover effect."""
        self._is_hovering = True
        self._cover_container.setStyleSheet(self._style_hover)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Handle mouse leave for hover effect."""
        self._is_hovering = False
        self._cover_container.setStyleSheet(self._style_normal)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        """Handle mouse click."""
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._data)
        super().mousePressEvent(event)


class RecommendSection(QWidget):
    """Section widget displaying recommendation cards in a horizontal scroll."""

    recommendation_clicked = Signal(dict)  # Emits recommendation data

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: List[RecommendCard] = []
        self._setup_ui()

    def _setup_ui(self):
        """Set up the section UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 0)
        layout.setSpacing(6)

        # Set background style
        self.setStyleSheet("background-color: transparent;")

        # Title
        self._title_label = QLabel(t("recommendations"))
        self._title_label.setStyleSheet("""
            QLabel {
                color: #1db954;
                font-size: 16px;
                font-weight: bold;
            }
        """)
        layout.addWidget(self._title_label)

        # Scroll area for cards
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(False)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll_area.setFixedHeight(200)
        self._scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:horizontal {
                background-color: #1e1e1e;
                height: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal {
                background-color: #3d3d3d;
                border-radius: 4px;
                min-width: 30px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #4d4d4d;
            }
            QScrollBar::add-line, QScrollBar::sub-line {
                width: 0px;
            }
        """)

        # Cards container
        self._cards_container = QWidget()
        self._cards_container.setStyleSheet("background-color: transparent;")
        self._cards_container.setFixedHeight(190)  # Slightly less than scroll area height
        self._cards_layout = QHBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(16)
        self._cards_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self._scroll_area.setWidget(self._cards_container)
        layout.addWidget(self._scroll_area)

        # Loading indicator
        self._loading = self._create_loading_indicator()
        layout.addWidget(self._loading)
        self._loading.hide()

        # Initially hidden
        self.hide()

    def _create_loading_indicator(self) -> QWidget:
        """Create loading indicator."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setAlignment(Qt.AlignCenter)

        progress = QProgressBar()
        progress.setRange(0, 0)  # Indeterminate
        progress.setFixedSize(150, 4)
        progress.setStyleSheet("""
            QProgressBar {
                background-color: #2a2a2a;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #1db954;
                border-radius: 2px;
            }
        """)
        layout.addWidget(progress)

        return widget

    def show_loading(self):
        """Show loading indicator."""
        self._loading.show()
        # Clear existing cards
        self._clear_cards()
        # Show section while loading
        self.show()

    def hide_loading(self):
        """Hide loading indicator."""
        self._loading.hide()

    def _clear_cards(self):
        """Clear all existing cards."""
        for card in self._cards:
            card.deleteLater()
        self._cards.clear()

    def load_recommendations(self, recommendations: List[Dict[str, Any]]):
        """
        Load recommendation cards.

        Args:
            recommendations: List of recommendation data dicts
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"load_recommendations called with {len(recommendations)} items")

        self._clear_cards()
        self.hide_loading()

        if not recommendations:
            logger.info("No recommendations, hiding section")
            self.hide()
            return

        for rec in recommendations:
            logger.debug(f"Creating card: title={rec.get('title')}, cover_url={rec.get('cover_url')}")
            card = RecommendCard(rec)
            card.clicked.connect(self.recommendation_clicked.emit)
            self._cards.append(card)
            self._cards_layout.addWidget(card)

        # Update container width to fit all cards
        total_width = len(self._cards) * (RecommendCard.CARD_WIDTH + 16) - 16
        self._cards_container.setFixedWidth(max(total_width, self.width()))
        self._cards_container.adjustSize()

        logger.info(f"Showing section with {len(self._cards)} cards, container width: {total_width}")
        self.show()

    def refresh_ui(self):
        """Refresh UI for language changes."""
        if hasattr(self, '_title_label'):
            self._title_label.setText(t("recommendations"))
