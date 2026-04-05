from __future__ import annotations

from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel

from .qr_login import QQMusicQRLogin


class QQMusicLoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._client = QQMusicQRLogin()
        self.setWindowTitle("QQ Music Login")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("QQ Music Login", self))
