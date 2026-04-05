from __future__ import annotations

from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel


class QQMusicLoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("QQ Music Login", self))
