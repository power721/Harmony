"""
Re-download dialog for online tracks.
Allows user to select audio quality before re-downloading.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainterPath, QRegion
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QWidget, QGraphicsDropShadowEffect, QComboBox,
)

from system.i18n import t
from system.theme import ThemeManager
from ui.dialogs.dialog_title_bar import setup_equalizer_title_layout


class RedownloadDialog(QDialog):
    """Dialog for selecting plugin-provided quality before re-download."""

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

    def __init__(
        self,
        track_title: str,
        current_quality: str = None,
        quality_options: list[dict[str, str]] | list[str] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._quality = None
        self._drag_pos = None
        self._quality_options = self._normalize_quality_options(quality_options)
        self._quality_combo = None

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

        hint_label = QLabel(t("redownload_hint"))
        hint_label.setObjectName("hintLabel")
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)

        if self._quality_options:
            quality_row = QHBoxLayout()
            quality_label = QLabel(t("select_quality"))
            self._quality_combo = QComboBox()
            self._quality_combo.setFixedWidth(260)
            self._quality_combo.setProperty("compact", True)
            for option in self._quality_options:
                self._quality_combo.addItem(option["label"], option["value"])
            self._select_initial_quality(current_quality)
            quality_row.addWidget(quality_label)
            quality_row.addWidget(self._quality_combo)
            quality_row.addStretch()
            layout.addLayout(quality_row)
        else:
            unsupported_label = QLabel(t("not_supported_yet"))
            unsupported_label.setObjectName("hintLabel")
            unsupported_label.setWordWrap(True)
            layout.addWidget(unsupported_label)

        layout.addStretch()

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        if self._quality_options:
            cancel_btn = QPushButton(t("cancel"))
            cancel_btn.setProperty("role", "cancel")
            cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            cancel_btn.clicked.connect(self.reject)
            button_layout.addWidget(cancel_btn)

            ok_btn = QPushButton(t("ok"))
            ok_btn.setProperty("role", "primary")
            ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            ok_btn.clicked.connect(self.accept)
            button_layout.addWidget(ok_btn)
        else:
            close_btn = QPushButton(t("ok"))
            close_btn.setProperty("role", "primary")
            close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            close_btn.clicked.connect(self.reject)
            button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

    def get_quality(self) -> str:
        """Get selected quality value."""
        if self._quality_combo is not None:
            selected = self._quality_combo.currentData()
            self._quality = str(selected or "").strip() or None
        return self._quality

    @staticmethod
    def show_dialog(
        track_title: str,
        current_quality: str = None,
        quality_options: list[dict[str, str]] | list[str] | None = None,
        parent=None,
    ):
        dialog = RedownloadDialog(track_title, current_quality, quality_options, parent)
        if dialog.exec() == QDialog.Accepted:
            return dialog.get_quality()
        return None

    @staticmethod
    def _normalize_quality_options(options) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        if not options:
            return normalized
        for item in options:
            if isinstance(item, str):
                value = item.strip()
                if value:
                    normalized.append({"value": value, "label": value})
                continue
            if not isinstance(item, dict):
                continue
            value = str(item.get("value", "") or "").strip()
            if not value:
                continue
            label = str(item.get("label", "") or value).strip() or value
            normalized.append({"value": value, "label": label})
        return normalized

    def _select_initial_quality(self, current_quality: str | None) -> None:
        if self._quality_combo is None:
            return
        preferred = str(current_quality or "").strip().lower()
        index_to_select = 0
        if preferred:
            for i, option in enumerate(self._quality_options):
                if option["value"].strip().lower() == preferred:
                    index_to_select = i
                    break
        self._quality_combo.setCurrentIndex(index_to_select)

    def _apply_theme(self):
        theme_manager = ThemeManager.instance()
        self.setStyleSheet(theme_manager.get_qss(self._STYLE_TEMPLATE))

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
