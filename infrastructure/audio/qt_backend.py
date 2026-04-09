"""Qt Multimedia implementation of AudioBackend."""

from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from .audio_backend import AudioBackend, AudioEffectsState, AudioEffectCapabilities


class QtAudioBackend(AudioBackend):
    """QMediaPlayer-based audio backend."""

    STATE_STOPPED = 0
    STATE_PLAYING = 1
    STATE_PAUSED = 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._source_path = ""

        self._player.positionChanged.connect(self.position_changed.emit)
        self._player.durationChanged.connect(self.duration_changed.emit)
        self._player.playbackStateChanged.connect(self._on_state_changed)
        self._player.mediaStatusChanged.connect(self._on_media_status_changed)
        self._player.errorOccurred.connect(self._on_error)

    def set_source(self, file_path: str):
        self._source_path = file_path or ""
        self._player.setSource(QUrl.fromLocalFile(self._source_path))

    def play(self):
        self._player.play()

    def pause(self):
        self._player.pause()

    def stop(self):
        self._player.stop()

    def seek(self, position_ms: int):
        self._player.setPosition(max(0, int(position_ms)))

    def position(self) -> int:
        return int(self._player.position())

    def duration(self) -> int:
        return int(self._player.duration())

    def is_playing(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def is_paused(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PausedState

    def get_source_path(self) -> str:
        return self._source_path

    def set_volume(self, volume: int):
        volume = max(0, min(100, int(volume)))
        self._audio_output.setVolume(volume / 100.0)

    def get_volume(self) -> int:
        return int(self._audio_output.volume() * 100)

    def set_eq_bands(self, bands: list[float]):
        # Qt Multimedia backend has no built-in EQ processing.
        _ = bands

    def supports_eq(self) -> bool:
        return False

    def set_audio_effects(self, effects: AudioEffectsState):
        _ = effects

    def supports_audio_effects(self) -> bool:
        return False

    def get_audio_effect_capabilities(self) -> AudioEffectCapabilities:
        return AudioEffectCapabilities.none()

    def cleanup(self):
        self._player.stop()

    def _on_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.state_changed.emit(self.STATE_PLAYING)
        elif state == QMediaPlayer.PlaybackState.PausedState:
            self.state_changed.emit(self.STATE_PAUSED)
        else:
            self.state_changed.emit(self.STATE_STOPPED)

    def _on_media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            self.media_loaded.emit()
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.end_of_media.emit()

    def _on_error(self, _error, error_string: str):
        self.error_occurred.emit(error_string)
