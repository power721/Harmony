"""
Regression tests for PlayerControls equalizer availability.
"""

from types import SimpleNamespace

from system.i18n import t
from ui.widgets.player_controls import PlayerControls


class _DummyButton:
    def __init__(self):
        self.enabled = None
        self.tooltip = None

    def setEnabled(self, enabled):
        self.enabled = enabled

    def setToolTip(self, tooltip):
        self.tooltip = tooltip


def test_refresh_equalizer_availability_disables_button_for_unsupported_backend():
    """Qt backend should disable the equalizer entry point."""
    controls = PlayerControls.__new__(PlayerControls)
    controls._eq_btn = _DummyButton()
    controls._player = SimpleNamespace(
        engine=SimpleNamespace(
            backend=SimpleNamespace(supports_eq=lambda: False)
        )
    )

    controls._refresh_equalizer_availability()

    assert controls._eq_btn.enabled is False
    assert controls._eq_btn.tooltip == t("audio_effects_not_supported")


def test_show_equalizer_does_not_create_dialog_when_backend_lacks_eq(monkeypatch):
    """Equalizer dialog must not open for unsupported backends."""
    controls = PlayerControls.__new__(PlayerControls)
    controls._eq_btn = _DummyButton()
    controls._equalizer_dialog = None
    controls._player = SimpleNamespace(
        engine=SimpleNamespace(
            backend=SimpleNamespace(supports_eq=lambda: False)
        )
    )
    dialog_created = False

    def _unexpected_dialog(*args, **kwargs):
        nonlocal dialog_created
        dialog_created = True
        raise AssertionError("EqualizerDialog should not be created")

    monkeypatch.setattr("ui.widgets.player_controls.EqualizerDialog", _unexpected_dialog)

    controls._show_equalizer()

    assert dialog_created is False
    assert controls._equalizer_dialog is None
