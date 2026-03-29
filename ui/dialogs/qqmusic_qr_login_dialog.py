"""
QQ Music QR code login dialog.
Uses local implementation without qqmusic_api dependency.
"""
import logging
import time
from io import BytesIO
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QButtonGroup, QRadioButton, QProgressBar, QWidget,
    QGraphicsDropShadowEffect,
)

from ui.dialogs.message_dialog import MessageDialog
from PySide6.QtCore import Qt, Signal, QThread, Slot
from PySide6.QtGui import QColor, QPainterPath, QRegion, QPixmap, QImage

from services.cloud.qqmusic.qr_login import (
    QQMusicQRLogin, QRLoginType, QRCodeLoginEvents, QR, Credential
)
from system.i18n import t, get_language
from system.theme import ThemeManager

logger = logging.getLogger(__name__)


class QRLoginThread(QThread):
    """Background thread for QR code login polling."""

    # Signals
    qr_code_ready = Signal(bytes)  # QR image data
    login_success = Signal(dict)  # credential dict
    login_failed = Signal(str)  # error message
    login_refused = Signal()  # user refused
    login_timeout = Signal()  # QR code expired
    status_update = Signal(str)  # status message

    def __init__(self, login_type: str = 'qq'):
        super().__init__()
        self.login_type = login_type
        self._running = True

    def stop(self):
        """Stop the polling thread."""
        self._running = False

    def run(self):
        """Run QR code login polling."""
        try:
            login_type = QRLoginType.WX if self.login_type == 'wx' else QRLoginType.QQ
            is_wechat = self.login_type == 'wx'
            logger.info(f"Starting QR login with type: {self.login_type} (is_wechat: {is_wechat})")

            client = QQMusicQRLogin()

            # Get QR code
            app_name = t("qqmusic_wx_login").replace("登录", "").strip() if is_wechat else "QQ"
            self.status_update.emit(t("qqmusic_fetching_qr"))

            qr = client.get_qrcode(login_type)
            if not qr:
                if self._running:
                    self.login_failed.emit(t("qqmusic_login_failed_detail").format(error="Failed to get QR code"))
                return

            if not self._running:
                return

            # Emit QR code image for display
            self.qr_code_ready.emit(qr.data)
            logger.debug(f"QR code obtained, type: {qr.qr_type}, identifier: {qr.identifier[:20]}...")

            # Poll for login status
            self.status_update.emit(t("qqmusic_scan_with_app").format(app=app_name))

            poll_count = 0
            max_polls = 120  # 2 minutes

            while poll_count < max_polls and self._running:
                try:
                    event, credential = client.check_qrcode(qr)

                    if not self._running:
                        return

                    if event == QRCodeLoginEvents.SCAN:
                        self.status_update.emit(t("qqmusic_waiting_scan"))

                    elif event == QRCodeLoginEvents.CONF:
                        self.status_update.emit(t("qqmusic_scan_confirmed"))

                    elif event == QRCodeLoginEvents.DONE:
                        self.status_update.emit(t("qqmusic_logging_in"))

                        if credential:
                            # Convert credential to dict
                            cred_dict = credential.as_dict()

                            # Add create time for refresh tracking
                            cred_dict['musickey_createtime'] = int(time.time())

                            # Ensure musicid is string
                            if 'musicid' in cred_dict and cred_dict['musicid'] is not None:
                                cred_dict['musicid'] = str(cred_dict['musicid'])

                            logger.info(f"Login success, musicid: {cred_dict.get('musicid')}, "
                                       f"login_type: {cred_dict.get('login_type')}, "
                                       f"has_refresh_key: {bool(cred_dict.get('refresh_key'))}, "
                                       f"has_refresh_token: {bool(cred_dict.get('refresh_token'))}, "
                                       f"encrypt_uin: {cred_dict.get('encrypt_uin')}")

                            self.login_success.emit(cred_dict)
                        else:
                            self.login_failed.emit("Login succeeded but no credential returned")
                        return

                    elif event == QRCodeLoginEvents.TIMEOUT:
                        self.login_timeout.emit()
                        return

                    elif event == QRCodeLoginEvents.REFUSE:
                        self.login_refused.emit()
                        return

                    poll_count += 1
                    self.msleep(1000)  # Poll every second

                except Exception as e:
                    logger.debug(f"Poll error: {e}")
                    poll_count += 1
                    self.msleep(1000)

            # Timeout
            if self._running:
                self.login_timeout.emit()

        except Exception as e:
            logger.error(f"QR login error: {e}")
            if self._running:
                self.login_failed.emit(t("qqmusic_login_failed_detail").format(error=str(e)))

    def wait_for_stop(self, timeout_ms: int = 2000):
        """Stop the thread and wait for it to finish."""
        self._running = False
        return self.wait(timeout_ms)


