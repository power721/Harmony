"""Audio backend abstraction for pluggable playback engines."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


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

    def cleanup(self):
        """Release resources."""
        raise NotImplementedError
