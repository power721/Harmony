"""Reusable drag-to-move behavior for frameless dialogs."""

from PySide6.QtCore import Qt


class DraggableDialogMixin:
    """Share the standard drag-to-move implementation across frameless dialogs."""

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
