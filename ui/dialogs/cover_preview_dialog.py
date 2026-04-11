"""Shared frameless cover preview dialog."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QFrame, QLabel, QVBoxLayout

from infrastructure.cache.image_cache import ImageCache
from infrastructure.network.http_client import HttpClient
from system.i18n import t
from system.theme import ThemeManager

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
    """Frameless cover preview with outside-click close and drag-to-move."""

    MAX_WINDOW_WIDTH = 500
    MAX_WINDOW_HEIGHT = 500
    OUTER_MARGIN = 24

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

    def _build_ui(self):
        """Create overlay and centered content frame."""
        theme = ThemeManager.instance().current_theme

        self.setStyleSheet(
            f"QDialog {{ background-color: rgba(0, 0, 0, 180); }}"
            f"QFrame#coverPreviewContent {{ background-color: {theme.background_alt}; border-radius: 12px; }}"
            f"QLabel {{ color: {theme.text_secondary}; background-color: transparent; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            self.OUTER_MARGIN,
            self.OUTER_MARGIN,
            self.OUTER_MARGIN,
            self.OUTER_MARGIN,
        )

        self._content_frame = QFrame(self)
        self._content_frame.setObjectName("coverPreviewContent")
        self._content_frame.setMinimumSize(200, 200)

        content_layout = QVBoxLayout(self._content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)

        self._image_label = QLabel(t("loading"))
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self._image_label)

        layout.addWidget(self._content_frame, 0, Qt.AlignmentFlag.AlignCenter)

        self._content_frame.mousePressEvent = self._on_content_press
        self._content_frame.mouseMoveEvent = self._on_content_move
        self._content_frame.mouseReleaseEvent = self._on_content_release

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
        """Scale the pixmap to the available screen size and display it."""
        max_content_width = self.MAX_WINDOW_WIDTH - (self.OUTER_MARGIN * 2)
        max_content_height = self.MAX_WINDOW_HEIGHT - (self.OUTER_MARGIN * 2)
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

    def _on_content_press(self, event):
        """Record the initial drag offset when dragging starts."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def _on_content_move(self, event):
        """Move the dialog while the image container is being dragged."""
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def _on_content_release(self, event):
        """Clear drag state after releasing the mouse."""
        self._drag_pos = None
        event.accept()

    def mousePressEvent(self, event):
        """Close when clicking the overlay outside the content frame."""
        if event.button() == Qt.MouseButton.LeftButton:
            if not self._content_frame.geometry().contains(event.position().toPoint()):
                self.close()
                return
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        """Close the preview on Escape."""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

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
    dialog = CoverPreviewDialog(
        image_source=image_source,
        title=title,
        request_headers=request_headers,
        parent=parent,
    )
    dialog.show()
    return dialog
