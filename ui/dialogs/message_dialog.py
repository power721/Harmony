"""
Custom message dialog replacing QMessageBox for consistent theming.

Provides static methods with the same API as QMessageBox:
- information(parent, title, text)
- warning(parent, title, text)
- question(parent, title, text, buttons, default_button) -> StandardButton
- critical(parent, title, text)
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainterPath, QRegion
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QGraphicsDropShadowEffect, QWidget,
    QScrollArea,
)
# Re-export QMessageBox constants so callers can keep using QMessageBox.Yes etc.
from PySide6.QtWidgets import QMessageBox as _QMB

from system.i18n import t
from system.theme import ThemeManager
from ui.dialogs.draggable_dialog_mixin import DraggableDialogMixin
from ui.dialogs.dialog_title_bar import setup_equalizer_title_layout
from ui.icons import IconName, get_icon

Yes = _QMB.StandardButton.Yes
No = _QMB.StandardButton.No
Ok = _QMB.StandardButton.Ok
Cancel = _QMB.StandardButton.Cancel
StandardButton = _QMB.StandardButton


class MessageDialog(DraggableDialogMixin, QDialog):
    """Theme-aware frameless message dialog."""

    _STYLE_TEMPLATE = """
        QLabel#msgText {
            color: %text_secondary%;
            font-size: 13px;
            background-color: transparent;
        }
        QScrollArea {
            background-color: transparent;
            border: none;
        }
    """

    _ICON_MAP = {
        "information": IconName.INFO,
        "warning": IconName.WARNING,
        "critical": IconName.CRITICAL,
    }

    def __init__(self, parent=None, dialog_type="information"):
        super().__init__(parent)
        self._dialog_type = dialog_type
        self._result = StandardButton.Cancel
        self._drag_pos = None

        self.setWindowFlags(Qt.WindowType.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumWidth(420)
        self.setMaximumWidth(520)

        self._setup_shadow()
        self._setup_ui()
        self._apply_style()
        ThemeManager.instance().register_widget(self)

    def _setup_shadow(self):
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

    def _setup_ui(self):
        # Outer layout with 0 margins — container fills the dialog
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        container = QWidget()
        container.setObjectName("dialogContainer")
        outer.addWidget(container)

        container_layout = QVBoxLayout(container)
        layout, self._title_bar_controller = setup_equalizer_title_layout(
            self,
            container_layout,
            "",
        )

        # Icon row
        icon_row = QHBoxLayout()
        icon_row.setSpacing(10)
        self._icon_label = QLabel()
        icon_name = self._ICON_MAP.get(self._dialog_type, IconName.INFO)
        self._icon_label.setPixmap(get_icon(icon_name, None, 24).pixmap(24, 24))
        icon_row.addWidget(self._icon_label)
        icon_row.addStretch()
        layout.addLayout(icon_row)

        # Message text in scroll area
        self._text_label = QLabel()
        self._text_label.setObjectName("msgText")
        self._text_label.setWordWrap(True)
        self._text_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        scroll = QScrollArea()
        scroll.setWidget(self._text_label)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setMaximumHeight(400)
        layout.addWidget(scroll)

        layout.addStretch()

        # Button row (right-aligned)
        self._btn_layout = QHBoxLayout()
        self._btn_layout.addStretch()
        layout.addLayout(self._btn_layout)

    def _add_button(self, text, role, is_primary=False):
        btn = QPushButton(text)
        btn.setProperty("role", "primary" if is_primary else "cancel")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda checked, r=role: self._on_clicked(r))
        self._btn_layout.addWidget(btn)
        return btn

    def _on_clicked(self, role):
        self._result = role
        self.accept()

    def _apply_style(self):
        self.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TEMPLATE))

    def refresh_theme(self):
        self._apply_style()
        self._title_bar_controller.refresh_theme()
        icon_name = self._ICON_MAP.get(self._dialog_type, IconName.INFO)
        self._icon_label.setPixmap(get_icon(icon_name, None, 24).pixmap(24, 24))

    def resizeEvent(self, event):
        path = QPainterPath()
        path.addRoundedRect(self.rect(), 12, 12)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))
        super().resizeEvent(event)

    # --- Drag to move ---
    # === Static API (drop-in replacement for QMessageBox) ===

    @staticmethod
    def information(parent, title, text, buttons=Ok, default_button=Ok):
        return MessageDialog._show(parent, "information", title, text, buttons, default_button)

    @staticmethod
    def warning(parent, title, text, buttons=Ok, default_button=Ok):
        return MessageDialog._show(parent, "warning", title, text, buttons, default_button)

    @staticmethod
    def question(parent, title, text, buttons=Yes | No, default_button=Yes):
        return MessageDialog._show(parent, "question", title, text, buttons, default_button)

    @staticmethod
    def critical(parent, title, text, buttons=Ok, default_button=Ok):
        return MessageDialog._show(parent, "critical", title, text, buttons, default_button)

    @staticmethod
    def _show(parent, dialog_type, title, text, buttons, default_button):
        dialog = MessageDialog(parent, dialog_type)
        dialog._title_bar_controller.title_label.setText(title)
        dialog._text_label.setText(text)

        # Build buttons in order
        for btn_text, role in [
            (t("yes"), Yes), (t("no"), No),
            (t("ok"), Ok), (t("cancel"), Cancel),
        ]:
            if buttons & role:
                dialog._add_button(btn_text, role, is_primary=(role == default_button))

        dialog.exec()
        result = dialog._result
        dialog.deleteLater()
        return result
