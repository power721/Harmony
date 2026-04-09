"""Shared title bar for frameless dialogs."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .runtime_bridge import get_icon, register_themed_widget


@dataclass
class DialogTitleBarController:
    """Controller for dialog title bar widgets."""

    dialog: QDialog
    title_bar: QWidget
    title_label: QLabel
    close_btn: QPushButton

    def refresh_theme(self):
        """Refresh icons and re-polish global theme selectors."""
        self.close_btn.setIcon(get_icon("times.svg", None, 14))
        for widget in (self.title_bar, self.title_label, self.close_btn):
            style = widget.style()
            if style is not None:
                style.unpolish(widget)
                style.polish(widget)


def setup_dialog_title_layout(
    dialog: QDialog,
    container_layout: QVBoxLayout,
    title: str,
    *,
    content_margins: tuple[int, int, int, int] = (24, 20, 24, 20),
    content_spacing: int = 12,
) -> tuple[QVBoxLayout, DialogTitleBarController]:
    """Setup equalizer-style title bar and return content layout + controller."""
    container_layout.setContentsMargins(0, 0, 0, 0)
    container_layout.setSpacing(0)

    title_bar = QWidget()
    title_bar.setObjectName("dialogTitleBar")
    title_layout = QHBoxLayout(title_bar)
    title_layout.setContentsMargins(14, 4, 10, 4)
    title_layout.setSpacing(0)

    title_label = QLabel(title)
    title_label.setObjectName("dialogTitle")
    title_layout.addWidget(title_label)
    title_layout.addStretch()

    close_btn = QPushButton()
    close_btn.setObjectName("dialogCloseBtn")
    close_btn.setFixedSize(28, 28)
    close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    close_btn.setIcon(get_icon("times.svg", None, 14))
    close_btn.setIconSize(QSize(14, 14))
    close_btn.clicked.connect(dialog.close)
    title_layout.addWidget(close_btn)

    container_layout.addWidget(title_bar)

    content_widget = QWidget()
    container_layout.addWidget(content_widget)
    content_layout = QVBoxLayout(content_widget)
    content_layout.setContentsMargins(*content_margins)
    content_layout.setSpacing(content_spacing)

    controller = DialogTitleBarController(dialog, title_bar, title_label, close_btn)
    controller.refresh_theme()
    register_themed_widget(title_bar)

    _bind_title_bar_drag(dialog, title_bar)

    return content_layout, controller


def _bind_title_bar_drag(dialog: QDialog, title_bar: QWidget):
    def _mouse_press(event):
        if event.button() == Qt.MouseButton.LeftButton:
            dialog._drag_pos = event.globalPosition().toPoint() - dialog.frameGeometry().topLeft()
        event.accept()

    def _mouse_move(event):
        if getattr(dialog, "_drag_pos", None) and event.buttons() & Qt.MouseButton.LeftButton:
            dialog.move(event.globalPosition().toPoint() - dialog._drag_pos)
        event.accept()

    def _mouse_release(event):
        dialog._drag_pos = None
        event.accept()

    title_bar.mousePressEvent = _mouse_press
    title_bar.mouseMoveEvent = _mouse_move
    title_bar.mouseReleaseEvent = _mouse_release
