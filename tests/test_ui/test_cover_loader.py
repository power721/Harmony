import os
from types import SimpleNamespace

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from ui.widgets.cover_loader import CoverLoader

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_cover_loader_resolves_online_cover_before_fallback():
    cover_service = SimpleNamespace(get_online_cover=lambda **_kwargs: "/tmp/online-cover.jpg")
    fallback_calls = []

    result = CoverLoader.resolve_track_cover_path(
        {
            "source": "ONLINE",
            "cloud_file_id": "song-mid",
            "artist": "Artist",
            "title": "Song",
        },
        cover_service,
        lambda *_args, **_kwargs: fallback_calls.append("fallback"),
    )

    assert result == "/tmp/online-cover.jpg"
    assert fallback_calls == []


def test_cover_loader_uses_fallback_loader_for_non_online_track():
    calls = []

    result = CoverLoader.resolve_track_cover_path(
        {
            "source": "Local",
            "path": "/tmp/song.mp3",
            "artist": "Artist",
            "title": "Song",
            "album": "Album",
        },
        None,
        lambda *args, **kwargs: calls.append((args, kwargs)) or "/tmp/fallback.jpg",
    )

    assert result == "/tmp/fallback.jpg"
    assert len(calls) == 1


def test_cover_loader_pixmap_from_bytes_scales_to_requested_size(tmp_path):
    app = QApplication.instance() or QApplication([])
    _ = app
    pixmap = QPixmap(8, 8)
    pixmap.fill(Qt.blue)
    image_path = tmp_path / "cover_loader_test.png"
    pixmap.save(str(image_path))
    image_data = image_path.read_bytes()

    scaled = CoverLoader.pixmap_from_bytes(image_data, 16, 16)

    assert scaled is not None
    assert scaled.width() == 16
    assert scaled.height() == 16


def test_cover_loader_reuses_shared_download_executor():
    first = CoverLoader.get_download_executor()
    second = CoverLoader.get_download_executor()

    assert first is second
