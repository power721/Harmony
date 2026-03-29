"""
Cloud login dialog for QR code authentication.
"""
import logging
from io import BytesIO

import qrcode
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap, QColor, QPainterPath, QRegion
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QProgressBar, QStackedWidget,
                               QTextEdit, QLineEdit, QWidget, QGraphicsDropShadowEffect)

from services.cloud.quark_service import QuarkDriveService
from services.cloud.baidu_service import BaiduDriveService
from system.i18n import t
from system.theme import ThemeManager

# Configure logging
logger = logging.getLogger(__name__)


class CloudLoginDialog(QDialog):
    """Dialog for QR code login to cloud services"""

    login_success = Signal(dict)  # Emits account info on success

    _STYLE_TEMPLATE = """
        QWidget#dialogContainer {
            background-color: %background_alt%;
            color: %text%;
            border: 1px solid %border%;
            border-radius: 12px;
        }
        QLabel#dialogTitle {
            color: %text%;
            font-size: 15px;
            font-weight: bold;
        }
        QLabel {
            color: %text%;
        }
        QPushButton {
            background-color: %border%;
            color: %text%;
            border: 1px solid %background_hover%;
            border-radius: 4px;
            padding: 8px 16px;
        }
        QPushButton:hover {
            background-color: %background_hover%;
        }
        QPushButton:pressed {
            background-color: %background_alt%;
        }
        QPushButton[role="cancel"] {
            background-color: %border%;
            color: %text%;
        }
        QPushButton[role="cancel"]:hover {
            background-color: %background_hover%;
        }
        QProgressBar {
            background-color: %border%;
            border: 1px solid %background_hover%;
            border-radius: 4px;
            text-align: center;
            color: %text%;
        }
        QProgressBar::chunk {
            background-color: %highlight%;
            border-radius: 3px;
        }
        QTextEdit, QLineEdit {
            background-color: %border%;
            color: %text%;
            border: 1px solid %background_hover%;
            border-radius: 4px;
            padding: 8px;
        }
        QTextEdit:focus, QLineEdit:focus {
            border: 1px solid %highlight%;
        }
    """

    def __init__(self, provider: str = "quark", parent=None):
        super().__init__(parent)
        self._provider = provider
        self._service = BaiduDriveService if provider == "baidu" else QuarkDriveService
        self._qr_token = None
        self._qr_url = None  # Store QR URL for redisplay
        self._poll_timer = QTimer(self)
        self._poll_attempts = 0
        self._drag_pos = None

        # Make dialog frameless
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._setup_shadow()
        self._setup_ui()
        self._start_login_flow()
        self.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TEMPLATE))
        ThemeManager.instance().register_widget(self)

    def _setup_shadow(self):
        """Setup drop shadow effect."""
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

    def _setup_ui(self):
        """Setup the dialog UI"""
        provider_name = t("baidu_drive") if self._provider == "baidu" else t("quark_drive")
        self.setWindowTitle(provider_name + " " + t("login"))
        self.setMinimumSize(450, 520)

        # Outer layout with 0 margins — container fills the dialog
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Container widget for rounded corners
        container = QWidget()
        container.setObjectName("dialogContainer")
        outer.addWidget(container)

        main_layout = QVBoxLayout(container)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(24, 20, 24, 20)

        # Title
        title_label = QLabel(provider_name + " " + t("login"))
        title_label.setObjectName("dialogTitle")
        main_layout.addWidget(title_label)

        # Mode toggle buttons
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(10)

        self._qr_mode_btn = QPushButton(t("scan_qr_code"))
        self._qr_mode_btn.setCheckable(True)
        self._qr_mode_btn.setChecked(True)
        self._qr_mode_btn.clicked.connect(self._switch_to_qr_mode)

        self._cookie_mode_btn = QPushButton(t("input_cookie"))
        self._cookie_mode_btn.setCheckable(True)
        self._cookie_mode_btn.clicked.connect(self._switch_to_cookie_mode)

        mode_layout.addWidget(self._qr_mode_btn)
        mode_layout.addWidget(self._cookie_mode_btn)
        main_layout.addLayout(mode_layout)

        # Stacked widget for different modes
        self._stacked_widget = QStackedWidget()

        # QR Code Mode
        qr_widget = self._create_qr_widget()
        self._stacked_widget.addWidget(qr_widget)

        # Cookie Input Mode
        cookie_widget = self._create_cookie_widget()
        self._stacked_widget.addWidget(cookie_widget)

        main_layout.addWidget(self._stacked_widget)

        # Bottom buttons
        button_layout = QHBoxLayout()

        self._refresh_btn = QPushButton(t("refresh_qr"))
        self._refresh_btn.clicked.connect(self._refresh_qr)
        button_layout.addWidget(self._refresh_btn)

        cancel_btn = QPushButton(t("cancel"))
        cancel_btn.setProperty("role", "cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        main_layout.addLayout(button_layout)

        # Setup polling timer
        self._poll_timer.timeout.connect(self._poll_login_status)

    def _create_qr_widget(self):
        """Create QR code login widget"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(20)

        # QR Code placeholder
        self._qr_label = QLabel()
        self._qr_label.setMinimumSize(250, 250)
        self._qr_label.setMaximumSize(250, 250)
        self._qr_label.setAlignment(Qt.AlignCenter)
        self._qr_label.setScaledContents(False)
        self._qr_label.setStyleSheet(f"border: 2px solid {ThemeManager.instance().current_theme.border}; border-radius: 8px; background: white;")
        layout.addWidget(self._qr_label, 0, Qt.AlignCenter)

        # Status label
        self._status_label = QLabel(t("generating_qr"))
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet(f"color: {ThemeManager.instance().current_theme.text_secondary};")
        layout.addWidget(self._status_label)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setMaximum(30)  # 30 ticks = 60 seconds (2s per tick)
        self._progress.setValue(0)
        layout.addWidget(self._progress)

        widget.setLayout(layout)
        return widget

    def _create_cookie_widget(self):
        """Create cookie input widget"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Title
        title = QLabel(t("input_cookie"))
        theme = ThemeManager.instance().current_theme
        title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {theme.highlight};")
        layout.addWidget(title)

        # Help text
        help_label = QLabel(t("cookie_help"))
        help_label.setWordWrap(True)
        help_label.setStyleSheet(f"color: {theme.text_secondary}; font-size: 12px;")
        layout.addWidget(help_label)

        # Cookie input
        self._cookie_input = QTextEdit()
        self._cookie_input.setPlaceholderText(t("cookie_placeholder"))
        self._cookie_input.setMaximumHeight(150)
        layout.addWidget(self._cookie_input)

        # Validate button
        self._validate_btn = QPushButton(t("validate_cookie"))
        self._validate_btn.clicked.connect(self._validate_cookie)
        layout.addWidget(self._validate_btn)

        # Cookie status label
        self._cookie_status_label = QLabel()
        self._cookie_status_label.setAlignment(Qt.AlignCenter)
        self._cookie_status_label.setWordWrap(True)
        self._cookie_status_label.setStyleSheet(f"color: {theme.text_secondary};")
        layout.addWidget(self._cookie_status_label)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def _switch_to_qr_mode(self):
        """Switch to QR code mode"""
        self._qr_mode_btn.setChecked(True)
        self._cookie_mode_btn.setChecked(False)
        self._stacked_widget.setCurrentIndex(0)
        self._refresh_btn.setVisible(True)
        self._poll_timer.start(2000) if self._qr_token else None

    def _switch_to_cookie_mode(self):
        """Switch to cookie input mode"""
        self._qr_mode_btn.setChecked(False)
        self._cookie_mode_btn.setChecked(True)
        self._stacked_widget.setCurrentIndex(1)
        self._refresh_btn.setVisible(False)
        self._poll_timer.stop()

    def _validate_cookie(self):
        """Validate the entered cookie"""
        cookie_str = self._cookie_input.toPlainText().strip()
        if not cookie_str:
            self._cookie_status_label.setText(t("cookie_empty"))
            self._cookie_status_label.setStyleSheet("color: #ff5555;")
            return

        self._cookie_status_label.setText(t("validating_cookie"))
        theme = ThemeManager.instance().current_theme
        self._cookie_status_label.setStyleSheet(f"color: {theme.text_secondary};")
        self._validate_btn.setEnabled(False)

        # Validate in a timer to avoid blocking UI
        QTimer.singleShot(100, lambda: self._do_validate_cookie(cookie_str))

    def _do_validate_cookie(self, cookie_str: str):
        """Perform cookie validation"""
        result = self._service.validate_cookie(cookie_str)
        self._validate_btn.setEnabled(True)

        if result and result.get('status') == 'success':
            self._cookie_status_label.setText(t("login_successful"))
            theme = ThemeManager.instance().current_theme
            self._cookie_status_label.setStyleSheet(f"color: {theme.highlight};")
            self.login_success.emit(result)
            QTimer.singleShot(1000, self.accept)
        else:
            self._cookie_status_label.setText(t("cookie_invalid"))
            self._cookie_status_label.setStyleSheet("color: #ff5555;")

    def _start_login_flow(self):
        """Start the login flow by generating QR code"""
        qr_data = self._service.generate_qr_code()
        if qr_data:
            # Baidu uses 'sign', Quark uses 'token'
            self._qr_token = qr_data.get('sign') or qr_data.get('token')
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
                border=2,  # Reduced border
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
            scan_text = t("scan_with_baidu") if self._provider == "baidu" else t("scan_with_quark")
            self._status_label.setText(scan_text)
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
        result = self._service.poll_login_status(
            self._qr_token,
            max_attempts=1,  # Single attempt per timer tick
            poll_interval=0  # No delay, we use QTimer for timing
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

    def refresh_theme(self):
        """Refresh theme when changed."""
        self.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TEMPLATE))
        theme = ThemeManager.instance().current_theme
        if self._status_label:
            self._status_label.setStyleSheet(f"color: {theme.text_secondary};")
        if self._qr_label:
            self._qr_label.setStyleSheet(f"border: 2px solid {theme.border}; border-radius: 8px; background: white;")

    def resizeEvent(self, event):
        """Apply rounded corner mask."""
        path = QPainterPath()
        path.addRoundedRect(self.rect(), 12, 12)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        """Handle mouse press for drag to move."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        """Handle mouse move for drag to move."""
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        """Handle mouse release."""
        self._drag_pos = None
