"""
Provider selection dialog for cloud services.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QWidget)

from system.i18n import t


class ProviderSelectDialog(QDialog):
    """Dialog for selecting cloud provider"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected_provider = None
        self._setup_ui()

    def _setup_ui(self):
        """Setup the dialog UI"""
        self.setWindowTitle(t("select_provider"))
        self.setMinimumSize(400, 250)

        # Apply dark theme styling
        self.setStyleSheet("""
            QDialog {
                background-color: #282828;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
            QPushButton {
                background-color: #3a3a3a;
                color: #ffffff;
                border: 1px solid #4a4a4a;
                border-radius: 8px;
                padding: 16px 24px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                border: 1px solid #1db954;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
        """)

        main_layout = QVBoxLayout()
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(30, 30, 30, 30)

        # Title
        title = QLabel(t("select_cloud_provider"))
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1db954;")
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        # Provider buttons
        provider_layout = QHBoxLayout()
        provider_layout.setSpacing(20)

        # Quark button
        self._quark_btn = QPushButton("夸克网盘")
        self._quark_btn.setCursor(Qt.PointingHandCursor)
        self._quark_btn.clicked.connect(lambda: self._select_provider("quark"))
        provider_layout.addWidget(self._quark_btn)

        # Baidu button
        self._baidu_btn = QPushButton("百度网盘")
        self._baidu_btn.setCursor(Qt.PointingHandCursor)
        self._baidu_btn.clicked.connect(lambda: self._select_provider("baidu"))
        provider_layout.addWidget(self._baidu_btn)

        main_layout.addLayout(provider_layout)

        # Cancel button
        cancel_layout = QHBoxLayout()
        cancel_layout.addStretch()

        cancel_btn = QPushButton(t("cancel"))
        cancel_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 24px;
                font-size: 14px;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        cancel_layout.addWidget(cancel_btn)
        cancel_layout.addStretch()

        main_layout.addLayout(cancel_layout)
        self.setLayout(main_layout)

    def _select_provider(self, provider: str):
        """Select provider and accept dialog"""
        self._selected_provider = provider
        self.accept()

    def get_selected_provider(self) -> str:
        """Get the selected provider"""
        return self._selected_provider
