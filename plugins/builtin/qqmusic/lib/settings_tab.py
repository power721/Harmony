from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class QQMusicSettingsTab(QWidget):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("QQ Music Settings", self))
        self._context = context
