"""
UI widgets module.
"""

from .player_controls import PlayerControls
from .lyrics_widget_pro import LyricsWidget
from .cloud_login_dialog import CloudLoginDialog
from .ai_settings_dialog import AISettingsDialog
from .equalizer_widget import EqualizerWidget, EqualizerPreset
from .cover_download_dialog import CoverDownloadDialog

__all__ = ['PlayerControls', 'LyricsWidget', 'CloudLoginDialog', 'AISettingsDialog', 'EqualizerWidget', 'EqualizerPreset', 'CoverDownloadDialog']
