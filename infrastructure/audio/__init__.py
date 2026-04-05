"""
Infrastructure audio module.
"""

from .audio_backend import AudioBackend, AudioEffectsState, AudioEffectCapabilities
from .audio_engine import PlayerEngine

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
    if name == "MpvAudioBackend":
        from .mpv_backend import MpvAudioBackend

        return MpvAudioBackend
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
