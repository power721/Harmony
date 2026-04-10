from pathlib import Path

import ui.icons as icons_module


class _FakeRenderer:
    def __init__(self, _svg_content):
        pass

    def render(self, _painter):
        return None


class _FakePixmap:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.filled = None

    def fill(self, value):
        self.filled = value


class _FakePainter:
    def __init__(self, _pixmap):
        self.ended = False

    def end(self):
        self.ended = True


class _FakeIcon:
    def __init__(self, payload=None):
        self.payload = payload


def test_icon_cache_uses_tuple_keys(monkeypatch, tmp_path):
    icon_file = tmp_path / "play.svg"
    icon_file.write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>', encoding="utf-8")

    monkeypatch.setattr(icons_module, "ICONS_DIR", tmp_path)
    monkeypatch.setattr(icons_module, "QSvgRenderer", _FakeRenderer)
    monkeypatch.setattr(icons_module, "QPixmap", _FakePixmap)
    monkeypatch.setattr(icons_module, "QPainter", _FakePainter)
    monkeypatch.setattr(icons_module, "QIcon", _FakeIcon)
    monkeypatch.setattr(icons_module, "_ICON_CACHE", {})
    monkeypatch.setattr(icons_module, "_PATH_ICON_CACHE", {})

    icon = icons_module.get_icon("play.svg", "#ffffff", 24)
    same_icon = icons_module.get_icon("play.svg", "#ffffff", 24)

    assert icon is same_icon
    assert list(icons_module._ICON_CACHE.keys()) == [("play.svg", "#ffffff", 24)]


def test_path_icon_cache_uses_tuple_keys(monkeypatch, tmp_path):
    icon_file = tmp_path / "play.svg"
    icon_file.write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>', encoding="utf-8")

    monkeypatch.setattr(icons_module, "QSvgRenderer", _FakeRenderer)
    monkeypatch.setattr(icons_module, "QPixmap", _FakePixmap)
    monkeypatch.setattr(icons_module, "QPainter", _FakePainter)
    monkeypatch.setattr(icons_module, "QIcon", _FakeIcon)
    monkeypatch.setattr(icons_module, "_PATH_ICON_CACHE", {})

    icon = icons_module.get_icon_from_path(str(icon_file), "#ffffff", 24)
    same_icon = icons_module.get_icon_from_path(str(icon_file), "#ffffff", 24)

    assert icon is same_icon
    assert list(icons_module._PATH_ICON_CACHE.keys()) == [(str(icon_file), "#ffffff", 24)]
