from unittest.mock import Mock

import services.playback.playback_service as playback_service


def test_resolve_audio_engine_backend_falls_back_to_mpv_when_qt_unavailable(monkeypatch):
    config = Mock()
    config.get_audio_engine.return_value = "qt"

    monkeypatch.setattr(
        playback_service.PlayerEngine,
        "is_backend_available",
        staticmethod(lambda backend: backend != playback_service.PlayerEngine.BACKEND_QT),
    )

    backend = playback_service._resolve_audio_engine_backend(config)

    assert backend == playback_service.PlayerEngine.BACKEND_MPV

