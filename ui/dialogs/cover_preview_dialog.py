"""Shared cover preview dialog with a themed title bar."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QFrame, QLabel, QVBoxLayout, QWidget

from infrastructure.cache.image_cache import ImageCache
from infrastructure.network.http_client import HttpClient
from system.i18n import t
from system.theme import ThemeManager
from ui.dialogs.dialog_title_bar import setup_equalizer_title_layout

logger = logging.getLogger(__name__)


class CoverPreviewLoader(QThread):
    """Load remote cover bytes without blocking the UI thread."""

    loaded = Signal(bytes)
    failed = Signal()

    def __init__(self, url: str, headers: dict | None = None):
        super().__init__()
        self._url = url
        self._headers = headers

    def run(self):
        """Fetch image bytes from cache or network."""
        cached = ImageCache.get(self._url)
        if cached:
            self.loaded.emit(cached)
            return

        data = HttpClient().get_content(self._url, headers=self._headers, timeout=10)
        if not data:
            self.failed.emit()
            return

        ImageCache.set(self._url, data)
        self.loaded.emit(data)


class CoverPreviewDialog(QDialog):
    """Frameless cover preview with shared title bar chrome."""

    MAX_WINDOW_WIDTH = 800
    MAX_WINDOW_HEIGHT = 800
    CONTENT_MARGINS = (24, 20, 24, 24)
    MAX_CONTENT_HEIGHT_PADDING = 120

    def __init__(
        self,
        image_source: str,
        title: str = "",
        request_headers: dict | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._image_source = image_source
        self._request_headers = request_headers
        self._loader: CoverPreviewLoader | None = None
        self._drag_pos = None

        self.setWindowTitle(title or t("cover"))
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMaximumSize(self.MAX_WINDOW_WIDTH, self.MAX_WINDOW_HEIGHT)
        self.resize(self.MAX_WINDOW_WIDTH, self.MAX_WINDOW_HEIGHT)

        self._build_ui()
        self._load_image()
        ThemeManager.instance().register_widget(self)

    def _build_ui(self):
        """Create the shared title-bar layout and centered image area."""
        theme = ThemeManager.instance().current_theme

        self.setStyleSheet(
            f"QFrame#coverPreviewContent {{ background-color: transparent; }}"
            f"QLabel#coverPreviewImage {{ color: {theme.text_secondary}; background-color: transparent; }}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        container = QWidget(self)
        container.setObjectName("dialogContainer")
        outer.addWidget(container)

        container_layout = QVBoxLayout(container)
        self._content_layout, self._title_bar_controller = setup_equalizer_title_layout(
            self,
            container_layout,
            self.windowTitle(),
            content_margins=self.CONTENT_MARGINS,
            content_spacing=0,
        )

        self._content_frame = QFrame(container)
        self._content_frame.setObjectName("coverPreviewContent")

        content_layout = QVBoxLayout(self._content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)

        self._image_label = QLabel(t("loading"))
        self._image_label.setObjectName("coverPreviewImage")
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self._image_label)

        self._content_layout.addWidget(self._content_frame, 0, Qt.AlignmentFlag.AlignCenter)

    def _is_url(self) -> bool:
        """Return whether the source should be fetched remotely."""
        return self._image_source.startswith(("http://", "https://"))

    def _load_image(self):
        """Load local or remote image into the preview."""
        if self._is_url():
            self._start_remote_load()
            return

        pixmap = QPixmap(str(Path(self._image_source)))
        if pixmap.isNull():
            self._image_label.setText(t("cover_load_failed"))
            return
        self._set_pixmap(pixmap)

    def _start_remote_load(self):
        """Start the remote loader thread."""
        self._loader = CoverPreviewLoader(self._image_source, headers=self._request_headers)
        self._loader.loaded.connect(self._on_remote_loaded)
        self._loader.failed.connect(self._on_remote_failed)
        self._loader.start()

    def _on_remote_loaded(self, data: bytes):
        """Decode the loaded remote image bytes."""
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            self._on_remote_failed()
            return
        self._set_pixmap(pixmap)

    def _on_remote_failed(self):
        """Show a failure state when the remote image could not be loaded."""
        self._image_label.setText(t("cover_load_failed"))

    def _set_pixmap(self, pixmap: QPixmap):
        """Scale the pixmap to the dialog bounds and display it."""
        horizontal_padding = self.CONTENT_MARGINS[0] + self.CONTENT_MARGINS[2]
        max_content_width = self.MAX_WINDOW_WIDTH - horizontal_padding
        max_content_height = self.MAX_WINDOW_HEIGHT - self.MAX_CONTENT_HEIGHT_PADDING
        scaled = pixmap.scaled(
            max(1, max_content_width),
            max(1, max_content_height),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._image_label.setText("")
        self._image_label.setPixmap(scaled)
        self._content_frame.setFixedSize(scaled.size())
        self.adjustSize()
        self.setFixedSize(
            min(self.width(), self.MAX_WINDOW_WIDTH),
            min(self.height(), self.MAX_WINDOW_HEIGHT),
        )

    def keyPressEvent(self, event):
        """Close the preview on Escape."""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    def refresh_theme(self):
        """Refresh dialog styling after a theme change."""
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)
        self._title_bar_controller.refresh_theme()

    def closeEvent(self, event):
        """Stop any running loader thread before closing."""
        if self._loader and self._loader.isRunning():
            self._loader.requestInterruption()
            self._loader.quit()
            self._loader.wait(1000)
        super().closeEvent(event)


def show_cover_preview(
    parent,
    image_source: str,
    title: str = "",
    request_headers: dict | None = None,
):
    """Show a shared cover preview dialog and return it for lifecycle tracking."""
    dialog_parent = parent
    if parent is not None:
        window_getter = getattr(parent, "window", None)
        if callable(window_getter):
            top_level_parent = window_getter()
            if top_level_parent is not None:
                dialog_parent = top_level_parent

    dialog = CoverPreviewDialog(
        image_source=image_source,
        title=title,
        request_headers=request_headers,
        parent=dialog_parent,
    )
    dialog.show()
    return dialog
