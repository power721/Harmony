"""
QQ Music login dialog.
Provides QR code login for QQ Music credentials.
"""
import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QMessageBox
)
from PySide6.QtCore import Qt, Signal

from system.i18n import t

logger = logging.getLogger(__name__)


class QQMusicLoginDialog(QDialog):
    """Dialog for QQ Music QR code login."""

    # Signal emitted when credentials are successfully set
    credentials_updated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("qqmusic_login_title"))
        self.setMinimumWidth(400)

        from app.bootstrap import Bootstrap
        self.config = Bootstrap.instance().config

        self._setup_ui()

    def _setup_ui(self):
        """Setup the UI."""
        self._apply_dark_style()

        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(24, 24, 24, 24)

        # Title
        title = QLabel(f"<h2>{t('qqmusic_login')}</h2>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Status
        self._status_label = QLabel()
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setWordWrap(True)
        self._update_status()
        layout.addWidget(self._status_label)

        # Instructions
        instructions = QLabel(t("qqmusic_login_instructions"))
        instructions.setAlignment(Qt.AlignCenter)
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #a0a0a0; font-size: 12px;")
        layout.addWidget(instructions)

        # Buttons
        button_layout = QHBoxLayout()

        self.qr_login_button = QPushButton(t("qqmusic_qr_login"))
        self.qr_login_button.clicked.connect(self._open_qr_login)
        button_layout.addWidget(self.qr_login_button)

        self.clear_button = QPushButton(t("qqmusic_clear"))
        self.clear_button.clicked.connect(self._clear_credentials)
        button_layout.addWidget(self.clear_button)

        self.close_button = QPushButton(t("close"))
        self.close_button.clicked.connect(self.reject)
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)

    def _apply_dark_style(self):
        """Apply dark theme style."""
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
                border-radius: 4px;
                padding: 10px 24px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                border: 1px solid #1db954;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
        """)

    def _update_status(self):
        """Update credential status label."""
        credential = self.config.get_qqmusic_credential()

        if credential and credential.get('musicid') and credential.get('musickey'):
            musicid = credential.get('musicid', '')
            login_type = credential.get('login_type', 2)
            login_method = t("qqmusic_wx_login") if login_type == 3 else t("qqmusic_qq_login")
            self._status_label.setText(
                f"<span style='color: #1db954;'>✓ {t('qqmusic_logged_in')}</span><br>"
                f"<span style='color: #a0a0a0; font-size: 12px;'>ID: {musicid} ({login_method})</span>"
            )
            self._status_label.setStyleSheet("font-size: 14px;")
        else:
            self._status_label.setText(
                f"<span style='color: #ff6b6b;'>✗ {t('qqmusic_not_logged_in')}</span>"
            )
            self._status_label.setStyleSheet("font-size: 14px;")

    def _open_qr_login(self):
        """Open QR code login dialog."""
        from ui.dialogs import QQMusicQRLoginDialog

        qr_dialog = QQMusicQRLoginDialog(self)
        qr_dialog.credentials_obtained.connect(self._on_credentials_obtained)
        qr_dialog.exec_()

    def _on_credentials_obtained(self, credential: dict):
        """Handle credentials obtained from QR login."""
        self._update_status()
        self.credentials_updated.emit()

    def _clear_credentials(self):
        """Clear stored credentials."""
        credential = self.config.get_qqmusic_credential()
        if not credential or not credential.get('musicid'):
            QMessageBox.information(self, t("info"), t("qqmusic_no_credentials"))
            return

        reply = QMessageBox.question(
            self,
            t("qqmusic_clear"),
            t("qqmusic_clear_confirm"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                self.config.clear_qqmusic_credential()

                # Refresh QQ Music client (will have no credentials)
                Bootstrap.instance().refresh_qqmusic_client()

                self._update_status()
                QMessageBox.information(self, t("success"), t("qqmusic_cleared"))
                self.credentials_updated.emit()
            except Exception as e:
                logger.error(f"Failed to clear QQ Music credentials: {e}")
                QMessageBox.warning(
                    self,
                    t("error"),
                    f"{t('error')}:\n{str(e)}"
                )
