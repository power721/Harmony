"""Tests for the shared cover preview dialog."""

import os

import pytest
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from system.theme import ThemeManager
from ui.dialogs.cover_preview_dialog import CoverPreviewDialog

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture(autouse=True)
def reset_theme_singleton():
    ThemeManager._instance = None
    yield
    ThemeManager._instance = None


@pytest.fixture(autouse=True)
def cleanup_widgets(qapp):
    yield
    for widget in qapp.topLevelWidgets():
        widget.close()
        widget.deleteLater()
    qapp.processEvents()


@pytest.fixture
def theme_config():
    class _Config:
        def get(self, *_args, **_kwargs):
            return "dark"

    return _Config()


def _make_png_bytes() -> bytes:
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.blue)
    ba = QByteArray()
    buffer = QBuffer(ba)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap.save(buffer, "PNG")
    buffer.close()
    return bytes(ba)


def test_cover_preview_closes_when_clicking_overlay(qapp, theme_config, tmp_path):
    ThemeManager.instance(theme_config)
    image_path = tmp_path / "cover.png"
    image_path.write_bytes(_make_png_bytes())

    dialog = CoverPreviewDialog(str(image_path), title="Album")
    dialog.show()
    qapp.processEvents()

    assert dialog.isVisible()

    QTest.mouseClick(dialog, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(5, 5))
    qapp.processEvents()

    assert not dialog.isVisible()


def test_cover_preview_closes_on_escape(qapp, theme_config, tmp_path):
    ThemeManager.instance(theme_config)
    image_path = tmp_path / "cover.png"
    image_path.write_bytes(_make_png_bytes())

    dialog = CoverPreviewDialog(str(image_path), title="Artist")
    dialog.show()
    qapp.processEvents()

    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    qapp.processEvents()

    assert not dialog.isVisible()


def test_cover_preview_drags_from_content(qapp, theme_config, tmp_path):
    ThemeManager.instance(theme_config)
    image_path = tmp_path / "cover.png"
    image_path.write_bytes(_make_png_bytes())

    dialog = CoverPreviewDialog(str(image_path), title="Genre")
    dialog.show()
    qapp.processEvents()
    dialog.move(100, 120)
    qapp.processEvents()

    content = dialog._content_frame
    start = content.rect().center()

    press = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(start),
        QPointF(content.mapToGlobal(start)),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    move = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(start + QPoint(40, 35)),
        QPointF(content.mapToGlobal(start + QPoint(40, 35))),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    release = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPointF(start + QPoint(40, 35)),
        QPointF(content.mapToGlobal(start + QPoint(40, 35))),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )

    QApplication.sendEvent(content, press)
    QApplication.sendEvent(content, move)
    QApplication.sendEvent(content, release)
    qapp.processEvents()

    assert dialog.pos() != QPoint(100, 120)


def test_cover_preview_stops_loader_on_close(qapp, theme_config, monkeypatch):
    ThemeManager.instance(theme_config)

    class _FakeLoader:
        def __init__(self):
            self.called = []

        def isRunning(self):
            return True

        def requestInterruption(self):
            self.called.append("requestInterruption")

        def quit(self):
            self.called.append("quit")

        def wait(self, timeout):
            self.called.append(("wait", timeout))
            return True

    monkeypatch.setattr(CoverPreviewDialog, "_is_url", lambda self: True)
    monkeypatch.setattr(CoverPreviewDialog, "_start_remote_load", lambda self: None)

    dialog = CoverPreviewDialog("https://example.com/cover.png", title="Online")
    dialog._loader = _FakeLoader()

    dialog.close()
    qapp.processEvents()

    assert dialog._loader.called == ["requestInterruption", "quit", ("wait", 1000)]


def test_cover_preview_close_event_ignores_missing_loader(qapp, theme_config):
    ThemeManager.instance(theme_config)

    dialog = CoverPreviewDialog("/tmp/missing-cover.png", title="Any")
    dialog._loader = None

    dialog.close()
    qapp.processEvents()

    assert not dialog.isVisible()


def test_cover_preview_window_does_not_exceed_500_pixels(qapp, theme_config, tmp_path):
    ThemeManager.instance(theme_config)

    pixmap = QPixmap(1200, 900)
    pixmap.fill(Qt.GlobalColor.blue)
    image_path = tmp_path / "large-cover.png"
    pixmap.save(str(image_path), "PNG")

    dialog = CoverPreviewDialog(str(image_path), title="Large Cover")
    dialog.show()
    qapp.processEvents()

    assert dialog.width() <= 500
    assert dialog.height() <= 500
