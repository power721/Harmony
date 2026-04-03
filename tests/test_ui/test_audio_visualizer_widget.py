"""Tests for AudioVisualizerWidget behavior."""

import os

import pytest
from PySide6.QtWidgets import QApplication

from ui.widgets.audio_visualizer_widget import AudioVisualizerWidget

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_visualizer_accepts_valid_spectrum_frame(qapp):
    widget = AudioVisualizerWidget()

    frame = {"mode": "spectrum", "bins": [0.1, 0.5, 0.8], "timestamp_ms": 42}
    widget.update_frame(frame)

    assert widget._last_frame is not None
    assert widget._last_frame["mode"] == "spectrum"
    assert widget._last_frame["bins"] == frame["bins"]


def test_visualizer_ignores_invalid_mode(qapp):
    widget = AudioVisualizerWidget()
    widget.set_mode("waveform")

    widget.set_mode("not-a-mode")

    assert widget._mode == "waveform"
