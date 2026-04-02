"""
Regression tests for seek synchronization in NowPlayingWindow.
"""

from types import SimpleNamespace

from ui.windows.now_playing_window import NowPlayingWindow


class _DummySlider:
    def __init__(self):
        self.values = []

    def setValue(self, value):
        self.values.append(value)


class _DummyLabel:
    def __init__(self):
        self.texts = []

    def setText(self, text):
        self.texts.append(text)


class _DummyLyrics:
    def __init__(self):
        self.positions = []

    def update_position(self, position_s):
        self.positions.append(position_s)


def _build_window_for_position_updates(*, controls_is_seeking: bool):
    window = NowPlayingWindow.__new__(NowPlayingWindow)
    window._current_duration = 300.0
    window._is_seeking = False
    window._player_controls = SimpleNamespace(_is_seeking=controls_is_seeking)
    window._progress_slider = _DummySlider()
    window._current_time = _DummyLabel()
    window._lyrics_widget = _DummyLyrics()
    return window


def test_on_position_changed_skips_slider_updates_while_controls_seeking():
    """NowPlayingWindow must not overwrite slider during active seek in PlayerControls."""
    window = _build_window_for_position_updates(controls_is_seeking=True)

    window._on_position_changed(120_000)

    assert window._progress_slider.values == []
    assert window._current_time.texts == []
    assert window._lyrics_widget.positions == [120.0]


def test_on_position_changed_updates_slider_when_not_seeking():
    """NowPlayingWindow updates slider/time only when no seek is active."""
    window = _build_window_for_position_updates(controls_is_seeking=False)

    window._on_position_changed(120_000)

    assert window._progress_slider.values == [400]
    assert window._current_time.texts
    assert window._lyrics_widget.positions == [120.0]
