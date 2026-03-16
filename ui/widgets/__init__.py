"""
UI widgets module.
"""

from .ai_settings_dialog import AISettingsDialog
from .album_card import AlbumCard
from .album_cover_download_dialog import AlbumCoverDownloadDialog
from .artist_card import ArtistCard
from .artist_cover_download_dialog import ArtistCoverDownloadDialog
from .base_cover_download_dialog import BaseCoverDownloadDialog
from .cloud_login_dialog import CloudLoginDialog
from .equalizer_widget import EqualizerWidget, EqualizerPreset
from .lyrics_widget_pro import LyricsWidget
from .player_controls import PlayerControls
from .track_cover_download_dialog import TrackCoverDownloadDialog, CoverDownloadDialog

__all__ = [
    'PlayerControls', 'LyricsWidget', 'CloudLoginDialog', 'AISettingsDialog',
    'EqualizerWidget', 'EqualizerPreset',
    'BaseCoverDownloadDialog', 'TrackCoverDownloadDialog', 'CoverDownloadDialog',
    'AlbumCard', 'ArtistCard', 'AlbumCoverDownloadDialog', 'ArtistCoverDownloadDialog',
]
