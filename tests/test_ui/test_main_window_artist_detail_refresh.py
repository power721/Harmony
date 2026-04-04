"""MainWindow artist-detail refresh behavior tests."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import ui.windows.main_window as main_window_module
from ui.windows.main_window import MainWindow


def test_refresh_current_artist_detail_updates_artist_and_list(monkeypatch):
    current_artist = SimpleNamespace(name="Artist A")
    updated_artist = SimpleNamespace(name="Artist A", song_count=8, album_count=2)
    fake_bootstrap = SimpleNamespace(
        library_service=SimpleNamespace(get_artist_by_name=lambda _name: updated_artist)
    )
    fake_main = SimpleNamespace(
        _artist_view=SimpleNamespace(get_artist=lambda: current_artist, set_artist=MagicMock()),
        _artists_view=SimpleNamespace(refresh=MagicMock()),
        _stacked_widget=SimpleNamespace(currentIndex=lambda: 6),
        _on_back=MagicMock(),
    )
    monkeypatch.setattr(main_window_module.Bootstrap, "instance", lambda: fake_bootstrap)

    MainWindow._refresh_current_artist_detail(fake_main)

    fake_main._artists_view.refresh.assert_called_once()
    fake_main._artist_view.set_artist.assert_called_once_with(updated_artist)
    fake_main._on_back.assert_not_called()


def test_refresh_current_artist_detail_goes_back_when_artist_removed(monkeypatch):
    current_artist = SimpleNamespace(name="Artist A")
    fake_bootstrap = SimpleNamespace(
        library_service=SimpleNamespace(get_artist_by_name=lambda _name: None)
    )
    fake_main = SimpleNamespace(
        _artist_view=SimpleNamespace(get_artist=lambda: current_artist, set_artist=MagicMock()),
        _artists_view=SimpleNamespace(refresh=MagicMock()),
        _stacked_widget=SimpleNamespace(currentIndex=lambda: 6),
        _on_back=MagicMock(),
    )
    monkeypatch.setattr(main_window_module.Bootstrap, "instance", lambda: fake_bootstrap)

    MainWindow._refresh_current_artist_detail(fake_main)

    fake_main._artists_view.refresh.assert_called_once()
    fake_main._artist_view.set_artist.assert_not_called()
    fake_main._on_back.assert_called_once()
