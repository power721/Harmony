from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

from ui.views.album_view import AlbumView


def test_album_view_default_cover_pixmap_is_cached():
    app = QApplication.instance() or QApplication([])
    _ = app  # keep Qt app alive for QPixmap creation

    AlbumView._DEFAULT_COVER_CACHE.clear()
    theme = SimpleNamespace(background_hover="#202020", text_secondary="#666666")

    first = AlbumView._get_default_cover_pixmap(theme)
    second = AlbumView._get_default_cover_pixmap(theme)

    assert first.cacheKey() == second.cacheKey()
    assert len(AlbumView._DEFAULT_COVER_CACHE) == 1
