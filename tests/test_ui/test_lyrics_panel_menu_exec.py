from types import SimpleNamespace

from ui.windows.components.lyrics_panel import LyricsPanel


class _FakeSignal:
    def connect(self, _callback):
        return None


class _FakeAction:
    def __init__(self):
        self.triggered = _FakeSignal()


class _FakeMenu:
    def __init__(self, _parent):
        self.exec_called = False
        self.exec_legacy_called = False

    def setStyleSheet(self, _style):
        return None

    def addAction(self, _label):
        return _FakeAction()

    def addSeparator(self):
        return None

    def exec(self, _pos):
        self.exec_called = True

    def exec_(self, _pos):
        self.exec_legacy_called = True
        raise AssertionError("exec_ should not be used")


def test_lyrics_panel_context_menu_uses_exec(monkeypatch):
    fake_menu = _FakeMenu(None)

    monkeypatch.setattr("ui.windows.components.lyrics_panel.QMenu", lambda parent: fake_menu)
    monkeypatch.setattr(
        "system.theme.ThemeManager.instance",
        lambda: SimpleNamespace(get_qss=lambda template: template),
    )
    monkeypatch.setattr("ui.windows.components.lyrics_panel.t", lambda key: key)

    panel = SimpleNamespace(
        _MENU_STYLE="style",
        _lyrics_view=SimpleNamespace(mapToGlobal=lambda pos: pos),
        download_requested=object(),
        edit_requested=object(),
        delete_requested=object(),
        open_location_requested=object(),
        refresh_requested=object(),
    )

    LyricsPanel._show_context_menu(panel, (10, 20))

    assert fake_menu.exec_called is True
