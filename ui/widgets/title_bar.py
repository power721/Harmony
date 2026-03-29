"""
Spotify-style custom title bar for Harmony.

Features:
- Mac-style decorative traffic lights
- Windows-style window controls (minimize, maximize, close)
- Drag-to-move
- Double-click to toggle maximize
- Theme-aware via ThemeManager token system
- Dynamic accent color from album cover (gradient blend)
"""
import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QLinearGradient
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
)

from system.theme import ThemeManager
from ui.icons import IconName, get_icon

logger = logging.getLogger(__name__)


class TitleBar(QWidget):
    """Custom Spotify-style title bar widget."""

    _STYLE_TEMPLATE = """
        QWidget#titleBar {
            background-color: %background%;
        }
        QPushButton#winBtn {
            border: none;
            color: %text%;
            background: transparent;
            width: 36px;
            height: 28px;
            border-radius: 6px;
        }
        QPushButton#winBtn:hover {
            background-color: %background_hover%;
        }
        QPushButton#closeBtn {
            border: none;
            color: %text%;
            background: transparent;
            width: 36px;
            height: 28px;
            border-radius: 6px;
        }
        QPushButton#closeBtn:hover {
            background-color: #e81123;
            color: white;
        }
        QLabel#titleLabel {
            color: %text%;
            font-size: 14px;
            font-weight: bold;
        }
        QLabel#trackLabel {
            color: %text_secondary%;
            font-size: 13px;
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("titleBar")
        self.setFixedHeight(44)

        self._accent_color: QColor | None = None
        self._default_title = "Harmony"
        self._drag_pos = None

        self._setup_ui()
        self._apply_style()

        # Register for theme changes
        ThemeManager.instance().register_widget(self)

    def _setup_ui(self):
        """Create child widgets and layout."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 6, 0)
        layout.setSpacing(0)

        # === Mac-style decorative traffic lights ===
        mac_container = QWidget()
        mac_container.setFixedWidth(60)
        mac_layout = QHBoxLayout(mac_container)
        mac_layout.setContentsMargins(0, 0, 0, 0)
        mac_layout.setSpacing(8)
        mac_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        for color in ["#ff5f57", "#febc2e", "#28c840"]:
            dot = QLabel()
            dot.setFixedSize(12, 12)
            dot.setStyleSheet(
                f"""
                QLabel {{
                    background-color: {color};
                    border-radius: 6px;
                }}
            """
            )
            mac_layout.addWidget(dot)

        layout.addWidget(mac_container)

        # === Title (center) ===
        self._title_label = QLabel(self._default_title)
        self._title_label.setObjectName("titleLabel")
        layout.addWidget(self._title_label)

        layout.addStretch()

        # === Windows-style controls (right) ===
        self._btn_min = QPushButton()
        self._btn_min.setObjectName("winBtn")
        self._btn_min.setIcon(get_icon(IconName.MINIMIZE, None, 14))
        self._btn_min.clicked.connect(
            lambda: self.window().showMinimized() if self.window() else None
        )

        self._btn_max = QPushButton()
        self._btn_max.setObjectName("winBtn")
        self._btn_max.setIcon(get_icon(IconName.MAXIMIZE, None, 14))
        self._btn_max.clicked.connect(self._toggle_maximize)

        self._btn_close = QPushButton()
        self._btn_close.setObjectName("closeBtn")
        self._btn_close.setIcon(get_icon(IconName.TIMES, None, 14))
        self._btn_close.clicked.connect(
            lambda: self.window().close() if self.window() else None
        )

        for btn in (self._btn_min, self._btn_max, self._btn_close):
            btn.setFixedSize(36, 28)
            layout.addWidget(btn)

    def _toggle_maximize(self):
        """Toggle maximize/restore."""
        win = self.window()
        if win:
            if win.isMaximized():
                win.showNormal()
            else:
                win.showMaximized()

    def _apply_style(self):
        """Apply themed stylesheet."""
        theme = ThemeManager.instance()
        style = theme.get_qss(self._STYLE_TEMPLATE)
        self.setStyleSheet(style)

    def refresh_theme(self):
        """Called by ThemeManager on theme change."""
        self._apply_style()
        self._btn_min.setIcon(get_icon(IconName.MINIMIZE, None, 14))
        self._btn_max.setIcon(get_icon(IconName.MAXIMIZE, None, 14))
        self._btn_close.setIcon(get_icon(IconName.TIMES, None, 14))
        self.update()

    # === Track title display ===

    def set_track_title(self, title: str, artist: str):
        """Display track info in the title bar."""
        text = f"{title} \u2014 {artist}" if artist else title
        self._title_label.setText(text)
        self._title_label.setObjectName("trackLabel")
        style = self._title_label.style()
        if style:
            style.unpolish(self._title_label)
            style.polish(self._title_label)

    def clear_track_title(self):
        """Restore default 'Harmony' title."""
        self._title_label.setText(self._default_title)
        self._title_label.setObjectName("titleLabel")
        style = self._title_label.style()
        if style:
            style.unpolish(self._title_label)
            style.polish(self._title_label)

    # === Dynamic accent color ===

    def set_accent_color(self, color: QColor):
        """Set accent color from album cover. Triggers gradient update."""
        self._accent_color = color
        self.update()

    def clear_accent_color(self):
        """Clear accent color, revert to theme background."""
        self._accent_color = None
        self.update()

    def paintEvent(self, event):
        """Paint gradient background when accent color is active."""
        if self._accent_color is None:
            return super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Get theme background
        theme = ThemeManager.instance()
        bg_color = QColor(theme.current_theme.background)

        # Blend: 40% accent + 60% theme background
        blended = QColor(
            int(self._accent_color.red() * 0.4 + bg_color.red() * 0.6),
            int(self._accent_color.green() * 0.4 + bg_color.green() * 0.6),
            int(self._accent_color.blue() * 0.4 + bg_color.blue() * 0.6),
        )

        # Gradient: blended at top -> theme bg at bottom
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, blended)
        gradient.setColorAt(1.0, bg_color)

        painter.fillRect(self.rect(), gradient)
        painter.end()

    # === Drag to move ===

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            win = self.window()
            if win:
                delta = event.globalPosition().toPoint() - self._drag_pos
                win.move(win.pos() + delta)
                self._drag_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._toggle_maximize()
