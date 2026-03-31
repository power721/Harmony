"""
Help dialog showing application info and keyboard shortcuts.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainterPath, QRegion
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QScrollArea,
    QWidget,
    QGraphicsDropShadowEffect,
)

from system.i18n import t
from system.theme import ThemeManager


class HelpDialog(QDialog):
    """Dialog showing help information and keyboard shortcuts."""

    _STYLE_TEMPLATE = """
        HelpDialog {
            background-color: transparent;
        }
        QWidget#dialogContainer {
            background-color: %background%;
            color: %text%;
            border: 1px solid %border%;
            border-radius: 12px;
        }
        QWidget#dialogContainer QLabel {
            color: %text%;
        }
        QGroupBox {
            color: %highlight%;
            font-weight: bold;
            border: 1px solid %border%;
            border-radius: 8px;
            margin-top: 12px;
            padding-top: 8px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 8px;
        }
        QPushButton {
            background-color: %background_hover%;
            color: %text%;
            border: 1px solid %border%;
            border-radius: 6px;
            padding: 8px 16px;
            font-size: 13px;
        }
        QPushButton:hover {
            background-color: %border%;
            border: 1px solid %highlight%;
        }
        QPushButton#rebuildBtn {
            background-color: %highlight%;
            color: %background%;
            font-weight: bold;
        }
        QPushButton#rebuildBtn:hover {
            background-color: %highlight_hover%;
        }
        QScrollArea {
            border: none;
            background-color: transparent;
        }
        QScrollArea > QWidget > QWidget {
            background-color: transparent;
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_pos = None

        # Make dialog frameless
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.setWindowTitle(t("help"))
        self.setMinimumSize(500, 550)
        self.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TEMPLATE))

        self._setup_shadow()
        ThemeManager.instance().register_widget(self)

        self._setup_ui()

    def _setup_shadow(self):
        """Setup drop shadow effect."""
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

    def _setup_ui(self):
        """Set up the dialog UI."""
        # Outer layout with 0 margins — container fills the dialog
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Container widget for rounded corners
        container = QWidget()
        container.setObjectName("dialogContainer")
        outer.addWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(15)

        # App info
        info_group = QGroupBox(t("about"))
        info_layout = QVBoxLayout(info_group)

        app_name = QLabel("Harmony")
        app_name.setStyleSheet(
            f"font-size: 24px; font-weight: bold; color: {ThemeManager.instance().current_theme.highlight};")
        app_name.setAlignment(Qt.AlignCenter)
        info_layout.addWidget(app_name)

        version_label = QLabel("v1.0")
        version_label.setStyleSheet(f"font-size: 14px; color: {ThemeManager.instance().current_theme.text_secondary};")
        version_label.setAlignment(Qt.AlignCenter)
        info_layout.addWidget(version_label)

        desc = QLabel(t("app_description"))
        desc.setStyleSheet(f"font-size: 13px; color: {ThemeManager.instance().current_theme.text_secondary};")
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        info_layout.addWidget(desc)

        content_layout.addWidget(info_group)

        # Keyboard shortcuts
        shortcuts_group = QGroupBox(t("keyboard_shortcuts"))
        shortcuts_layout = QVBoxLayout(shortcuts_group)

        shortcuts = [
            ("Space", t("shortcut_play_pause")),
            ("Ctrl + ←", t("shortcut_prev")),
            ("Ctrl + →", t("shortcut_next")),
            ("Ctrl + ↑", t("shortcut_vol_up")),
            ("Ctrl + ↓", t("shortcut_vol_down")),
            ("Ctrl + F", t("shortcut_favorite")),
            ("Ctrl + M", t("shortcut_mini")),
            ("Ctrl + N", t("shortcut_new_playlist")),
            ("Ctrl + Q", t("shortcut_quit")),
            ("F1", t("shortcut_help")),
        ]

        for key, action in shortcuts:
            row = QHBoxLayout()
            key_label = QLabel(key)
            key_label.setStyleSheet(f"""
                background-color: {ThemeManager.instance().current_theme.background_hover};
                padding: 4px 10px;
                border-radius: 4px;
                font-family: monospace;
                font-size: 12px;
            """)
            key_label.setFixedWidth(100)
            row.addWidget(key_label)

            action_label = QLabel(action)
            action_label.setStyleSheet(
                f"font-size: 13px; color: {ThemeManager.instance().current_theme.text_secondary};")
            row.addWidget(action_label)
            row.addStretch()

            shortcuts_layout.addLayout(row)

        content_layout.addWidget(shortcuts_group)

        content_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)

        # Close button
        close_btn = QPushButton(t("ok"))
        close_btn.clicked.connect(self.accept)
        close_btn.setFixedWidth(100)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        close_layout.addWidget(close_btn)
        close_layout.addStretch()
        layout.addLayout(close_layout)

    def refresh_theme(self):
        """Refresh theme when changed."""
        self.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TEMPLATE))
        # Re-apply inline styles that use theme colors
        theme = ThemeManager.instance().current_theme

        # Find labels by iterating through the widget tree
        for label in self.findChildren(QLabel):
            text = label.text()
            if text == "Harmony":
                label.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {theme.highlight};")
            elif text == "v1.0":
                label.setStyleSheet(f"font-size: 14px; color: {theme.text_secondary};")
            elif label.objectName() != "keyLabel" and text not in ["Harmony", "v1.0"]:
                # Update shortcut action labels (not key labels which have their own style)
                # Check if this is in the shortcuts section
                parent = label.parentWidget()
                if parent and isinstance(parent.findChild(QGroupBox), QGroupBox):
                    # This is likely a shortcut action label
                    label.setStyleSheet(f"font-size: 13px; color: {theme.text_secondary};")

        # Update key labels background
        for label in self.findChildren(QLabel):
            if "font-family: monospace" in label.styleSheet():
                label.setStyleSheet(f"""
                    background-color: {theme.background_hover};
                    padding: 4px 10px;
                    border-radius: 4px;
                    font-family: monospace;
                    font-size: 12px;
                """)

    def resizeEvent(self, event):
        """Apply rounded corner mask."""
        path = QPainterPath()
        path.addRoundedRect(self.rect(), 12, 12)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        """Handle mouse press for drag to move."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        """Handle mouse move for drag to move."""
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        """Handle mouse release."""
        self._drag_pos = None
