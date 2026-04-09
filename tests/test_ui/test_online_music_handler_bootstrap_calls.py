from types import SimpleNamespace

from ui.windows.components.online_music_handler import OnlineMusicHandler


def test_add_multiple_to_queue_resolves_bootstrap_once(monkeypatch):
    call_count = 0
    library_service = SimpleNamespace(add_online_track=lambda **_kwargs: 1)
    bootstrap = SimpleNamespace(library_service=library_service)

    def fake_instance():
        nonlocal call_count
        call_count += 1
        return bootstrap

    monkeypatch.setattr("app.bootstrap.Bootstrap.instance", fake_instance)

    handler = OnlineMusicHandler.__new__(OnlineMusicHandler)
    handler._download_service = None
    handler._status_callback = None
    handler._show_status = lambda _message: None
    handler._resolve_provider_id = OnlineMusicHandler._resolve_provider_id
    handler._playback = SimpleNamespace(
        engine=SimpleNamespace(add_track=lambda _item: None),
        save_queue=lambda: None,
    )

    OnlineMusicHandler.add_multiple_to_queue(
        handler,
        [
            ("mid-1", {"title": "Song 1"}),
            ("mid-2", {"title": "Song 2"}),
        ],
    )

    assert call_count == 1
