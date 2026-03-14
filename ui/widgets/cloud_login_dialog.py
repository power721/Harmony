"""
Cloud login dialog for QR code authentication.
"""
import logging

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QProgressBar)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
import qrcode
from io import BytesIO
from services.cloud.quark_service import QuarkDriveService
from system.i18n import t

# Configure logging
logger = logging.getLogger(__name__)


class CloudLoginDialog(QDialog):
    """Dialog for QR code login to cloud services"""

    login_success = Signal(dict)  # Emits account info on success

    def __init__(self, parent=None):
        super().__init__(parent)
        self._qr_token = None
        self._qr_url = None  # Store QR URL for redisplay
        self._poll_timer = QTimer(self)
        self._poll_attempts = 0
        self._setup_ui()
        self._start_login_flow()

    def _setup_ui(self):
        """Setup the dialog UI"""
        self.setWindowTitle(t("cloud_drive") + " " + t("login"))
        self.setMinimumSize(400, 500)

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
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
            QProgressBar {
                background-color: #3a3a3a;
                border: 1px solid #4a4a4a;
                border-radius: 4px;
                text-align: center;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #1db954;
                border-radius: 3px;
            }
        """)

        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # Title
        title = QLabel(t("scan_qr_code"))
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1db954;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # QR Code placeholder
        self._qr_label = QLabel()
        self._qr_label.setMinimumSize(250, 250)
        self._qr_label.setMaximumSize(250, 250)
        self._qr_label.setAlignment(Qt.AlignCenter)
        self._qr_label.setScaledContents(False)  # Don't auto-scale, we'll do it manually
        self._qr_label.setStyleSheet("border: 2px solid #404040; border-radius: 8px; background: white;")
        layout.addWidget(self._qr_label)

        # Status label
        self._status_label = QLabel(t("generating_qr"))
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet("color: #a0a0a0;")
        layout.addWidget(self._status_label)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setMaximum(30)  # 30 ticks = 60 seconds (2s per tick)
        self._progress.setValue(0)
        layout.addWidget(self._progress)

        # Buttons
        button_layout = QHBoxLayout()

        refresh_btn = QPushButton(t("refresh_qr"))
        refresh_btn.clicked.connect(self._refresh_qr)
        button_layout.addWidget(refresh_btn)

        cancel_btn = QPushButton(t("cancel"))
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

        # Setup polling timer
        self._poll_timer.timeout.connect(self._poll_login_status)

    def _start_login_flow(self):
        """Start the login flow by generating QR code"""
        qr_data = QuarkDriveService.generate_qr_code()
        if qr_data:
            self._qr_token = qr_data['token']
            self._qr_url = qr_data['qr_url']
            self._display_qr_code(self._qr_url)
            self._start_polling()
        else:
            self._status_label.setText(t("qr_code_error"))

    def _display_qr_code(self, url: str):
        """Display QR code from URL using local library"""
        try:
            # Generate QR code using local library
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=8,  # Reduced box size for better fit
                border=2,    # Reduced border
            )
            qr.add_data(url)
            qr.make(fit=True)

            # Create image with exact size
            img = qr.make_image(fill_color="black", back_color="white")

            # Convert to QPixmap
            buf = BytesIO()
            img.save(buf, format='PNG')
            buf.seek(0)

            # Load into QPixmap
            pixmap = QPixmap()
            pixmap.loadFromData(buf.getvalue())

            # Scale pixmap to fit the label while maintaining aspect ratio
            scaled_pixmap = pixmap.scaled(
                self._qr_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )

            self._qr_label.setPixmap(scaled_pixmap)
            self._status_label.setText(t("scan_with_quark"))
        except Exception as e:
            logger.error(f"Error generating QR code: {e}", exc_info=True)
            self._status_label.setText(t("qr_code_error") + f": {e}")

    def _start_polling(self):
        """Start polling for login status"""
        self._poll_attempts = 0
        self._progress.setValue(0)
        self._poll_timer.start(2000)  # Poll every 2 seconds

    def _poll_login_status(self):
        """Poll login status from server"""
        self._poll_attempts += 1
        self._progress.setValue(self._poll_attempts)

        # Do a single poll attempt each timer tick
        result = QuarkDriveService.poll_login_status(
            self._qr_token,
            max_attempts=1,  # Single attempt per timer tick
            poll_interval=0   # No delay, we use QTimer for timing
        )

        if result:
            status = result.get('status')

            if status == 'success':
                self._poll_timer.stop()
                self._status_label.setText(t("login_successful"))
                self.login_success.emit(result)
                QTimer.singleShot(1000, self.accept)

            elif status == 'waiting':
                # Still waiting for scan, update status and continue polling
                self._status_label.setText(t("waiting_for_scan") + f" ({self._poll_attempts}/30)")
                # Timer continues running

            elif status == 'expired':
                self._poll_timer.stop()
                self._status_label.setText(t("qr_expired"))

            elif status == 'error':
                self._poll_timer.stop()
                self._status_label.setText(t("qr_code_error") + f": {result.get('message')}")

            elif status == 'timeout':
                # This shouldn't happen with max_attempts=1, but handle it
                self._poll_timer.stop()
                self._status_label.setText(t("login_timeout"))

        # Check for QR code expiration (60 seconds = 30 timer ticks at 2 seconds)
        if self._poll_attempts >= 30:
            self._poll_timer.stop()
            self._status_label.setText(t("login_timeout"))

    def _refresh_qr(self):
        """Refresh QR code"""
        self._poll_timer.stop()
        self._start_login_flow()

    def showEvent(self, event):
        """Handle dialog show event to ensure proper QR code display"""
        super().showEvent(event)
        # Use QTimer to delay QR code redisplay until after dialog is fully shown
        if hasattr(self, '_qr_url') and self._qr_url:
            QTimer.singleShot(100, lambda: self._display_qr_code(self._qr_url))

    def reject(self):
        """Handle dialog rejection (cancel button or Escape key)"""
        self._poll_timer.stop()
        super().reject()

    def closeEvent(self, event):
        """Clean up on close"""
        self._poll_timer.stop()
        super().closeEvent(event)
