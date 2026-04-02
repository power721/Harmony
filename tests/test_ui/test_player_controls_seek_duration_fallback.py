"""
Regression tests for PlayerControls seek behavior when duration cache is stale.
"""

from types import SimpleNamespace

from ui.widgets.player_controls import PlayerControls


class _DummySlider:
    def __init__(self, value: int):
        self._value = value

    def value(self):
        return self._value

    def setValue(self, value):
        self._value = value


class _DummyLabel:
    def __init__(self):
        self.texts = []

    def setText(self, text):
        self.texts.append(text)


def _make_controls(*, slider_value: int, duration_ms: int, track_duration_s: float = 0.0):
    controls = PlayerControls.__new__(PlayerControls)
    seek_calls = []
    controls._is_seeking = True
    controls._skip_seek_on_release = False
    controls._current_duration = 0.0
    controls._progress_slider = _DummySlider(slider_value)
    controls._total_time_label = _DummyLabel()
    controls._player = SimpleNamespace(
        engine=SimpleNamespace(
            duration=lambda: duration_ms,
            seek=lambda position_ms: seek_calls.append(position_ms),
            current_track={"duration": track_duration_s} if track_duration_s > 0 else {},
        )
    )
    return controls, seek_calls


def test_seek_end_uses_engine_duration_when_cached_duration_is_zero():
    """Seek should use engine duration fallback instead of replaying from 0."""
    controls, seek_calls = _make_controls(slider_value=500, duration_ms=200_000)

    controls._on_seek_end()

    assert seek_calls == [100_000]


def test_seek_end_does_not_seek_when_duration_is_unknown():
    """Seek must not call engine.seek(0) when duration is still unavailable."""
    controls, seek_calls = _make_controls(slider_value=500, duration_ms=0)

    controls._on_seek_end()

    assert seek_calls == []


def test_seek_end_uses_track_duration_when_engine_duration_is_zero():
    """Seek should fall back to current track metadata duration after track switch."""
    controls, seek_calls = _make_controls(
        slider_value=500,
        duration_ms=0,
        track_duration_s=180.0,
    )

    controls._on_seek_end()

    assert seek_calls == [90_000]
