import os
from unittest.mock import Mock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from domain.artist import Artist
from system.theme import ThemeManager
from ui.widgets.artist_card import ArtistCard

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


def test_artist_card_load_avatar_scales_pixmap_once(qapp, mock_theme_config, monkeypatch, tmp_path):
    ThemeManager.instance(mock_theme_config)
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.blue)
    avatar_path = tmp_path / "avatar.png"
    pixmap.save(str(avatar_path))

    scaled_calls = []
    original_scaled = QPixmap.scaled

    def tracking_scaled(self, *args, **kwargs):
        scaled_calls.append((self.width(), self.height(), args[:2]))
        return original_scaled(self, *args, **kwargs)

    monkeypatch.setattr(QPixmap, "scaled", tracking_scaled)

    card = ArtistCard(Artist(name="Artist", cover_path=str(avatar_path)))
    _ = card  # keep alive

    assert len(scaled_calls) == 1
