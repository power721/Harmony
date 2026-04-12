"""
UI widgets module.
"""

from .album_card import AlbumCard
from .artist_card import ArtistCard
from .equalizer_widget import EqualizerWidget, EqualizerPreset
from .lyrics_widget_pro import LyricsWidget
from .playlist_tree_widget import PlaylistTreeWidget
from .player_controls import PlayerControls

__all__ = [
    'PlayerControls', 'LyricsWidget',
    'EqualizerWidget', 'EqualizerPreset',
    'AlbumCard', 'ArtistCard', 'PlaylistTreeWidget',
]