class QQMusicQRLoginDialog(QDialog):
    """Dialog for QQ Music QR code login."""

    # Signal emitted when credentials are successfully obtained
    credentials_obtained = Signal(dict)

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
        QRadioButton {
            color: %text%;
            font-size: 13px;
            spacing: 8px;
        }
        QRadioButton::indicator {
            width: 18px;
            height: 18px;
            border: 2px solid %background_hover%;
            border-radius: 9px;
            background-color: %background_alt%;
        }
        QRadioButton::indicator:checked {
            border: 2px solid %highlight%;
            background-color: %highlight%;
        }
        QRadioButton::indicator:hover {
            border: 2px solid %highlight%;
        }
        QPushButton {
            background-color: %border%;
            color: %text%;
            border: 1px solid %background_hover%;
            border-radius: 4px;
            padding: 8px 20px;
            font-size: 13px;
        }
        QPushButton:hover {
            background-color: %background_hover%;
            border: 1px solid %highlight%;
        }
        QPushButton:pressed {
            background-color: %background_alt%;
        }
        QPushButton:disabled {
            background-color: %background_alt%;
            color: %border%;
        }
        QProgressBar {
            border: none;
            background-color: %background_alt%;
            height: 4px;
            border-radius: 2px;
        }
        QProgressBar::chunk {
            background-color: %highlight%;
            border-radius: 2px;
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_pos = None

        self.setWindowTitle(t("qqmusic_login_title"))
        self.setMinimumWidth(450)
        self.setMinimumHeight(600)
        self.resize(460, 680)

        self.setWindowFlags(Qt.WindowType.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._setup_shadow()

        from app.bootstrap import Bootstrap
        self.config = Bootstrap.instance().config

        self._login_thread: Optional[QRLoginThread] = None
        self._login_type = 'wx'  # default to WeChat

        self._setup_ui()
        self._start_login()
        ThemeManager.instance().register_widget(self)

    def _setup_shadow(self):
        """Setup drop shadow effect."""
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

    def _setup_ui(self):
        """Setup the UI."""
        self.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TEMPLATE))

        # Outer layout with 0 margins
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Container widget for rounded corners
        container = QWidget()
        container.setObjectName("dialogContainer")
        outer.addWidget(container)

        layout = QVBoxLayout(container)
        layout.setSpacing(15)
        layout.setContentsMargins(24, 20, 24, 20)

        # Title
        title_label = QLabel(t("qqmusic_login_title"))
        title_label.setObjectName("dialogTitle")
        layout.addWidget(title_label)

        # Login type selection
        type_layout = QHBoxLayout()
        type_label = QLabel(t("qqmusic_login_method"))
        theme = ThemeManager.instance().current_theme
        type_label.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {theme.text};")
        self._qq_radio = QRadioButton(t("qqmusic_qq_login"))
        self._wx_radio = QRadioButton(t("qqmusic_wx_login"))
        self._wx_radio.setChecked(True)  # 默认微信登录
        self._login_type = 'wx'  # default to WeChat
        self._qq_radio.toggled.connect(self._on_login_type_changed)

        type_group = QButtonGroup(self)
        type_group.addButton(self._qq_radio)
        type_group.addButton(self._wx_radio)

        type_layout.addWidget(type_label)
        type_layout.addWidget(self._qq_radio)
        type_layout.addWidget(self._wx_radio)
        type_layout.addStretch()

        layout.addLayout(type_layout)

        # Status label (above QR code)
        self._status_label = QLabel(t("qqmusic_loading_qr"))
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet(f"font-size: 14px; color: {theme.highlight}; padding: 8px; font-weight: bold;")
        layout.addWidget(self._status_label)

        # QR code container
        qr_container = QWidget()
        qr_layout = QVBoxLayout(qr_container)
        qr_layout.setContentsMargins(0, 0, 0, 0)

        # QR code image
        self._qr_label = QLabel()
        self._qr_label.setMinimumSize(300, 300)
        self._qr_label.setMaximumSize(300, 300)
        self._qr_label.setAlignment(Qt.AlignCenter)
        self._qr_label.setStyleSheet(f"border: 2px solid {theme.background_hover}; border-radius: 8px; background: #ffffff;")
        qr_layout.addWidget(self._qr_label)

        layout.addWidget(qr_container, alignment=Qt.AlignCenter)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setRange(0, 0)  # Indeterminate progress
        self._progress_bar.setMaximumHeight(4)
        self._progress_bar.hide()
        layout.addWidget(self._progress_bar)

        # Instructions
        self._instructions_label = QLabel()
        self._instructions_label.setAlignment(Qt.AlignCenter)
        self._instructions_label.setStyleSheet(f"color: {theme.text_secondary}; font-size: 12px;")
        self._update_instructions()
        layout.addWidget(self._instructions_label)

        # Buttons
        button_layout = QHBoxLayout()

        self._refresh_button = QPushButton(t("qqmusic_refresh_qr"))
        self._refresh_button.setCursor(Qt.PointingHandCursor)
        self._refresh_button.clicked.connect(self._refresh_qr)
        self._refresh_button.setEnabled(False)
        button_layout.addWidget(self._refresh_button)

        self._cancel_button = QPushButton(t("cancel"))
        self._cancel_button.setCursor(Qt.PointingHandCursor)
        self._cancel_button.clicked.connect(self._cancel_login)
        button_layout.addWidget(self._cancel_button)

        layout.addLayout(button_layout)

    def _on_login_type_changed(self):
        """Handle login type radio button change."""
        if self._qq_radio.isChecked():
            self._login_type = 'qq'
        else:
            self._login_type = 'wx'

        # Update instructions text
        self._update_instructions()
        # Restart login with new type
        self._restart_login()

    def _update_instructions(self):
        """Update instructions based on login type."""
        app_name = "WeChat" if self._login_type == 'wx' else "QQ"
        if get_language() == "zh":
            app_name = "微信" if self._login_type == 'wx' else "QQ"
        self._instructions_label.setText(t("qqmusic_instructions").format(app=app_name))

    def _restart_login(self):
        """Restart login process - stop old thread and start new one."""
        # Keep reference to old thread
        old_thread = self._login_thread
        self._login_thread = None

        # Stop old thread if exists
        if old_thread:
            old_thread.stop()
            # Let the old thread finish naturally, don't wait
            # We keep it referenced but don't block

        # Start new login
        self._start_login()

    def _start_login(self):
        """Start QR code login process."""
        self._progress_bar.show()
        self._refresh_button.setEnabled(False)
        self._qr_label.clear()
        self._status_label.setText(t("qqmusic_fetching_qr"))

        # Create new thread
        thread = QRLoginThread(self._login_type)
        thread.qr_code_ready.connect(self._on_qr_code_ready)
        thread.login_success.connect(self._on_login_success)
        thread.login_failed.connect(self._on_login_failed)
        thread.login_refused.connect(self._on_login_refused)
        thread.login_timeout.connect(self._on_login_timeout)
        thread.status_update.connect(self._on_status_update)
        thread.finished.connect(lambda: self._on_thread_finished(thread))

        self._login_thread = thread
        thread.start()

    def _on_thread_finished(self, thread):
        """Handle thread finished event."""
        # Clean up reference if this is the current thread
        if self._login_thread == thread:
            self._login_thread = None

    def _refresh_qr(self):
        """Refresh QR code."""
        # Disable refresh button to prevent double-click
        self._refresh_button.setEnabled(False)
        self._restart_login()

    def _cancel_login(self):
        """Cancel login and close dialog."""
        if self._login_thread:
            self._login_thread.stop()
        self.reject()

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

    def closeEvent(self, event):
        """Handle dialog close event."""
        if self._login_thread:
            self._login_thread.stop()
        event.accept()

    @Slot(bytes)
    def _on_qr_code_ready(self, qr_data: bytes):
        """Handle QR code ready event."""
        try:
            from PIL import Image

            # Convert bytes to QPixmap
            img = Image.open(BytesIO(qr_data))

            # Resize if needed
            if img.size != (300, 300):
                img = img.resize((300, 300), Image.Resampling.LANCZOS)

            # Convert PIL image to bytes
            byte_arr = BytesIO()
            img.save(byte_arr, format='PNG')
            byte_arr = byte_arr.getvalue()

            # Create QPixmap from bytes
            qimage = QImage.fromData(byte_arr)
            pixmap = QPixmap.fromImage(qimage)

            self._qr_label.setPixmap(pixmap)
            self._refresh_button.setEnabled(True)

        except Exception as e:
            logger.error(f"Failed to display QR code: {e}")
            self._qr_label.setText(f"{t('qqmusic_qr_display_failed')}\n{str(e)}")

    @Slot(dict)
    def _on_login_success(self, credential: dict):
        """Handle login success event."""
        self._progress_bar.hide()
        self._status_label.setText(t("qqmusic_login_success") if t('language') != '中文' else "登录成功！正在保存凭证...")

        try:
            # Save credentials (full credential dict)
            self.config.set_qqmusic_credential(credential)

            # Get user nickname
            try:
                from services.cloud.qqmusic import QQMusicClient
                client = QQMusicClient(credential)
                user_info = client.verify_login()
                if user_info.get('valid') and user_info.get('nick'):
                    self.config.set_qqmusic_nick(user_info['nick'])
                    logger.info(f"Got QQ Music nickname: {user_info['nick']}")
            except Exception as e:
                logger.warning(f"Failed to get QQ Music nickname: {e}")

            # Refresh QQ Music client to use new credentials
            from app.bootstrap import Bootstrap
            Bootstrap.instance().refresh_qqmusic_client()

            MessageDialog.information(
                self,
                t("success"),
                t("qqmusic_login_success")
            )

            self.credentials_obtained.emit(credential)
            self.accept()

        except Exception as e:
            logger.error(f"Failed to save credentials: {e}")
            MessageDialog.warning(
                self,
                t("error"),
                f"{t('error')}:\n{str(e)}"
            )

    @Slot(str)
    def _on_login_failed(self, error: str):
        """Handle login failed event."""
        self._progress_bar.hide()
        self._status_label.setText(t("qqmusic_login_failed"))
        MessageDialog.warning(self, t("qqmusic_login_failed"), error)

    @Slot()
    def _on_login_refused(self):
        """Handle login refused event."""
        self._progress_bar.hide()
        self._status_label.setText(t("qqmusic_user_cancelled"))
        MessageDialog.information(self, t("cancel"), t("qqmusic_you_cancelled"))

    @Slot()
    def _on_login_timeout(self):
        """Handle login timeout event."""
        self._progress_bar.hide()
        self._status_label.setText(t("qqmusic_qr_expired"))
        self._refresh_button.setEnabled(True)
        MessageDialog.information(
            self,
            t("qqmusic_qr_expired"),
            t("qqmusic_qr_timeout_refresh")
        )

    @Slot(str)
    def _on_status_update(self, status: str):
        """Handle status update event."""
        self._status_label.setText(status)

    def refresh_theme(self):
        """Refresh theme when changed."""
        self.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TEMPLATE))
        theme = ThemeManager.instance().current_theme
        if self._status_label:
            self._status_label.setStyleSheet(f"font-size: 14px; color: {theme.highlight}; padding: 8px; font-weight: bold;")
        if self._qr_label:
            self._qr_label.setStyleSheet(f"border: 2px solid {theme.background_hover}; border-radius: 8px; background: #ffffff;")
        if self._instructions_label:
            self._instructions_label.setStyleSheet(f"color: {theme.text_secondary}; font-size: 12px;")
