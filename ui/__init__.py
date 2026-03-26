"""
UI module - PySide6 user interface components.
"""

from .views.cloud import CloudDriveView
# Views
from .views.library_view import LibraryView
from .views.playlist_view import PlaylistView
from .views.queue_view import QueueView
from .dialogs.cloud_login_dialog import CloudLoginDialog
from .widgets.equalizer_widget import EqualizerWidget, EqualizerPreset
from .widgets.lyrics_widget_pro import LyricsWidget
# Widgets
from .widgets.player_controls import PlayerControls
# Windows
from .windows.main_window import MainWindow
from .windows.mini_player import MiniPlayer

__all__ = [
    # Windows
    'MainWindow', 'MiniPlayer',
    # Views
    'LibraryView', 'PlaylistView', 'QueueView', 'CloudDriveView',
    # Widgets
    'PlayerControls', 'LyricsWidget', 'CloudLoginDialog', 'EqualizerWidget', 'EqualizerPreset',
]
