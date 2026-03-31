"""
Welcome/onboarding dialog shown on first run when the library is empty.

Guides new users to add their first music folder.
"""
import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainterPath, QRegion
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel,
    QPushButton, QGraphicsDropShadowEffect, QWidget,
    QFileDialog,
)

from system.i18n import t
from system.theme import ThemeManager
from ui.icons import IconName, get_icon

logger = logging.getLogger(__name__)


class WelcomeDialog(QDialog):
    """Theme-aware frameless welcome dialog for first-run onboarding."""

    _STYLE_TEMPLATE = """
        QWidget#welcomeContainer {
            background-color: %background_alt%;
            color: %text%;
            border: 1px solid %border%;
            border-radius: 12px;
        }
        QLabel#welcomeTitle {
            color: %text%;
            font-size: 20px;
            font-weight: bold;
        }
        QLabel#welcomeSubtitle {
            color: %text_secondary%;
            font-size: 13px;
        }
        QLabel#welcomeDescription {
            color: %text_secondary%;
            font-size: 13px;
        }
        QPushButton#addFolderBtn {
            background-color: %highlight%;
            color: %background%;
            border: 1px solid %highlight%;
            border-radius: 8px;
            padding: 12px 28px;
            min-width: 200px;
            font-size: 14px;
            font-weight: bold;
        }
        QPushButton#addFolderBtn:hover {
            background-color: %highlight_hover%;
        }
        QPushButton#skipBtn {
            background-color: transparent;
            color: %text_secondary%;
            border: none;
            padding: 8px 20px;
            font-size: 13px;
        }
        QPushButton#skipBtn:hover {
            color: %text%;
        }
    """

    def __init__(self, parent=None, library_service=None):
        super().__init__(parent)
        self._library_service = library_service
        self._drag_pos = None
        self._selected_folder = None

        self.setWindowFlags(Qt.WindowType.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(480, 360)

        self._setup_shadow()
        self._setup_ui()
        self._apply_style()
        ThemeManager.instance().register_widget(self)

    def _setup_shadow(self):
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        container = QWidget()
        container.setObjectName("welcomeContainer")
        outer.addWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(8)

        # Icon
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_pixmap = get_icon(IconName.MUSIC, None, 48).pixmap(48, 48)
        icon_label.setPixmap(icon_pixmap)
        layout.addWidget(icon_label)

        layout.addSpacing(12)

        # Title
        self._title_label = QLabel(t("welcome_title"))
        self._title_label.setObjectName("welcomeTitle")
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title_label)

        layout.addSpacing(4)

        # Subtitle
        subtitle = QLabel(t("welcome_subtitle"))
        subtitle.setObjectName("welcomeSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(12)

        # Description
        description = QLabel(t("welcome_description"))
        description.setObjectName("welcomeDescription")
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(description)

        layout.addStretch()

        # Add Folder button
        self._add_folder_btn = QPushButton(t("add_music_folder"))
        self._add_folder_btn.setObjectName("addFolderBtn")
        self._add_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_folder_btn.clicked.connect(self._on_add_folder)
        layout.addWidget(self._add_folder_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addSpacing(4)

        # Skip button
        self._skip_btn = QPushButton(t("skip"))
        self._skip_btn.setObjectName("skipBtn")
        self._skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._skip_btn.clicked.connect(self.reject)
        layout.addWidget(self._skip_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def _on_add_folder(self):
        """Open directory picker and scan the selected folder."""
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setWindowTitle(t("select_music_folder"))

        if dialog.exec():
            folder = dialog.selectedFiles()[0]
            self._selected_folder = folder
            self.accept()

    def get_selected_folder(self) -> str | None:
        """Return the folder selected by the user, or None."""
        return self._selected_folder

    def _apply_style(self):
        self.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TEMPLATE))

    def refresh_theme(self):
        self._apply_style()
        icon_pixmap = get_icon(IconName.MUSIC, None, 48).pixmap(48, 48)
        for child in self.findChildren(QLabel):
            if child.pixmap() and child.pixmap().width() >= 48:
                child.setPixmap(icon_pixmap)
                break

    def resizeEvent(self, event):
        path = QPainterPath()
        path.addRoundedRect(self.rect(), 12, 12)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))
        super().resizeEvent(event)

    # --- Drag to move ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
