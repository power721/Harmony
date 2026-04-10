"""Reusable rounded-mask debounce behavior for frameless windows/dialogs."""

from PySide6.QtCore import QTimer
from PySide6.QtGui import QPainterPath, QRegion


class RoundedMaskDebounceMixin:
    """Debounce expensive setMask updates triggered by resize events."""

    _rounded_mask_radius = 12
    _rounded_mask_debounce_ms = 100

    def _ensure_rounded_mask_timer(self):
        timer = getattr(self, "_rounded_mask_timer", None)
        if timer is not None:
            return timer

        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(self._apply_rounded_mask)
        self._rounded_mask_timer = timer
        return timer

    def _schedule_rounded_mask_update(self):
        self._ensure_rounded_mask_timer().start(self._rounded_mask_debounce_ms)

    def _apply_rounded_mask(self):
        path = QPainterPath()
        path.addRoundedRect(self.rect(), self._rounded_mask_radius, self._rounded_mask_radius)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def resizeEvent(self, event):
        self._schedule_rounded_mask_update()
        super().resizeEvent(event)
