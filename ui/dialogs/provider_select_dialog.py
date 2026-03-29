"""
Provider selection dialog for cloud services.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QWidget, QGraphicsDropShadowEffect)
from PySide6.QtGui import QColor, QPainterPath, QRegion

from system.i18n import t
from system.theme import ThemeManager


class ProviderSelectDialog(QDialog):
    """Dialog for selecting cloud provider"""

    _STYLE_TEMPLATE = """
        QWidget#dialogContainer {
            background-color: %background_alt%;
            color: %text%;
            border: 1px solid %border%;
            border-radius: 12px;
        }
        QLabel#dialogTitle {
            color: %text%;
            font-size: 15px;
            font-weight: bold;
        }
        QLabel {
            color: %text%;
        }
        QPushButton {
            background-color: %border%;
            color: %text%;
            border: 1px solid %background_hover%;
            border-radius: 8px;
            padding: 16px 24px;
            font-size: 16px;
        }
        QPushButton:hover {
            background-color: %background_hover%;
            border: 1px solid %highlight%;
        }
        QPushButton:pressed {
            background-color: %background_alt%;
        }
        QPushButton[role="cancel"] {
            background-color: %border%;
            color: %text%;
            padding: 8px 24px;
            font-size: 14px;
        }
        QPushButton[role="cancel"]:hover {
            background-color: %background_hover%;
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_provider = None
        self._drag_pos = None

        # Make dialog frameless
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._setup_shadow()
        self.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TEMPLATE))
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
        """Setup the dialog UI"""
        self.setWindowTitle(t("select_provider"))
        self.setMinimumSize(400, 250)

        # Outer layout with 0 margins — container fills the dialog
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Container widget for rounded corners
        container = QWidget()
        container.setObjectName("dialogContainer")
        outer.addWidget(container)

        main_layout = QVBoxLayout(container)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(24, 20, 24, 20)

        # Title
        title = QLabel(t("select_cloud_provider"))
        title.setObjectName("dialogTitle")
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        # Provider buttons
        provider_layout = QHBoxLayout()
        provider_layout.setSpacing(20)

        # Quark button
        self._quark_btn = QPushButton("夸克网盘")
        self._quark_btn.setCursor(Qt.PointingHandCursor)
        self._quark_btn.clicked.connect(lambda: self._select_provider("quark"))
        provider_layout.addWidget(self._quark_btn)

        # Baidu button
        self._baidu_btn = QPushButton("百度网盘")
        self._baidu_btn.setCursor(Qt.PointingHandCursor)
        self._baidu_btn.clicked.connect(lambda: self._select_provider("baidu"))
        provider_layout.addWidget(self._baidu_btn)

        main_layout.addLayout(provider_layout)

        # Cancel button
        cancel_layout = QHBoxLayout()
        cancel_layout.addStretch()

        cancel_btn = QPushButton(t("cancel"))
        cancel_btn.setProperty("role", "cancel")
        cancel_btn.clicked.connect(self.reject)
        cancel_layout.addWidget(cancel_btn)
        cancel_layout.addStretch()

        main_layout.addLayout(cancel_layout)

    def _select_provider(self, provider: str):
        """Select provider and accept dialog"""
        self._selected_provider = provider
        self.accept()

    def get_selected_provider(self) -> str:
        """Get the selected provider"""
        return self._selected_provider

    def refresh_theme(self):
        """Refresh theme when changed."""
        self.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TEMPLATE))

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
