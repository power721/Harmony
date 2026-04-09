from types import SimpleNamespace

import ui.windows.mini_player as mini_player_module
from ui.windows.mini_player import MiniPlayer


class _FakeThreadPool:
    def __init__(self):
        self.started = []

    def start(self, runnable):
        self.started.append(runnable)


def test_load_cover_async_uses_qt_thread_pool(monkeypatch):
    pool = _FakeThreadPool()

    monkeypatch.setattr(mini_player_module.QThreadPool, "globalInstance", lambda: pool)
    fake = SimpleNamespace(
        _cover_load_version=0,
        _cover_loaded=SimpleNamespace(emit=lambda *_args: None),
        _player=SimpleNamespace(
            cover_service=None,
            get_track_cover=lambda *_args, **_kwargs: None,
        ),
    )

    MiniPlayer._load_cover_async(
        fake,
        {
            "path": "",
            "title": "Song",
            "artist": "Artist",
            "album": "Album",
            "source": "Local",
            "cover_path": "",
        },
    )

    assert fake._cover_load_version == 1
    assert len(pool.started) == 1
