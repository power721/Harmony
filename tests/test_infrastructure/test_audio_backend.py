"""Tests for the audio backend abstraction."""

from infrastructure.audio.audio_backend import AudioBackend


class _DummyBackend(AudioBackend):
    def set_source(self, file_path: str):
        self._source = file_path

    def play(self):
        return None

    def pause(self):
        return None

    def stop(self):
        return None

    def seek(self, position_ms: int):
        self._pos = position_ms

    def position(self) -> int:
        return getattr(self, "_pos", 0)

    def duration(self) -> int:
        return 0

    def is_playing(self) -> bool:
        return False

    def is_paused(self) -> bool:
        return False

    def get_source_path(self) -> str:
        return getattr(self, "_source", "")

    def set_volume(self, volume: int):
        self._vol = volume

    def get_volume(self) -> int:
        return getattr(self, "_vol", 0)

    def set_eq_bands(self, bands: list[float]):
        self._bands = bands

    def supports_eq(self) -> bool:
        return False

    def cleanup(self):
        return None


def test_audio_backend_contract_can_be_implemented():
    backend = _DummyBackend()

    backend.set_source("/tmp/a.mp3")
    backend.seek(1234)
    backend.set_volume(55)
    backend.set_eq_bands([0.0] * 10)

    assert backend.get_source_path() == "/tmp/a.mp3"
    assert backend.position() == 1234
    assert backend.get_volume() == 55
    assert backend.supports_eq() is False
