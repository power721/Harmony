from types import SimpleNamespace

from ui.windows.now_playing_window import NowPlayingWindow


class _FakeDialog:
    def __init__(self, _parent):
        self.exec_called = False
        self.delete_later_called = False

    def setWindowTitle(self, _title):
        return None

    def setWindowFlags(self, _flags):
        return None

    def resize(self, _width, _height):
        return None

    def setStyleSheet(self, _style):
        return None

    def reject(self):
        return None

    def accept(self):
        return None

    def exec(self):
        self.exec_called = True

    def deleteLater(self):
        self.delete_later_called = True


class _FakeLayout:
    def __init__(self, *_args, **_kwargs):
        return None

    def setContentsMargins(self, *_args):
        return None

    def addStretch(self):
        return None

    def addWidget(self, _widget):
        return None

    def addLayout(self, _layout):
        return None


class _FakeButton:
    def __init__(self, *_args, **_kwargs):
        self.clicked = SimpleNamespace(connect=lambda _callback: None)

    def setObjectName(self, _name):
        return None

    def setFixedSize(self, _w, _h):
        return None

    def setCursor(self, _cursor):
        return None

    def setIcon(self, _icon):
        return None

    def setIconSize(self, _size):
        return None


class _FakeListWidget:
    PositionAtCenter = object()

    def __init__(self, *_args, **_kwargs):
        self.itemDoubleClicked = SimpleNamespace(connect=lambda _callback: None)

    def setCursor(self, _cursor):
        return None

    def addItem(self, _item):
        return None

    def count(self):
        return 0


class _FakeListItem:
    def __init__(self, _text):
        return None

    def setData(self, *_args):
        return None

    def setTextAlignment(self, *_args):
        return None


def test_show_playlist_dialog_deletes_dialog_after_exec(monkeypatch):
    fake_dialog = _FakeDialog(None)

    monkeypatch.setattr("ui.windows.now_playing_window.QDialog", lambda parent: fake_dialog)
    monkeypatch.setattr("ui.windows.now_playing_window.QVBoxLayout", _FakeLayout)
    monkeypatch.setattr("ui.windows.now_playing_window.QHBoxLayout", _FakeLayout)
    monkeypatch.setattr("ui.windows.now_playing_window.QPushButton", _FakeButton)
    monkeypatch.setattr("ui.windows.now_playing_window.QListWidget", _FakeListWidget)
    monkeypatch.setattr("ui.windows.now_playing_window.QListWidgetItem", _FakeListItem)
    monkeypatch.setattr(
        "system.theme.ThemeManager.instance",
        lambda: SimpleNamespace(get_qss=lambda template: template, current_theme=SimpleNamespace(highlight="#fff")),
    )
    monkeypatch.setattr("ui.windows.now_playing_window.get_icon", lambda *_args, **_kwargs: object())
    monkeypatch.setattr("ui.windows.now_playing_window.t", lambda key: key)

    fake_window = SimpleNamespace(
        _STYLE_QUEUE_DIALOG="style",
        _playback=SimpleNamespace(
            engine=SimpleNamespace(
                playlist_items=[],
                current_index=-1,
                play_at=lambda _index: None,
            )
        ),
    )

    NowPlayingWindow._show_playlist_dialog(fake_window)

    assert fake_dialog.exec_called is True
    assert fake_dialog.delete_later_called is True
