"""
QQ Music QR code login dialog.
Uses qqmusic_api library for QR code login.
"""
import asyncio
import logging
from io import BytesIO
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QMessageBox, QButtonGroup, QRadioButton, QProgressBar, QWidget
)
from PySide6.QtCore import Qt, Signal, QThread, Slot
from PySide6.QtGui import QPixmap, QImage

from system.i18n import t

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
        self._loop = None

    def stop(self):
        """Stop the polling thread."""
        self._running = False

    def run(self):
        """Run QR code login polling."""
        try:
            # Import qqmusic_api
            from qqmusic_api.login import get_qrcode, check_qrcode, QRLoginType, QRCodeLoginEvents

            # Map string to enum
            login_type_enum = QRLoginType.QQ if self.login_type == 'qq' else QRLoginType.WX
            is_wechat = self.login_type == 'wx'
            logger.info(f"Starting QR login with type: {self.login_type} (is_wechat: {is_wechat})")

            # Run async function in thread
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            try:
                credential = self._loop.run_until_complete(self._qr_login(login_type_enum, is_wechat))
                if credential and self._running:
                    # Use as_dict() for reliable extraction of all fields
                    try:
                        cred_dict = credential.as_dict()
                        # Merge extra_fields into main dict (contains musickeyCreateTime, keyExpiresIn, etc.)
                        if 'extra_fields' in cred_dict and isinstance(cred_dict['extra_fields'], dict):
                            cred_dict.update(cred_dict.pop('extra_fields'))
                        elif 'extra_fields' in cred_dict:
                            cred_dict.pop('extra_fields', None)
                    except Exception:
                        # Fallback to manual extraction
                        cred_dict = {}
                        for attr in ['musicid', 'musickey', 'login_type', 'openid', 'refresh_token',
                                     'access_token', 'expired_at', 'unionid', 'str_musicid',
                                     'refresh_key', 'encrypt_uin', 'extra_fields']:
                            if hasattr(credential, attr):
                                val = getattr(credential, attr, None)
                                if attr == 'musicid' and val is not None:
                                    cred_dict[attr] = str(val)
                                elif attr == 'extra_fields' and isinstance(val, dict):
                                    cred_dict.update(val)
                                else:
                                    cred_dict[attr] = val

                    # Ensure musicid is string
                    if 'musicid' in cred_dict and cred_dict['musicid'] is not None:
                        cred_dict['musicid'] = str(cred_dict['musicid'])

                    # Add create time for refresh tracking
                    import time
                    cred_dict['musickey_createtime'] = int(time.time())

                    # Map API response field names to our storage format
                    if 'keyExpiresIn' in cred_dict:
                        cred_dict['key_expires_in'] = cred_dict.pop('keyExpiresIn')
                    if 'loginType' in cred_dict:
                        cred_dict['login_type'] = cred_dict.pop('loginType')
                    if 'encryptUin' in cred_dict:
                        cred_dict['encrypt_uin'] = cred_dict.pop('encryptUin')

                    logger.info(f"Login success, musicid: {cred_dict.get('musicid')}, "
                               f"login_type: {cred_dict.get('login_type')}, "
                               f"has_refresh_key: {bool(cred_dict.get('refresh_key'))}, "
                               f"has_refresh_token: {bool(cred_dict.get('refresh_token'))}, "
                               f"encrypt_uin: {cred_dict.get('encrypt_uin')}")
                    self.login_success.emit(cred_dict)
            finally:
                if self._loop and not self._loop.is_closed():
                    self._loop.close()
                self._loop = None

        except ImportError:
            if self._running:
                self.login_failed.emit(t("qqmusic_api_not_installed"))
        except Exception as e:
            logger.error(f"QR login error: {e}")
            if self._running:
                self.login_failed.emit(t("qqmusic_login_failed_detail").format(error=str(e)))

    def wait_for_stop(self, timeout_ms: int = 2000):
        """Stop the thread and wait for it to finish."""
        self._running = False
        return self.wait(timeout_ms)

    async def _qr_login(self, login_type, is_wechat: bool):
        """Execute QR code login process."""
        from qqmusic_api.login import get_qrcode, check_qrcode, QRCodeLoginEvents
        from pyzbar.pyzbar import decode
        from PIL import Image

        # Get QR code
        app_name = t("qqmusic_wx_login").replace("登录", "").strip() if is_wechat else "QQ"
        self.status_update.emit(t("qqmusic_fetching_qr"))
        qr = await get_qrcode(login_type)

        # Check if still running
        if not self._running:
            return None

        # Emit QR code image for display
        logger.debug(f"QR code: {qr}")
        self.qr_code_ready.emit(qr.data)

        # Poll for login status
        self.status_update.emit(t("qqmusic_scan_with_app").format(app=app_name))

        poll_count = 0
        max_polls = 120  # 2 minutes

        while poll_count < max_polls and self._running:
            try:
                event, credential = await check_qrcode(qr)

                if not self._running:
                    return None

                if event == QRCodeLoginEvents.SCAN:
                    self.status_update.emit(t("qqmusic_waiting_scan"))

                elif event == QRCodeLoginEvents.CONF:
                    self.status_update.emit(t("qqmusic_scan_confirmed"))

                elif event == QRCodeLoginEvents.DONE:
                    self.status_update.emit(t("qqmusic_logging_in"))
                    return credential

                elif event == QRCodeLoginEvents.TIMEOUT:
                    self.login_timeout.emit()
                    return None

                elif event == QRCodeLoginEvents.REFUSE:
                    self.login_refused.emit()
                    return None

                poll_count += 1
                await asyncio.sleep(1)  # Poll every second

            except Exception as e:
                logger.debug(f"Poll error: {e}")
                poll_count += 1
                await asyncio.sleep(1)

        # Timeout
        if self._running:
            self.login_timeout.emit()
        return None


