from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QLabel, QPushButton, QVBoxLayout, QWidget

from .login_dialog import QQMusicLoginDialog


class QQMusicSettingsTab(QWidget):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self._context = context
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("QQ Music Settings", self))
        self._status_label = QLabel(self)
        self._status_label.setText(self._build_status_text())
        layout.addWidget(self._status_label)
        self._quality_combo = QComboBox(self)
        for quality in ("320", "flac", "master"):
            self._quality_combo.addItem(quality, quality)
        current_quality = str(self._context.settings.get("quality", "320"))
        for index in range(self._quality_combo.count()):
            if self._quality_combo.itemData(index) == current_quality:
                self._quality_combo.setCurrentIndex(index)
                break
        layout.addWidget(self._quality_combo)

        login_btn = QPushButton("Login", self)
        login_btn.clicked.connect(self._open_login_dialog)
        layout.addWidget(login_btn)

        clear_btn = QPushButton("Clear Credentials", self)
        clear_btn.clicked.connect(self._clear_credentials)
        layout.addWidget(clear_btn)

        save_btn = QPushButton("Save", self)
        save_btn.clicked.connect(self._save)
        layout.addWidget(save_btn)

    def _save(self):
        self._context.settings.set("quality", self._quality_combo.currentData())

    def _open_login_dialog(self):
        dialog = QQMusicLoginDialog(self)
        dialog.exec()

    def _clear_credentials(self):
        self._context.settings.set("credential", None)
        self._context.settings.set("nick", "")
        self._status_label.setText(self._build_status_text())

    def _build_status_text(self) -> str:
        nick = self._context.settings.get("nick", "")
        if nick:
            return f"Logged in as {nick}"
        return "Not logged in"
