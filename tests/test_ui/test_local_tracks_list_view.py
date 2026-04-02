"""
Smoke tests for LocalTracksListView helper methods used by LibraryView.
"""

import os
from unittest.mock import MagicMock, PropertyMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from domain.track import Track, TrackSource
from ui.views.local_tracks_list_view import LocalTracksListView


def test_local_tracks_list_view_supports_append_and_track_selection():
    """Paged loading helpers should preserve row lookup and selection by track ID."""
    app = QApplication.instance() or QApplication([])
    theme_manager = MagicMock()
    theme = MagicMock()
    theme.background = "#101010"
    theme.background_alt = "#1a1a1a"
    theme.background_hover = "#202020"
    theme.text = "#ffffff"
    theme.text_secondary = "#b3b3b3"
    theme.highlight = "#1db954"
    theme.border = "#404040"
    type(theme_manager).current_theme = PropertyMock(return_value=theme)

    with patch("system.theme.ThemeManager.instance", return_value=theme_manager):
        view = LocalTracksListView()
        view.show()
        app.processEvents()

        first_page = [
            Track(id=1, path="/music/1.mp3", title="One", source=TrackSource.LOCAL),
            Track(id=2, path="/music/2.mp3", title="Two", source=TrackSource.LOCAL),
        ]
        next_page = [
            Track(id=3, path="/music/3.mp3", title="Three", source=TrackSource.LOCAL),
        ]

        view.load_tracks(first_page, favorite_ids=set())
        view.append_tracks(next_page)

        assert view.row_count() == 3
        assert view.select_track_by_id(3) is True
        app.processEvents()
        assert [track.id for track in view.selected_tracks()] == [3]