class QQMusicQRLoginDialog(QDialog):
    """Dialog for QQ Music QR code login."""

    # Signal emitted when credentials are successfully obtained
    credentials_obtained = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("qqmusic_login_title"))
        self.setMinimumWidth(450)
        self.setMinimumHeight(600)
        self.resize(460, 680)

        from app.bootstrap import Bootstrap
        self.config = Bootstrap.instance().config

        self._login_thread: Optional[QRLoginThread] = None
        self._login_type = 'wx'  # default to WeChat

        self._setup_ui()
        self._start_login()

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
            QRadioButton {
                color: #ffffff;
                font-size: 13px;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #4a4a4a;
                border-radius: 9px;
                background-color: #2a2a2a;
            }
            QRadioButton::indicator:checked {
                border: 2px solid #1db954;
                background-color: #1db954;
            }
            QRadioButton::indicator:hover {
                border: 2px solid #1db954;
            }
            QPushButton {
                background-color: #3a3a3a;
                color: #ffffff;
                border: 1px solid #4a4a4a;
                border-radius: 4px;
                padding: 8px 20px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                border: 1px solid #1db954;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
            QPushButton:disabled {
                background-color: #2a2a2a;
                color: #606060;
            }
            QProgressBar {
                border: none;
                background-color: #2a2a2a;
                height: 4px;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #1db954;
                border-radius: 2px;
            }
        """)

    def _setup_ui(self):
        """Setup the UI."""
        self._apply_dark_style()

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel(f"<h3>{t('qqmusic_login_title')}</h3>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Login type selection
        type_layout = QHBoxLayout()
        type_label = QLabel(t("qqmusic_login_method"))
        type_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
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
        self._status_label.setStyleSheet("font-size: 14px; color: #1db954; padding: 8px; font-weight: bold;")
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
        self._qr_label.setStyleSheet("border: 2px solid #4a4a4a; border-radius: 8px; background: #ffffff;")
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
        self._instructions_label.setStyleSheet("color: #a0a0a0; font-size: 12px;")
        self._update_instructions()
        layout.addWidget(self._instructions_label)

        # Buttons
        button_layout = QHBoxLayout()

        self._refresh_button = QPushButton(t("qqmusic_refresh_qr"))
        self._refresh_button.clicked.connect(self._refresh_qr)
        self._refresh_button.setEnabled(False)
        button_layout.addWidget(self._refresh_button)

        self._cancel_button = QPushButton(t("cancel"))
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
        if t("language") == "中文":
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

            # Refresh QQ Music client to use new credentials
            from app.bootstrap import Bootstrap
            Bootstrap.instance().refresh_qqmusic_client()

            QMessageBox.information(
                self,
                t("success"),
                t("qqmusic_login_success")
            )

            self.credentials_obtained.emit(credential)
            self.accept()

        except Exception as e:
            logger.error(f"Failed to save credentials: {e}")
            QMessageBox.warning(
                self,
                t("error"),
                f"{t('error')}:\n{str(e)}"
            )

    @Slot(str)
    def _on_login_failed(self, error: str):
        """Handle login failed event."""
        self._progress_bar.hide()
        self._status_label.setText(t("qqmusic_login_failed"))
        QMessageBox.warning(self, t("qqmusic_login_failed"), error)

    @Slot()
    def _on_login_refused(self):
        """Handle login refused event."""
        self._progress_bar.hide()
        self._status_label.setText(t("qqmusic_user_cancelled"))
        QMessageBox.information(self, t("cancel"), t("qqmusic_you_cancelled"))

    @Slot()
    def _on_login_timeout(self):
        """Handle login timeout event."""
        self._progress_bar.hide()
        self._status_label.setText(t("qqmusic_qr_expired"))
        self._refresh_button.setEnabled(True)
        QMessageBox.information(
            self,
            t("qqmusic_qr_expired"),
            t("qqmusic_qr_timeout_refresh")
        )

    @Slot(str)
    def _on_status_update(self, status: str):
        """Handle status update event."""
        self._status_label.setText(status)

    def closeEvent(self, event):
        """Handle dialog close event."""
        if self._login_thread:
            self._login_thread.stop()
        event.accept()
