"""
Infrastructure module - Technical implementations.
"""

from .audio import AudioBackend, MpvAudioBackend, PlayerEngine
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
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
