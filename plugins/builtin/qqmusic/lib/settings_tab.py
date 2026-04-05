from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QLabel, QPushButton, QVBoxLayout, QWidget


class QQMusicSettingsTab(QWidget):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self._context = context
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("QQ Music Settings", self))
        self._quality_combo = QComboBox(self)
        for quality in ("320", "flac", "master"):
            self._quality_combo.addItem(quality, quality)
        current_quality = str(self._context.settings.get("quality", "320"))
        for index in range(self._quality_combo.count()):
            if self._quality_combo.itemData(index) == current_quality:
                self._quality_combo.setCurrentIndex(index)
                break
        layout.addWidget(self._quality_combo)

        save_btn = QPushButton("Save", self)
        save_btn.clicked.connect(self._save)
        layout.addWidget(save_btn)

    def _save(self):
        self._context.settings.set("quality", self._quality_combo.currentData())
