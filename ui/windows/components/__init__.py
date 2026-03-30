"""
MainWindow components module.
"""

from .lyrics_panel import LyricsPanel, LyricsController
from .online_music_handler import OnlineMusicHandler
from .scan_dialog import ScanDialog, ScanWorker
from .sidebar import Sidebar

__all__ = [
    "Sidebar",
    "LyricsPanel",
    "LyricsController",
    "OnlineMusicHandler",
    "ScanDialog",
    "ScanWorker",
]
