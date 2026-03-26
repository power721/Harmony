"""
MainWindow components module.
"""

from .sidebar import Sidebar
from .lyrics_panel import LyricsPanel, LyricsController
from .online_music_handler import OnlineMusicHandler
from .scan_dialog import ScanDialog, ScanWorker

__all__ = [
    "Sidebar",
    "LyricsPanel",
    "LyricsController",
    "OnlineMusicHandler",
    "ScanDialog",
    "ScanWorker",
]
