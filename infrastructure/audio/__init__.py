"""
Infrastructure audio module.
"""

from .audio_backend import AudioBackend, AudioEffectsState, AudioEffectCapabilities
from .audio_engine import PlayerEngine
from .mpv_backend import MpvAudioBackend

__all__ = [
    "AudioBackend",
    "AudioEffectsState",
    "AudioEffectCapabilities",
    "QtAudioBackend",
    "MpvAudioBackend",
    "PlayerEngine",
]


def __getattr__(name: str):
    if name == "QtAudioBackend":
        from .qt_backend import QtAudioBackend

        return QtAudioBackend
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
