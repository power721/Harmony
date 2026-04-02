"""Tests for EqualizerWidget behavior."""

import os
from unittest.mock import Mock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QSlider

from system.theme import ThemeManager
from ui.widgets.equalizer_widget import EqualizerWidget

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
