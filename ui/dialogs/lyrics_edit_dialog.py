"""
Dialog for editing lyrics for tracks.
"""
import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainterPath, QRegion, QCursor
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QTextEdit,
    QPushButton,
    QHBoxLayout,
    QWidget,
    QGraphicsDropShadowEffect,
)

from services import LyricsService
from system.i18n import t
from system.theme import ThemeManager
from ui.dialogs.dialog_title_bar import setup_equalizer_title_layout

logger = logging.getLogger(__name__)


class LyricsEditDialog(QDialog):
    """Dialog for editing lyrics for a track with themed title bar."""

    lyrics_saved = Signal(str, str)  # Emitted when lyrics are saved (track_path, lyrics)

    _STYLE_TEMPLATE = """
        QTextEdit {
            background-color: %background%;
            color: %text%;
            border: 1px solid %border%;
            border-radius: 4px;
            padding: 10px;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 13px;
        }
    """

    def __init__(
            self,
            track_path: str,
            track_title: str,
            track_artist: str,
            parent=None
    ):
        """
        Initialize the dialog.

        Args:
            track_path: Path to the audio file
            track_title: Track title
            track_artist: Track artist
            parent: Parent widget
        """
        super().__init__(parent)
        self._track_path = track_path
        self._track_title = track_title
        self._track_artist = track_artist
        self._drag_pos = None

        # Make dialog frameless
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._setup_shadow()
        self._setup_ui()
        ThemeManager.instance().register_widget(self)

    def _setup_shadow(self):
        """Setup drop shadow effect."""
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

    def _setup_ui(self):
        """Setup the user interface."""
        self.setWindowTitle(t("edit_lyrics_title"))
        self.setMinimumSize(600, 500)
        self.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TEMPLATE))

        # Outer layout with 0 margins — container fills the dialog
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Container widget for rounded corners
        container = QWidget()
        container.setObjectName("dialogContainer")
        outer.addWidget(container)

        container_layout = QVBoxLayout(container)
        layout, self._title_bar_controller = setup_equalizer_title_layout(
            self,
            container_layout,
            t("edit_lyrics_title"),
        )

        # Track info
        info_label = QLabel(f"{self._track_title} - {self._track_artist}")
        info_label.setStyleSheet(ThemeManager.instance().get_qss(
            "color: %highlight%; font-size: 14px; padding: 5px;"
        ))
        layout.addWidget(info_label)

        # Help text
        help_label = QLabel(t("lyrics_format_help"))
        help_label.setStyleSheet(ThemeManager.instance().get_qss(
            "color: %text_secondary%; font-size: 11px;"
        ))
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

        # Text editor
        self._text_edit = QTextEdit()
        layout.addWidget(self._text_edit)

        # Load existing lyrics
        existing_lyrics = LyricsService.get_lyrics(
            self._track_path, self._track_title, self._track_artist
        )
        if existing_lyrics:
            self._text_edit.setPlainText(existing_lyrics)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton(t("cancel"))
        cancel_btn.setProperty("role", "cancel")
        cancel_btn.setCursor(QCursor(Qt.PointingHandCursor))
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton(t("save"))
        save_btn.setProperty("role", "primary")
        save_btn.setCursor(QCursor(Qt.PointingHandCursor))
        save_btn.clicked.connect(self._save_lyrics)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _save_lyrics(self):
        """Save the lyrics."""
        new_lyrics = self._text_edit.toPlainText()

        if new_lyrics.strip():
            LyricsService.save_lyrics(self._track_path, new_lyrics)
            self.lyrics_saved.emit(self._track_path, new_lyrics)
        else:
            LyricsService.delete_lyrics(self._track_path)
            self.lyrics_saved.emit(self._track_path, "")

        self.accept()

    def get_lyrics(self) -> str:
        """Get the edited lyrics."""
        return self._text_edit.toPlainText()

    def refresh_theme(self):
        """Refresh theme when changed."""
        self.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TEMPLATE))
        self._title_bar_controller.refresh_theme()

    def resizeEvent(self, event):
        """Apply rounded corner mask."""
        path = QPainterPath()
        path.addRoundedRect(self.rect(), 12, 12)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        """Handle mouse press for drag to move."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        """Handle mouse move for drag to move."""
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        """Handle mouse release."""
        self._drag_pos = None

    @staticmethod
    def show_dialog(
            track_path: str,
            track_title: str,
            track_artist: str,
            parent=None
    ) -> Optional[str]:
        """
        Static method to show the dialog and get the result.

        Args:
            track_path: Path to the audio file
            track_title: Track title
            track_artist: Track artist
            parent: Parent widget

        Returns:
            The edited lyrics text or None if cancelled
        """
        dialog = LyricsEditDialog(
            track_path, track_title, track_artist, parent
        )

        if dialog.exec() == QDialog.Accepted:
            return dialog.get_lyrics()

        return None
