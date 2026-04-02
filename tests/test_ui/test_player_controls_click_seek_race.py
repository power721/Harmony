"""
Regression tests for click/release seek race in PlayerControls.
"""

from types import SimpleNamespace

from ui.widgets.player_controls import PlayerControls


class _DummySlider:
    def __init__(self, value: int):
        self._value = value

    def value(self):
        return self._value


class _DummyLabel:
    def setText(self, _text):
        pass


def _make_controls(*, duration_s: float, slider_value: int):
    controls = PlayerControls.__new__(PlayerControls)
    seek_calls = []
    controls._is_seeking = False
    controls._skip_seek_on_release = False
    controls._current_duration = duration_s
    controls._progress_slider = _DummySlider(slider_value)
    controls._total_time_label = _DummyLabel()
    controls._player = SimpleNamespace(
        engine=SimpleNamespace(
            duration=lambda: int(duration_s * 1000),
            current_track={"duration": duration_s},
            seek=lambda position_ms: seek_calls.append(position_ms),
        )
    )
    return controls, seek_calls


def test_click_seek_skips_duplicate_seek_on_release():
    """Click should seek once and skip the follow-up release seek."""
    controls, seek_calls = _make_controls(duration_s=200.0, slider_value=500)

    controls._on_seek_start()
    controls._on_slider_clicked(750)
    controls._on_seek_end()

    assert seek_calls == [150_000]
