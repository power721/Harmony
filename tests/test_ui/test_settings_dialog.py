from infrastructure.audio import PlayerEngine
import ui.dialogs.settings_dialog as settings_dialog


def test_audio_engine_options_exclude_qt_when_backend_unavailable(monkeypatch):
    monkeypatch.setattr(
        PlayerEngine,
        "is_backend_available",
        staticmethod(lambda backend: backend != PlayerEngine.BACKEND_QT),
    )

    options = settings_dialog._get_audio_engine_options()

    assert [value for _label, value in options] == [PlayerEngine.BACKEND_MPV]
