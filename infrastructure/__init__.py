"""
Infrastructure module - Technical implementations.
"""

from .audio import AudioBackend, PlayerEngine
from .database import DatabaseManager
from .network import HttpClient

__all__ = [
    "AudioBackend",
    "QtAudioBackend",
    "MpvAudioBackend",
    "PlayerEngine",
    "DatabaseManager",
    "HttpClient",
]


def __getattr__(name: str):
    if name == "QtAudioBackend":
        from .audio.qt_backend import QtAudioBackend

        return QtAudioBackend
    if name == "MpvAudioBackend":
        from .audio.mpv_backend import MpvAudioBackend

        return MpvAudioBackend
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
