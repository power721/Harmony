"""Lightweight audio visualizer widget for spectrum and waveform modes."""

from __future__ import annotations

import math
from typing import Iterable, List, Optional

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget


class AudioVisualizerWidget(QWidget):
    """Simple QWidget that paints the latest audio spectrum or waveform frame."""

    _VALID_MODES = {"spectrum", "waveform"}
    _MAX_BINS = 256
    _MAX_SAMPLES = 512

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._mode: str = "spectrum"
        self._last_frame: Optional[dict] = None
        self._background = QColor(0, 0, 0, 25)
        self._spectrum_color = QColor("#45caff")
        self._waveform_color = QColor("#72f1b8")

        self.setMinimumHeight(100)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)

    def set_mode(self, mode: str) -> None:
        """Set the preferred rendering mode."""
        if mode not in self._VALID_MODES:
            return
        if mode == self._mode:
            return
        self._mode = mode
        self.update()

    def update_frame(self, frame: dict) -> None:
        """Update the widget with a new frame if it matches the schema."""
        if not isinstance(frame, dict):
            return

        mode = frame.get("mode") or self._mode
        if mode not in self._VALID_MODES:
            return

        timestamp_ms = self._parse_timestamp(frame.get("timestamp_ms"))

        if mode == "spectrum":
            bins = self._normalize_bins(frame.get("bins"))
            if not bins:
                return
            sanitized = {
                "mode": "spectrum",
                "bins": bins,
                "timestamp_ms": timestamp_ms,
            }
        else:
            samples = self._normalize_samples(frame.get("samples"))
            if len(samples) < 2:
                return
            sanitized = {
                "mode": "waveform",
                "samples": samples,
                "timestamp_ms": timestamp_ms,
            }

        self._last_frame = sanitized
        self.update()

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), self._background)

        if not self._last_frame:
            painter.end()
            return

        mode = self._last_frame.get("mode", self._mode)
        if mode == "waveform":
            self._paint_waveform(painter)
        else:
            self._paint_spectrum(painter)
        painter.end()

    def _paint_spectrum(self, painter: QPainter) -> None:
        bins: List[float] = self._last_frame.get("bins") or []
        if not bins:
            return

        count = len(bins)
        bar_width = max(1, self.width() // max(1, count))
        gap = max(1, int(bar_width * 0.2))
        usable_width = max(1, bar_width - gap)

        for index, value in enumerate(bins):
            height = int(value * self.height())
            height = max(1, min(self.height(), height))
            x = index * bar_width
            rect = QRectF(x, self.height() - height, usable_width, height)
            painter.fillRect(rect, self._spectrum_color)

    def _paint_waveform(self, painter: QPainter) -> None:
        samples: List[float] = self._last_frame.get("samples") or []
        if len(samples) < 2:
            return

        mid_y = self.height() / 2.0
        amplitude = self.height() * 0.45
        step = self.width() / max(1, len(samples) - 1)

        path = QPainterPath()
        path.moveTo(0, mid_y - samples[0] * amplitude)
        for index, value in enumerate(samples[1:], start=1):
            path.lineTo(index * step, mid_y - value * amplitude)

        painter.setPen(QPen(self._waveform_color, 2))
        painter.drawPath(path)

    @staticmethod
    def _parse_timestamp(value) -> int:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0
        if math.isnan(number) or math.isinf(number):
            return 0
        return max(0, int(number))

    @classmethod
    def _normalize_bins(cls, values: Optional[Iterable]) -> List[float]:
        if values is None:
            return []
        normalized: List[float] = []
        try:
            iterator = iter(values)
        except TypeError:
            return []
        try:
            for value in iterator:
                try:
                    number = float(value)
                except (TypeError, ValueError):
                    continue
                if math.isnan(number) or math.isinf(number):
                    continue
                number = max(0.0, min(1.0, number))
                normalized.append(number)
                if len(normalized) >= cls._MAX_BINS:
                    break
        except TypeError:
            return normalized
        return normalized

    @classmethod
    def _normalize_samples(cls, values: Optional[Iterable]) -> List[float]:
        if values is None:
            return []
        normalized: List[float] = []
        try:
            iterator = iter(values)
        except TypeError:
            return []
        try:
            for value in iterator:
                try:
                    number = float(value)
                except (TypeError, ValueError):
                    continue
                if math.isnan(number) or math.isinf(number):
                    continue
                number = max(-1.0, min(1.0, number))
                normalized.append(number)
                if len(normalized) >= cls._MAX_SAMPLES:
                    break
        except TypeError:
            return normalized
        return normalized
