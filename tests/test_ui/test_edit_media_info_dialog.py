from types import SimpleNamespace
from unittest.mock import Mock

from PySide6.QtWidgets import QApplication

import ui.dialogs.edit_media_info_dialog as dialog_module
from ui.dialogs.edit_media_info_dialog import EditMediaInfoDialog
from system.theme import ThemeManager


class _FakePool:
    def __init__(self):
        self.started = []

    def start(self, runnable):
        self.started.append(runnable)


def test_edit_media_info_dialog_loads_file_details_in_background(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    _ = app

    config = Mock()
    config.get.return_value = "dark"
    ThemeManager._instance = None
    ThemeManager.instance(config)

    audio_file = tmp_path / "song.mp3"
    audio_file.write_bytes(b"demo")
    library_service = Mock()
    library_service.get_track.return_value = SimpleNamespace(
        title="Song",
        artist="Artist",
        album="Album",
        genre="Genre",
        path=str(audio_file),
    )

    pool = _FakePool()
    monkeypatch.setattr(dialog_module.QThreadPool, "globalInstance", lambda: pool)

    dialog = EditMediaInfoDialog([1], library_service)
    _ = dialog

    assert len(pool.started) == 1
