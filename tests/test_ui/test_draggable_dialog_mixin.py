from types import SimpleNamespace

from PySide6.QtCore import QPoint, Qt

from ui.dialogs.draggable_dialog_mixin import DraggableDialogMixin


class _FakeEvent:
    def __init__(self, button=Qt.MouseButton.LeftButton, buttons=Qt.MouseButton.LeftButton, point=None):
        self._button = button
        self._buttons = buttons
        self._point = point or QPoint(20, 30)

    def button(self):
        return self._button

    def buttons(self):
        return self._buttons

    def globalPosition(self):
        return SimpleNamespace(toPoint=lambda: self._point)


class _FrameGeometry:
    @staticmethod
    def topLeft():
        return QPoint(5, 10)


class _Dialog(DraggableDialogMixin):
    def __init__(self):
        self._drag_pos = None
        self.moves = []

    def frameGeometry(self):
        return _FrameGeometry()

    def move(self, point):
        self.moves.append(point)


def test_draggable_dialog_mixin_moves_dialog_with_mouse_drag():
    dialog = _Dialog()

    dialog.mousePressEvent(_FakeEvent(point=QPoint(25, 40)))
    dialog.mouseMoveEvent(_FakeEvent(point=QPoint(35, 50)))
    dialog.mouseReleaseEvent(_FakeEvent())

    assert dialog.moves == [QPoint(15, 20)]
    assert dialog._drag_pos is None
