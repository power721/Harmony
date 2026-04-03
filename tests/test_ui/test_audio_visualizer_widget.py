"""Tests for AudioVisualizerWidget behavior."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from ui.widgets.audio_visualizer_widget import AudioVisualizerWidget


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


def test_visualizer_update_frame_invalid_mode_leaves_last_frame_none(qapp):
    widget = AudioVisualizerWidget()

    widget.update_frame({"mode": "invalid", "bins": [0.2]})

    assert widget._last_frame is None


def test_visualizer_accepts_waveform_frame(qapp):
    widget = AudioVisualizerWidget()

    frame = {"mode": "waveform", "samples": [-2.0, -0.2, 0.1, 1.5], "timestamp_ms": 33}
    widget.update_frame(frame)

    assert widget._last_frame is not None
    assert widget._last_frame["mode"] == "waveform"
    assert len(widget._last_frame["samples"]) == 4
    assert max(widget._last_frame["samples"]) <= 1.0
    assert min(widget._last_frame["samples"]) >= -1.0


def test_visualizer_invalid_timestamp_defaults_to_zero(qapp):
    widget = AudioVisualizerWidget()

    widget.update_frame({"mode": "spectrum", "bins": [0.4, 0.3], "timestamp_ms": "abc"})

    assert widget._last_frame["timestamp_ms"] == 0


def test_visualizer_paint_handles_recent_frame(qapp):
    widget = AudioVisualizerWidget()
    widget.resize(200, 120)
    widget.update_frame({"mode": "spectrum", "bins": [0.1, 0.5, 0.2]})

    widget.show()
    widget.repaint()
    qapp.processEvents()
