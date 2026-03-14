"""
UI module - PySide6 user interface components.
"""

# Windows
from .windows.main_window import MainWindow
from .windows.mini_player import MiniPlayer

# Views
from .views.library_view import LibraryView
from .views.playlist_view import PlaylistView
from .views.queue_view import QueueView
from .views.cloud_view import CloudDriveView

# Widgets
from .widgets.player_controls import PlayerControls
from .widgets.lyrics_widget_pro import LyricsWidget
from .widgets.cloud_login_dialog import CloudLoginDialog
from .widgets.equalizer_widget import EqualizerWidget, EqualizerPreset

__all__ = [
    # Windows
    'MainWindow', 'MiniPlayer',
    # Views
    'LibraryView', 'PlaylistView', 'QueueView', 'CloudDriveView',
    # Widgets
    'PlayerControls', 'LyricsWidget', 'CloudLoginDialog', 'EqualizerWidget', 'EqualizerPreset',
]
