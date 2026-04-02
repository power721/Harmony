"""Popup widget to display large cover art on hover."""

from PySide6.QtCore import Qt, QTimer, QRect, QPoint
from PySide6.QtGui import QColor, QPixmap, QPainter
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QApplication


class CoverHoverPopup(QWidget):
    """Popup widget to display large cover art on hover."""

    def __init__(self, parent=None, size: int = 300):
        super().__init__(parent)
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self._size = size

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._cover_label = QLabel()
        self._cover_label.setFixedSize(self._size, self._size)
        self._cover_label.setAlignment(Qt.AlignCenter)
        self._cover_label.setStyleSheet("border-radius: 8px;")
        layout.addWidget(self._cover_label)

        self._current_track_id = None
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def show_cover(self, cover_path: str | None, track_id: str, pos: QPoint):
        """Show cover at specified position."""
        if self._current_track_id == track_id and self.isVisible():
            return

        self._current_track_id = track_id

        if cover_path:
            pixmap = QPixmap(cover_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    self._size,
                    self._size,
                    Qt.KeepAspectRatioByExpanding,
                    Qt.SmoothTransformation,
                )
                self._cover_label.setPixmap(scaled)
            else:
                self._show_placeholder()
        else:
            self._show_placeholder()

        screen = QApplication.screenAt(pos)
        if not screen:
            screen = QApplication.primaryScreen()
        screen_rect = screen.availableGeometry()

        offset = 250
        x = pos.x() + offset
        y = pos.y() - self._size // 2

        if x + self._size > screen_rect.right():
            x = pos.x() - self._size - offset
        if y < screen_rect.top():
            y = screen_rect.top()
        if y + self._size > screen_rect.bottom():
            y = screen_rect.bottom() - self._size

        self.move(x, y)
        self.show()
        self._hide_timer.stop()

    def _show_placeholder(self):
        from system.theme import ThemeManager

        theme = ThemeManager.instance().current_theme

        pixmap = QPixmap(self._size, self._size)
        pixmap.fill(QColor(theme.background_alt))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QColor(theme.border))
        font = painter.font()
        font.setPixelSize(120)
        painter.setFont(font)
        painter.drawText(QRect(0, 0, self._size, self._size), Qt.AlignCenter, "♪")
        painter.end()

        self._cover_label.setPixmap(pixmap)

    def schedule_hide(self, delay_ms: int = 100):
        """Schedule hide after delay."""
        self._hide_timer.start(delay_ms)

    def cancel_hide(self):
        """Cancel scheduled hide."""
        self._hide_timer.stop()
