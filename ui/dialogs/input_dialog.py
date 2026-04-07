from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainterPath, QRegion
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QDialog,
    QLabel,
    QGraphicsDropShadowEffect,
)

from system.i18n import t
from system.theme import ThemeManager
from ui.dialogs.dialog_title_bar import setup_equalizer_title_layout


class InputDialog(QDialog):
    """Custom input dialog with dark theme styling and frameless window."""

    def __init__(self, title: str, label: str, text: str = "", parent=None):
        super().__init__(parent)
        self._drag_pos = None

        self.setWindowFlags(Qt.WindowType.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setProperty("shell", True)
        self.setFixedSize(380, 200)
        self.setWindowTitle(title)

        self._setup_shadow()
        self._setup_ui(title, label, text)
        self._apply_style()
        ThemeManager.instance().register_widget(self)

    def _setup_shadow(self):
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

    def _setup_ui(self, title, label, text):
        container = QWidget(self)
        container.setObjectName("dialogContainer")
        container.setGeometry(0, 0, 380, 200)

        container_layout = QVBoxLayout(container)
        layout, self._title_bar_controller = setup_equalizer_title_layout(
            self,
            container_layout,
            title,
        )

        # Label
        label_widget = QLabel(label)
        label_widget.setObjectName("dialogLabel")
        layout.addWidget(label_widget)

        # Input
        self._input = QLineEdit()
        self._input.setText(text)
        self._input.selectAll()
        layout.addWidget(self._input)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton(t("cancel"))
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_layout.addWidget(cancel_btn)

        ok_btn = QPushButton(t("ok"))
        ok_btn.setProperty("role", "primary")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_layout.addWidget(ok_btn)

        layout.addLayout(btn_layout)

    def _apply_style(self):
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)

    def refresh_theme(self):
        self._apply_style()
        self._title_bar_controller.refresh_theme()

    def resizeEvent(self, event):
        path = QPainterPath()
        path.addRoundedRect(self.rect(), 12, 12)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def get_text(self) -> str:
        """Get the input text."""
        return self._input.text().strip()

    @staticmethod
    def getText(parent, title: str, label: str, text: str = "") -> tuple:
        """
        Static method to get text from user.
        Returns (text, accepted) tuple similar to QInputDialog.getText.
        """
        dialog = InputDialog(title, label, text, parent)
        result = dialog.exec()
        return dialog.get_text(), result == QDialog.Accepted
