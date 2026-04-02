"""Audio backend abstraction for pluggable playback engines."""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QObject, Signal


@dataclass
class AudioEffectCapabilities:
    """Backend capability flags for audio effects."""

    eq: bool = False
    bass_boost: bool = False
    treble_boost: bool = False
    reverb: bool = False
    stereo_enhance: bool = False

    @classmethod
    def none(cls) -> "AudioEffectCapabilities":
        return cls()

    @classmethod
    def all_supported(cls) -> "AudioEffectCapabilities":
        return cls(eq=True, bass_boost=True, treble_boost=True, reverb=True, stereo_enhance=True)


@dataclass
class AudioEffectsState:
    """Unified audio effects state."""

    enabled: bool = True
    eq_bands: list[float] = field(default_factory=list)
    bass_boost: float = 0.0
    treble_boost: float = 0.0
    reverb_level: float = 0.0
    stereo_enhance: float = 0.0


class AudioBackend(QObject):
    """Abstract audio backend interface."""

    # Signals
    position_changed = Signal(int)
    duration_changed = Signal(int)
    state_changed = Signal(int)  # 0=stopped, 1=playing, 2=paused
    media_loaded = Signal()
    end_of_media = Signal()
    error_occurred = Signal(str)

    def set_source(self, file_path: str):
        """Set playback source from local file path."""
        raise NotImplementedError

    def play(self):
        """Start or resume playback."""
        raise NotImplementedError

    def pause(self):
        """Pause playback."""
        raise NotImplementedError

    def stop(self):
        """Stop playback."""
        raise NotImplementedError

    def seek(self, position_ms: int):
        """Seek to position (ms)."""
        raise NotImplementedError

    def position(self) -> int:
        """Current position in milliseconds."""
        raise NotImplementedError

    def duration(self) -> int:
        """Duration in milliseconds."""
        raise NotImplementedError

    def is_playing(self) -> bool:
        """Whether backend is currently playing."""
        raise NotImplementedError

    def is_paused(self) -> bool:
        """Whether backend is currently paused."""
        raise NotImplementedError

    def get_source_path(self) -> str:
        """Get current source local path."""
        raise NotImplementedError

    def set_volume(self, volume: int):
        """Set volume 0-100."""
        raise NotImplementedError

    def get_volume(self) -> int:
        """Get volume 0-100."""
        raise NotImplementedError

    def set_eq_bands(self, bands: list[float]):
        """Apply EQ gains in dB for backend-defined bands."""
        raise NotImplementedError

    def supports_eq(self) -> bool:
        """Whether backend supports EQ."""
        raise NotImplementedError

    def set_audio_effects(self, effects: AudioEffectsState):
        """Apply advanced audio effects state."""
        raise NotImplementedError

    def supports_audio_effects(self) -> bool:
        """Whether backend supports advanced audio effects."""
        raise NotImplementedError

    def get_audio_effect_capabilities(self) -> AudioEffectCapabilities:
        """Get backend support matrix for effect controls."""
        raise NotImplementedError

    def cleanup(self):
        """Release resources."""
        raise NotImplementedError
