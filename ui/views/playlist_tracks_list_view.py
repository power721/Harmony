"""
Playlist-specific track list view.
"""

from PySide6.QtCore import Signal

from ui.views.local_tracks_list_view import LocalTracksListView
from ui.widgets.context_menus import PlaylistTrackContextMenu


class PlaylistTracksListView(LocalTracksListView):
    """List view for playlist tracks with remove-from-playlist action."""

    remove_from_playlist_requested = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent, show_index=False, show_source=True)
        self._context_menu = PlaylistTrackContextMenu(self)
        self._connect_context_menu()

    def _connect_context_menu(self):
        super()._connect_context_menu()
        if hasattr(self._context_menu, "remove_from_playlist"):
            self._context_menu.remove_from_playlist.connect(self.remove_from_playlist_requested)
