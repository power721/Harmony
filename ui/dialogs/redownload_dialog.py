"""
Re-download dialog for QQ Music tracks.
Allows user to select audio quality before re-downloading.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainterPath, QRegion
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QWidget, QGraphicsDropShadowEffect,
)

from system.i18n import t
from system.theme import ThemeManager
from services.cloud.qqmusic.common import (
    get_selectable_qualities,
    get_quality_label_key,
    normalize_quality,
)


class RedownloadDialog(QDialog):
    """Dialog for selecting audio quality when re-downloading a QQ Music track."""

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
            font-size: 13px;
        }
        QLabel#hintLabel {
            color: %text_secondary%;
            font-size: 12px;
        }
        QPushButton {
            background-color: %highlight%;
            color: %background%;
            border: none;
            padding: 8px 20px;
            border-radius: 4px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: %highlight_hover%;
        }
        QPushButton:disabled {
            background-color: %border%;
            color: %text_secondary%;
        }
        QPushButton[role="cancel"] {
            background-color: %border%;
            color: %text%;
        }
        QPushButton[role="cancel"]:hover {
            background-color: %background_hover%;
        }
    """ + ThemeManager.get_combobox_style() + """
    """

    def __init__(self, track_title: str, current_quality: str = None, parent=None):
        super().__init__(parent)
        self._quality = current_quality or "320"
        self._drag_pos = None

        self.setWindowFlags(Qt.WindowType.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._setup_shadow()
        self._setup_ui(track_title, current_quality)
        self.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TEMPLATE))
        ThemeManager.instance().register_widget(self)

    def _setup_shadow(self):
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

    def _setup_ui(self, track_title: str, current_quality: str = None):
        self.setWindowTitle(t("redownload"))
        self.setFixedSize(420, 220)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        container = QWidget()
        container.setObjectName("dialogContainer")
        outer.addWidget(container)

        layout = QVBoxLayout(container)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        # Title
        title_label = QLabel(f"{t('redownload')} - {track_title}")
        title_label.setObjectName("dialogTitle")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # Quality selection
        quality_row = QHBoxLayout()
        quality_label = QLabel(t("select_quality"))
        quality_label.setFixedWidth(80)
        quality_row.addWidget(quality_label)

        self._quality_combo = QComboBox()
        self._quality_combo.setCursor(Qt.PointingHandCursor)
        normalized_current = normalize_quality(current_quality or "320")
        default_index = 0
        for i, value in enumerate(get_selectable_qualities()):
            label_key = get_quality_label_key(value)
            label = t(label_key) if label_key else value
            self._quality_combo.addItem(label, value)
            if value == normalized_current:
                default_index = i
        self._quality_combo.setCurrentIndex(default_index)
        quality_row.addWidget(self._quality_combo)
        layout.addLayout(quality_row)

        # Hint label
        hint_label = QLabel(t("redownload_hint"))
        hint_label.setObjectName("hintLabel")
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)

        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton(t("cancel"))
        cancel_btn.setProperty("role", "cancel")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)

        confirm_btn = QPushButton(t("ok"))
        confirm_btn.setCursor(Qt.PointingHandCursor)
        confirm_btn.clicked.connect(self.accept)

        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(confirm_btn)
        layout.addLayout(button_layout)

    def get_quality(self) -> str:
        """Get selected quality value."""
        return self._quality_combo.currentData()

    @staticmethod
    def show_dialog(track_title: str, current_quality: str = None, parent=None):
        """Show dialog and return selected quality, or None if cancelled."""
        dialog = RedownloadDialog(track_title, current_quality, parent)
        if dialog.exec() == QDialog.Accepted:
            return dialog.get_quality()
        return None

    def refresh_theme(self):
        self.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TEMPLATE))

    def resizeEvent(self, event):
        path = QPainterPath()
        path.addRoundedRect(self.rect(), 12, 12)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
