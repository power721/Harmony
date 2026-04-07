"""
Custom frameless progress dialog matching EditMediaInfoDialog style.
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainterPath, QRegion
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QGraphicsDropShadowEffect,
)

from system.theme import ThemeManager
from ui.dialogs.dialog_title_bar import setup_equalizer_title_layout


class ProgressDialog(QDialog):
    """Frameless progress dialog with rounded corners and shadow."""

    canceled = Signal()

    def __init__(self, title: str, label_text: str, cancel_text: str, minimum: int, maximum: int, parent=None):
        super().__init__(parent)
        self._drag_pos = None
        self._minimum = minimum
        self._maximum = maximum

        self.setWindowTitle(title)
        self.setMinimumWidth(350)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowModality(Qt.WindowModal)
        self.setProperty("shell", True)

        self._setup_shadow()
        self._setup_ui(title, label_text, cancel_text)

        # Hide cancel button if no cancel text provided
        if not cancel_text:
            self._cancel_button.hide()

        ThemeManager.instance().register_widget(self)

    def _setup_shadow(self):
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

    def _setup_ui(self, title: str, label_text: str, cancel_text: str):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        container = QWidget()
        container.setObjectName("dialogContainer")
        outer.addWidget(container)

        container_layout = QVBoxLayout(container)
        layout, self._title_bar_controller = setup_equalizer_title_layout(
            self,
            container_layout,
            title,
        )

        # Status label
        self._label = QLabel(label_text)
        self._label.setWordWrap(True)
        layout.addWidget(self._label)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(self._minimum, self._maximum)
        self._progress_bar.setValue(self._minimum)
        layout.addWidget(self._progress_bar)

        # Cancel button
        self._cancel_button = QPushButton(cancel_text)
        self._cancel_button.setProperty("role", "cancel")
        self._cancel_button.clicked.connect(self._on_cancel)
        layout.addWidget(self._cancel_button, alignment=Qt.AlignRight)

    def setLabelText(self, text: str):
        self._label.setText(text)

    def setValue(self, value: int):
        self._progress_bar.setValue(value)

    def value(self) -> int:
        return self._progress_bar.value()

    def setRange(self, minimum: int, maximum: int):
        self._progress_bar.setRange(minimum, maximum)

    def _on_cancel(self):
        self.canceled.emit()
        self.reject()

    def wasCanceled(self) -> bool:
        return self.result() == QDialog.DialogCode.Rejected

    def refresh_theme(self):
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
