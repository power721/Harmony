"""
Recommendation card widgets for online recommendations.
"""

import logging
from typing import Callable, Dict, Any, Optional, List

from PySide6.QtCore import Qt, Signal, QThread, QRect
from PySide6.QtGui import QPixmap, QColor, QPainter, QFont
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QScrollArea,
    QProgressBar,
)
from shiboken6 import isValid

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
        self._stop_thread(wait_ms=500)

    def _stop_thread(self, wait_ms: int = 1000):
        """Stop worker thread cooperatively without force termination."""
        if not isValid(self):
            return
        if self.isRunning():
            self.requestInterruption()
            self.quit()
            self.wait(wait_ms)


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
        self._is_placeholder = bool(data.get("_placeholder"))
        self._is_hovering = False
        self._cover_loader: Optional[CoverLoader] = None

        self._setup_ui()
        self._set_default_cover()
        if not self._is_placeholder:
            self._load_cover()

        # Register with theme manager
        from system.theme import ThemeManager
        ThemeManager.instance().register_widget(self)

    def _setup_ui(self):
        """Set up the card UI."""
        from system.theme import ThemeManager

        self.setFixedSize(self.CARD_WIDTH, self.CARD_HEIGHT)
        self.setCursor(Qt.ArrowCursor if self._is_placeholder else Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Cover container
        self._cover_container = QFrame()
        self._cover_container.setFixedSize(self.COVER_SIZE, self.COVER_SIZE)

        # Pre-computed stylesheets for hover (H-08 optimization)
        theme = ThemeManager.instance().current_theme
        radius = self.BORDER_RADIUS
        self._style_normal = f"QFrame {{ background-color: {theme.background_hover}; border-radius: {radius}px; }}"
        self._style_hover = f"QFrame {{ background-color: {theme.background_hover}; border-radius: {radius}px; border: 2px solid {theme.highlight}; }}"
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
        self._name_label.setStyleSheet(self._name_label_style())
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
        from system.theme import ThemeManager

        theme = ThemeManager.instance().current_theme
        pixmap = QPixmap(self.COVER_SIZE, self.COVER_SIZE)
        pixmap.fill(QColor(theme.background_hover))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QColor(theme.text_secondary))
        font = QFont()
        font.setPixelSize(36)
        painter.setFont(font)
        painter.drawText(
            QRect(0, 0, self.COVER_SIZE, self.COVER_SIZE),
            Qt.AlignCenter,
            "…" if self._is_placeholder else "\u266B"
        )
        painter.end()

        self._cover_label.setPixmap(pixmap)

    def enterEvent(self, event):
        """Handle mouse enter for hover effect."""
        if self._is_placeholder:
            return
        self._is_hovering = True
        self._cover_container.setStyleSheet(self._style_hover)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Handle mouse leave for hover effect."""
        if self._is_placeholder:
            return
        self._is_hovering = False
        self._cover_container.setStyleSheet(self._style_normal)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        """Handle mouse click."""
        if not self._is_placeholder and event.button() == Qt.LeftButton:
            self.clicked.emit(self._data)
        super().mousePressEvent(event)

    def _name_label_style(self) -> str:
        from system.theme import ThemeManager

        if self._is_placeholder:
            return ThemeManager.instance().get_qss("""
                QLabel {
                    color: %text_secondary%;
                    font-size: 12px;
                    font-weight: bold;
                    background: transparent;
                }
            """)
        return ThemeManager.instance().get_qss("""
            QLabel {
                color: %text%;
                font-size: 12px;
                font-weight: bold;
                background: transparent;
            }
        """)

    def refresh_theme(self):
        """Refresh theme colors when theme changes."""
        from system.theme import ThemeManager

        theme = ThemeManager.instance().current_theme
        radius = self.BORDER_RADIUS

        # Update pre-computed stylesheets
        self._style_normal = f"QFrame {{ background-color: {theme.background_hover}; border-radius: {radius}px; }}"
        self._style_hover = f"QFrame {{ background-color: {theme.background_hover}; border-radius: {radius}px; border: 2px solid {theme.highlight}; }}"

        # Apply current state
        if self._is_hovering:
            self._cover_container.setStyleSheet(self._style_hover)
        else:
            self._cover_container.setStyleSheet(self._style_normal)

        # Update text labels
        self._name_label.setStyleSheet(self._name_label_style())
        if self._is_placeholder:
            self._set_default_cover()


class RecommendSection(QWidget):
    """Section widget displaying recommendation cards in a horizontal scroll."""

    recommendation_clicked = Signal(dict)  # Emits recommendation data

    _STYLE_TEMPLATE = """
        QLabel {
            color: %highlight%;
            font-size: 16px;
            font-weight: bold;
        }
    """

    _SCROLL_STYLE_TEMPLATE = """
        QScrollArea {
            background-color: transparent;
            border: none;
        }
        QScrollBar:horizontal {
            background-color: %background%;
            height: 8px;
            border-radius: 4px;
        }
        QScrollBar::handle:horizontal {
            background-color: %background_hover%;
            border-radius: 4px;
            min-width: 30px;
        }
        QScrollBar::handle:horizontal:hover {
            background-color: %border%;
        }
        QScrollBar::add-line, QScrollBar::sub-line {
            width: 0px;
        }
    """

    _LOADING_STYLE_TEMPLATE = """
        QProgressBar {
            background-color: %background_hover%;
            border: none;
            border-radius: 2px;
        }
        QProgressBar::chunk {
            background-color: %highlight%;
            border-radius: 2px;
        }
    """

    def __init__(self, title: str = None, parent=None, translator: Callable[[str, Optional[str]], str] = t):
        super().__init__(parent)
        self._cards: List[RecommendCard] = []
        self._custom_title = title
        self._translate = translator
        self._setup_ui()

        # Register with theme manager
        from system.theme import ThemeManager
        ThemeManager.instance().register_widget(self)

    def _setup_ui(self):
        """Set up the section UI."""
        from system.theme import ThemeManager

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 0)
        layout.setSpacing(2)

        # Set background style
        self.setStyleSheet("background-color: transparent;")

        # Title
        self._title_label = QLabel(self._custom_title if self._custom_title else self._translate("recommendations"))
        self._title_label.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TEMPLATE))
        layout.addWidget(self._title_label)

        # Scroll area for cards
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(False)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll_area.setFixedHeight(200)
        self._scroll_area.setStyleSheet(ThemeManager.instance().get_qss(self._SCROLL_STYLE_TEMPLATE))

        # Cards container
        self._cards_container = QWidget()
        self._cards_container.setStyleSheet("background-color: transparent;")
        self._cards_container.setFixedHeight(190)  # Slightly less than scroll area height
        self._cards_layout = QHBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(8)
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
        from system.theme import ThemeManager

        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setAlignment(Qt.AlignCenter)

        progress = QProgressBar()
        progress.setRange(0, 0)  # Indeterminate
        progress.setFixedSize(150, 4)
        progress.setStyleSheet(ThemeManager.instance().get_qss(self._LOADING_STYLE_TEMPLATE))
        layout.addWidget(progress)

        return widget

    def show_loading(self, count: int = 5):
        """Show placeholder cards while data is loading."""
        self._loading.hide()
        self._clear_cards()

        placeholder_title = self._translate("loading", "Loading...")
        placeholders = [
            {
                "_placeholder": True,
                "id": f"placeholder-{index}",
                "title": placeholder_title,
            }
            for index in range(max(count, 1))
        ]
        for rec in placeholders:
            card = RecommendCard(rec)
            self._cards.append(card)
            self._cards_layout.addWidget(card)

        total_width = len(self._cards) * (RecommendCard.CARD_WIDTH + 16) - 16
        self._cards_container.setFixedWidth(max(total_width, self.width()))
        self._cards_container.adjustSize()
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

        self._clear_cards()
        self.hide_loading()

        if not recommendations:
            logger.info("No recommendations, hiding section")
            self.hide()
            return

        for rec in recommendations:
            card = RecommendCard(rec)
            card.clicked.connect(self.recommendation_clicked.emit)
            self._cards.append(card)
            self._cards_layout.addWidget(card)

        # Update container width to fit all cards
        total_width = len(self._cards) * (RecommendCard.CARD_WIDTH + 16) - 16
        self._cards_container.setFixedWidth(max(total_width, self.width()))
        self._cards_container.adjustSize()

        self.show()

    def refresh_ui(self):
        """Refresh UI for language changes."""
        if hasattr(self, '_title_label'):
            if self._custom_title:
                self._title_label.setText(self._custom_title)
            else:
                self._title_label.setText(self._translate("recommendations"))

    def refresh_theme(self):
        """Refresh theme colors when theme changes."""
        from system.theme import ThemeManager

        # Update title label
        self._title_label.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TEMPLATE))

        # Update scroll area
        self._scroll_area.setStyleSheet(ThemeManager.instance().get_qss(self._SCROLL_STYLE_TEMPLATE))

        # Update loading indicator
        progress = self._loading.findChild(QProgressBar)
        if progress:
            progress.setStyleSheet(ThemeManager.instance().get_qss(self._LOADING_STYLE_TEMPLATE))
