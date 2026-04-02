"""Tests for EqualizerWidget behavior."""

import os
from unittest.mock import Mock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QSlider

from system.theme import ThemeManager
from ui.widgets.equalizer_widget import EqualizerWidget
from infrastructure.audio.audio_backend import AudioEffectCapabilities

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture(autouse=True)
def reset_theme_singleton():
    ThemeManager._instance = None
    yield
    ThemeManager._instance = None


@pytest.fixture
def mock_theme_config():
    config = Mock()
    config.get.return_value = "dark"
    return config


def test_equalizer_preset_updates_slider_values(qapp, mock_theme_config):
    ThemeManager.instance(mock_theme_config)
    widget = EqualizerWidget()

    sliders = [s for s in widget.findChildren(QSlider) if s.orientation() == Qt.Vertical]
    assert len(sliders) == 10

    widget._apply_preset("bass_boost")
    qapp.processEvents()

    expected = [6, 5, 4, 2, 0, 0, 0, 0, 0, 0]
    assert [s.value() for s in sliders] == expected


class _BackendWithEffects:
    def __init__(self):
        self.eq_bands = None
        self.effects = None

    def set_eq_bands(self, bands):
        self.eq_bands = bands

    def set_audio_effects(self, effects):
        self.effects = effects

    def get_audio_effect_capabilities(self):
        return AudioEffectCapabilities.all_supported()


class _ConfigStub:
    def __init__(self):
        self._saved = {}

    def get_audio_effects(self):
        return {
            "enabled": True,
            "eq_bands": [1.0] * 10,
            "bass_boost": 18.0,
            "treble_boost": 11.0,
            "reverb_level": 27.0,
            "stereo_enhance": 9.0,
        }

    def set_audio_effects(self, value):
        self._saved = value


def test_equalizer_widget_applies_and_persists_audio_effects(qapp, mock_theme_config):
    ThemeManager.instance(mock_theme_config)
    backend = _BackendWithEffects()
    config = _ConfigStub()
    widget = EqualizerWidget(config_manager=config)
    widget.apply_to_backend(backend)
    qapp.processEvents()

    assert backend.eq_bands is not None
    assert backend.effects is not None
    assert backend.effects.bass_boost == 18.0

    widget._bass_slider.setValue(35)
    qapp.processEvents()
    assert backend.effects.bass_boost == 35.0
    assert config._saved.get("bass_boost") == 35.0
