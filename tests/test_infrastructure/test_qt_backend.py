"""Tests for QtAudioBackend using faked Qt multimedia classes."""

from infrastructure.audio import qt_backend


class _FakeSignal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, *args):
        for callback in list(self._callbacks):
            callback(*args)


class _FakeSource:
    def __init__(self, path: str = ""):
        self._path = path

    def isValid(self):
        return bool(self._path)

    def toLocalFile(self):
        return self._path


class _FakeQAudioOutput:
    def __init__(self):
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

    def __init__(self):
        self.positionChanged = _FakeSignal()
        self.durationChanged = _FakeSignal()
        self.playbackStateChanged = _FakeSignal()
        self.mediaStatusChanged = _FakeSignal()
        self.errorOccurred = _FakeSignal()

        self._audio = None
        self._source = _FakeSource("")
        self._position = 0
        self._state = self.PlaybackState.StoppedState

    def setAudioOutput(self, audio_output):
        self._audio = audio_output

    def setSource(self, source):
        self._source = _FakeSource(source)

    def source(self):
        return self._source

    def play(self):
        self._state = self.PlaybackState.PlayingState

    def pause(self):
        self._state = self.PlaybackState.PausedState

    def stop(self):
        self._state = self.PlaybackState.StoppedState

    def setPosition(self, value: int):
        self._position = value

    def position(self):
        return self._position

    def duration(self):
        return 180000

    def playbackState(self):
        return self._state


class _FakeQUrl:
    @staticmethod
    def fromLocalFile(path: str):
        return path


def test_qt_backend_control_and_signal_mapping(monkeypatch):
    monkeypatch.setattr(qt_backend, "QMediaPlayer", _FakeQMediaPlayer)
    monkeypatch.setattr(qt_backend, "QAudioOutput", _FakeQAudioOutput)
    monkeypatch.setattr(qt_backend, "QUrl", _FakeQUrl)

    backend = qt_backend.QtAudioBackend()

    states = []
    loaded = []
    ended = []
    errors = []
    backend.state_changed.connect(states.append)
    backend.media_loaded.connect(lambda: loaded.append(True))
    backend.end_of_media.connect(lambda: ended.append(True))
    backend.error_occurred.connect(errors.append)

    backend.set_source("/tmp/song.mp3")
    backend.seek(2500)
    backend.set_volume(77)

    backend.play()
    backend.pause()
    backend.stop()

    backend._player.playbackStateChanged.emit(_FakeQMediaPlayer.PlaybackState.PlayingState)
    backend._player.playbackStateChanged.emit(_FakeQMediaPlayer.PlaybackState.PausedState)
    backend._player.playbackStateChanged.emit(_FakeQMediaPlayer.PlaybackState.StoppedState)
    backend._player.mediaStatusChanged.emit(_FakeQMediaPlayer.MediaStatus.LoadedMedia)
    backend._player.mediaStatusChanged.emit(_FakeQMediaPlayer.MediaStatus.EndOfMedia)
    backend._player.errorOccurred.emit(1, "decode error")

    assert backend.get_source_path() == "/tmp/song.mp3"
    assert backend.position() == 2500
    assert backend.duration() == 180000
    assert backend.get_volume() == 77
    assert states == [1, 2, 0]
    assert loaded == [True]
    assert ended == [True]
    assert errors == ["decode error"]
    assert backend.supports_eq() is False
    assert backend.supports_audio_effects() is False
    caps = backend.get_audio_effect_capabilities()
    assert caps.eq is False
    assert caps.bass_boost is False
    assert caps.treble_boost is False
    assert caps.reverb is False
    assert caps.stereo_enhance is False


def test_qt_backend_reports_visualizer_unsupported(monkeypatch):
    monkeypatch.setattr(qt_backend, "QMediaPlayer", _FakeQMediaPlayer)
    monkeypatch.setattr(qt_backend, "QAudioOutput", _FakeQAudioOutput)
    monkeypatch.setattr(qt_backend, "QUrl", _FakeQUrl)

    backend = qt_backend.QtAudioBackend()

    assert backend.supports_visualizer() is False
    assert hasattr(backend, "visualizer_frame")
