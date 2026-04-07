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
from ui.dialogs.dialog_title_bar import setup_equalizer_title_layout
from services.online.quality import (
    get_selectable_qualities,
    get_quality_label_key,
    normalize_quality,
)


class RedownloadDialog(QDialog):
    """Dialog for selecting audio quality when re-downloading a QQ Music track."""

    _STYLE_TEMPLATE = """
        QLabel#hintLabel {
            color: %text_secondary%;
            font-size: 12px;
        }
    """
    _POPUP_STYLE_TEMPLATE = """
        QListView {
            background-color: %background_alt%;
            border: 1px solid %border%;
            color: %text%;
            selection-background-color: %highlight%;
            selection-color: %background%;
            outline: none;
        }
        QListView::item {
            padding: 6px 10px;
            min-height: 20px;
        }
        QListView::item:hover {
            background-color: %highlight%;
            color: %background%;
        }
        QListView::item:selected {
            background-color: %highlight%;
            color: %background%;
        }
    """
    _POPUP_CONTAINER_STYLE_TEMPLATE = """
        QFrame {
            background-color: %background_alt%;
            border: 1px solid %border%;
        }
    """

    def __init__(self, track_title: str, current_quality: str = None, parent=None):
        super().__init__(parent)
        self._quality = current_quality or "320"
        self._drag_pos = None

        self.setWindowFlags(Qt.WindowType.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._setup_shadow()
        self._setup_ui(track_title, current_quality)
        self._apply_theme()
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

        container_layout = QVBoxLayout(container)
        layout, self._title_bar_controller = setup_equalizer_title_layout(
            self,
            container_layout,
            f"{t('redownload')} - {track_title}",
        )

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
        confirm_btn.setProperty("role", "primary")
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

    def _apply_theme(self):
        theme_manager = ThemeManager.instance()
        self.setStyleSheet(theme_manager.get_qss(self._STYLE_TEMPLATE))
        popup_view = self._quality_combo.view()
        popup_view.setStyleSheet(theme_manager.get_qss(self._POPUP_STYLE_TEMPLATE))
        popup_view.window().setStyleSheet(
            theme_manager.get_qss(self._POPUP_CONTAINER_STYLE_TEMPLATE)
        )

    def refresh_theme(self):
        self._apply_theme()
        self._title_bar_controller.refresh_theme()

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
