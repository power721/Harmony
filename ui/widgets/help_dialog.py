"""
Help dialog showing application info and keyboard shortcuts.
"""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QScrollArea,
    QWidget,
    QMessageBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from system.i18n import t
from app.bootstrap import Bootstrap


class HelpDialog(QDialog):
    """Dialog showing help information and keyboard shortcuts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("help"))
        self.setMinimumSize(500, 670)
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
                color: #e0e0e0;
            }
            QLabel {
                color: #e0e0e0;
            }
            QGroupBox {
                color: #1db954;
                font-weight: bold;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
            }
            QPushButton {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
                border: 1px solid #1db954;
            }
            QPushButton#rebuildBtn {
                background-color: #1db954;
                color: #000000;
                font-weight: bold;
            }
            QPushButton#rebuildBtn:hover {
                background-color: #1ed760;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

        self._setup_ui()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(15)

        # App info
        info_group = QGroupBox(t("about"))
        info_layout = QVBoxLayout(info_group)

        app_name = QLabel("Harmony")
        app_name.setStyleSheet("font-size: 24px; font-weight: bold; color: #1db954;")
        app_name.setAlignment(Qt.AlignCenter)
        info_layout.addWidget(app_name)

        version_label = QLabel("v1.0")
        version_label.setStyleSheet("font-size: 14px; color: #101010;")
        version_label.setAlignment(Qt.AlignCenter)
        info_layout.addWidget(version_label)

        desc = QLabel(t("app_description"))
        desc.setStyleSheet("font-size: 13px; color: #101010;")
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        info_layout.addWidget(desc)

        content_layout.addWidget(info_group)

        # Keyboard shortcuts
        shortcuts_group = QGroupBox(t("keyboard_shortcuts"))
        shortcuts_layout = QVBoxLayout(shortcuts_group)

        shortcuts = [
            ("Space", t("shortcut_play_pause")),
            ("Ctrl + ←", t("shortcut_prev")),
            ("Ctrl + →", t("shortcut_next")),
            ("Ctrl + ↑", t("shortcut_vol_up")),
            ("Ctrl + ↓", t("shortcut_vol_down")),
            ("Ctrl + F", t("shortcut_favorite")),
            ("Ctrl + M", t("shortcut_mini")),
            ("Ctrl + N", t("shortcut_new_playlist")),
            ("Ctrl + Q", t("shortcut_quit")),
            ("F1", t("shortcut_help")),
        ]

        for key, action in shortcuts:
            row = QHBoxLayout()
            key_label = QLabel(key)
            key_label.setStyleSheet("""
                background-color: #2a2a2a;
                padding: 4px 10px;
                border-radius: 4px;
                font-family: monospace;
                font-size: 12px;
            """)
            key_label.setFixedWidth(100)
            row.addWidget(key_label)

            action_label = QLabel(action)
            action_label.setStyleSheet("font-size: 13px; color: #101010;")
            row.addWidget(action_label)
            row.addStretch()

            shortcuts_layout.addLayout(row)

        content_layout.addWidget(shortcuts_group)

        # Tools section
        tools_group = QGroupBox(t("tools"))
        tools_layout = QVBoxLayout(tools_group)

        # Rebuild database button
        rebuild_btn = QPushButton(t("rebuild_db"))
        rebuild_btn.setObjectName("rebuildBtn")
        rebuild_btn.setCursor(Qt.PointingHandCursor)
        rebuild_btn.clicked.connect(self._rebuild_database)
        tools_layout.addWidget(rebuild_btn)

        rebuild_desc = QLabel(t("rebuild_db_desc"))
        rebuild_desc.setStyleSheet("font-size: 12px; color: #101010;")
        rebuild_desc.setWordWrap(True)
        tools_layout.addWidget(rebuild_desc)

        content_layout.addWidget(tools_group)

        content_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)

        # Close button
        close_btn = QPushButton(t("ok"))
        close_btn.clicked.connect(self.accept)
        close_btn.setFixedWidth(100)
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        close_layout.addWidget(close_btn)
        close_layout.addStretch()
        layout.addLayout(close_layout)

    def _rebuild_database(self):
        """Rebuild albums and artists tables from tracks."""
        from app.bootstrap import Bootstrap
        from PySide6.QtCore import QTimer

        bootstrap = Bootstrap.instance()
        if not bootstrap.library_service:
            return

        # Confirm with user
        reply = QMessageBox.question(
            self,
            t("rebuild_db"),
            t("rebuild_db_confirm"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Rebuild
        result = bootstrap.library_service.rebuild_albums_artists()

        # Show result
        QMessageBox.information(
            self,
            t("success"),
            t("rebuild_db_success").format(
                albums=result['albums'],
                artists=result['artists']
            )
        )
