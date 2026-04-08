"""Regression tests for QtAudioBackend QObject parenting."""

from infrastructure.audio import qt_backend


class _FakeSignal:
    def connect(self, _callback):
        return None


class _FakeQAudioOutput:
    def __init__(self, parent=None):
        self.parent = parent
        self._volume = 0.0

    def setVolume(self, value: float):
        self._volume = value

    def volume(self) -> float:
        return self._volume


class _FakeQMediaPlayer:
    class PlaybackState:
        PlayingState = 1
        PausedState = 2
        StoppedState = 0

    class MediaStatus:
        LoadedMedia = 7
        EndOfMedia = 6

    def __init__(self, parent=None):
        self.parent = parent
        self.positionChanged = _FakeSignal()
        self.durationChanged = _FakeSignal()
        self.playbackStateChanged = _FakeSignal()
        self.mediaStatusChanged = _FakeSignal()
        self.errorOccurred = _FakeSignal()

    def setAudioOutput(self, _audio_output):
        return None


def test_qt_backend_parents_qt_multimedia_objects(monkeypatch):
    monkeypatch.setattr(qt_backend, "QMediaPlayer", _FakeQMediaPlayer)
    monkeypatch.setattr(qt_backend, "QAudioOutput", _FakeQAudioOutput)

    backend = qt_backend.QtAudioBackend()

    assert backend._player.parent is backend
    assert backend._audio_output.parent is backend
