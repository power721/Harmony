"""
QQ Music QR code login dialog.
Uses local implementation without qqmusic_api dependency.
"""
from __future__ import annotations

import logging
import re
import time
from io import BytesIO
from typing import Optional

from PySide6.QtCore import Qt, Signal, QThread, Slot
from PySide6.QtGui import QColor, QPainterPath, QRegion, QPixmap, QImage
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QButtonGroup, QRadioButton, QProgressBar, QWidget, QLineEdit,
    QGraphicsDropShadowEffect,
)

from .dialog_title_bar import setup_dialog_title_layout
from .i18n import get_language, set_language, t
from .qqmusic_client import QQMusicClient
from .qr_login import QQMusicQRLogin, QRLoginType, QRCodeLoginEvents
from .runtime_bridge import (
    bind_context,
    current_theme,
    get_qss,
    show_information,
    register_themed_widget,
    show_warning,
)

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

    def __init__(self, login_type: str = 'qq', http_client=None):
        super().__init__()
        self.login_type = login_type
        self._http_client = http_client
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

            client = QQMusicQRLogin(http_client=self._http_client)

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


class QQMusicLoginDialog(QDialog):
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
        QPushButton#qqmusicRefreshBtn {
            background-color: %border%;
            color: %text%;
            font-size: 13px;
            border: 1px solid %background_hover%;
            border-radius: 4px;
            padding: 8px 16px;
        }
        QPushButton#qqmusicRefreshBtn:hover {
            background-color: %background_hover%;
            border: 1px solid %highlight%;
        }
        QPushButton#qqmusicRefreshBtn:pressed {
            background-color: %background_alt%;
        }
        QPushButton#qqmusicRefreshBtn:disabled {
            background-color: %background_alt%;
            color: %text_secondary%;
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
        QComboBox {
            background-color: %background%;
            border: 1px solid %border%;
            border-radius: 6px;
            padding: 0px 12px;
            min-height: 32px;
            color: %text%;
            min-width: 80px;
        }
        QComboBox:hover {
            background-color: %background_hover%;
            border: 1px solid %highlight%;
        }
        QComboBox::drop-down {
            border: none;
            width: 30px;
        }
        QComboBox QAbstractItemView {
            background-color: %background_alt%;
            border: 1px solid %border%;
            color: %text%;
            selection-background-color: %highlight%;
            selection-color: %background%;
            outline: none;
        }
        QComboBox QAbstractItemView::item {
            padding: 6px 10px;
            min-height: 20px;
        }
        QComboBox QAbstractItemView::item:hover {
            background-color: %highlight%;
            color: %background%;
        }
        QComboBox QAbstractItemView::item:selected {
            background-color: %highlight%;
            color: %background%;
        }
    """

    def __init__(self, context=None, parent=None):
        super().__init__(parent)
        self._context = context
        bind_context(context)
        self._drag_pos = None

        self.setWindowTitle(t("qqmusic_login_title"))
        self.setMinimumWidth(450)
        self.setMinimumHeight(600)
        self.resize(460, 680)

        self.setWindowFlags(Qt.WindowType.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setProperty("shell", True)

        self._setup_shadow()

        self._login_thread: Optional[QRLoginThread] = None
        self._retired_login_threads: list[QRLoginThread] = []
        self._login_mode = "qr"
        self._login_type = 'wx'  # default to WeChat
        self._phone_client = QQMusicClient(http_client=getattr(self._context, "http", None))
        self._language_connected = False

        self._setup_ui()
        self._connect_language_events()
        self._start_login()
        register_themed_widget(self)

    def _setup_shadow(self):
        """Setup drop shadow effect."""
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

    def _setup_ui(self):
        """Setup the UI."""
        self.setStyleSheet(get_qss(self._STYLE_TEMPLATE))

        # Outer layout with 0 margins
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Container widget for rounded corners
        container = QWidget()
        container.setObjectName("dialogContainer")
        outer.addWidget(container)

        container_layout = QVBoxLayout(container)
        layout, self._title_bar_controller = setup_dialog_title_layout(
            self,
            container_layout,
            t("qqmusic_login_title"),
            content_spacing=2,
        )

        theme = current_theme()

        # Login mode selection
        mode_layout = QHBoxLayout()
        mode_label = QLabel(t("qqmusic_login_method"))
        mode_label.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {theme.text};")
        self._qr_mode_btn = QRadioButton(t("qqmusic_mode_qr"))
        self._phone_mode_btn = QRadioButton(t("qqmusic_mode_phone"))
        self._qr_mode_btn.setChecked(True)
        self._qr_mode_btn.toggled.connect(self._on_login_mode_changed)
        self._phone_mode_btn.toggled.connect(self._on_login_mode_changed)

        mode_group = QButtonGroup(self)
        mode_group.addButton(self._qr_mode_btn)
        mode_group.addButton(self._phone_mode_btn)

        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self._qr_mode_btn)
        mode_layout.addWidget(self._phone_mode_btn)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        self._qr_panel = QWidget()
        qr_panel_layout = QVBoxLayout(self._qr_panel)
        qr_panel_layout.setContentsMargins(0, 0, 0, 0)

        # Login type selection
        type_layout = QHBoxLayout()
        type_label = QLabel(t("qqmusic_login_method"))
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

        qr_panel_layout.addLayout(type_layout)

        # Status label (above QR code)
        self._status_label = QLabel(t("qqmusic_loading_qr"))
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet(f"font-size: 14px; color: {theme.highlight}; padding: 8px; font-weight: bold;")
        qr_panel_layout.addWidget(self._status_label)

        # QR code container
        qr_container = QWidget()
        qr_layout = QVBoxLayout(qr_container)
        qr_layout.setContentsMargins(0, 0, 0, 0)

        # QR code image
        self._qr_label = QLabel()
        self._qr_label.setMinimumSize(300, 300)
        self._qr_label.setMaximumSize(300, 300)
        self._qr_label.setAlignment(Qt.AlignCenter)
        self._qr_label.setStyleSheet(
            f"border: 2px solid {theme.background_hover}; border-radius: 8px; background: #ffffff;")
        qr_layout.addWidget(self._qr_label)

        qr_panel_layout.addWidget(qr_container, alignment=Qt.AlignCenter)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setRange(0, 0)  # Indeterminate progress
        self._progress_bar.setMaximumHeight(4)
        self._progress_bar.hide()
        qr_panel_layout.addWidget(self._progress_bar)

        # Instructions
        self._instructions_label = QLabel()
        self._instructions_label.setAlignment(Qt.AlignCenter)
        self._instructions_label.setStyleSheet(f"color: {theme.text_secondary}; font-size: 12px;")
        self._update_instructions()
        qr_panel_layout.addWidget(self._instructions_label)

        # Buttons
        button_layout = QHBoxLayout()

        self._refresh_button = QPushButton(t("qqmusic_refresh_qr"))
        self._refresh_button.setObjectName("qqmusicRefreshBtn")
        self._refresh_button.setCursor(Qt.PointingHandCursor)
        self._refresh_button.clicked.connect(self._refresh_qr)
        self._refresh_button.setEnabled(False)
        button_layout.addWidget(self._refresh_button)
        qr_panel_layout.addLayout(button_layout)
        layout.addWidget(self._qr_panel)

        self._phone_panel = QWidget()
        phone_panel_layout = QVBoxLayout(self._phone_panel)
        phone_panel_layout.setContentsMargins(0, 0, 0, 0)

        self._country_code_label = QLabel("+86")
        self._phone_input = QLineEdit()
        self._phone_code_input = QLineEdit()
        self._phone_status_label = QLabel("")
        self._phone_status_label.setWordWrap(True)
        self._phone_status_label.setStyleSheet(f"font-size: 12px; color: {theme.text_secondary};")
        self._phone_send_code_btn = QPushButton(t("qqmusic_send_code"))
        self._phone_submit_btn = QPushButton(t("qqmusic_login"))
        self._phone_send_code_btn.clicked.connect(self._send_phone_auth_code)
        self._phone_submit_btn.clicked.connect(self._submit_phone_login)

        phone_input_layout = QHBoxLayout()
        phone_input_layout.addWidget(self._country_code_label)
        phone_input_layout.addWidget(self._phone_input)
        phone_panel_layout.addWidget(QLabel(t("qqmusic_phone_number")))
        phone_panel_layout.addLayout(phone_input_layout)
        phone_panel_layout.addWidget(QLabel(t("qqmusic_phone_code")))
        phone_panel_layout.addWidget(self._phone_code_input)

        phone_button_layout = QHBoxLayout()
        phone_button_layout.addWidget(self._phone_send_code_btn)
        phone_button_layout.addWidget(self._phone_submit_btn)
        phone_panel_layout.addLayout(phone_button_layout)
        phone_panel_layout.addWidget(self._phone_status_label)
        phone_panel_layout.addWidget(QLabel(t("qqmusic_phone_hint")))
        layout.addWidget(self._phone_panel)
        self._phone_panel.hide()

        footer_layout = QHBoxLayout()
        footer_layout.addStretch()
        self._cancel_button = QPushButton(t("cancel"))
        self._cancel_button.setProperty("role", "cancel")
        self._cancel_button.setCursor(Qt.PointingHandCursor)
        self._cancel_button.clicked.connect(self._cancel_login)
        footer_layout.addWidget(self._cancel_button)
        layout.addLayout(footer_layout)

    def _connect_language_events(self) -> None:
        events = getattr(self._context, "events", None) if self._context is not None else None
        if events is None or self._language_connected:
            return
        signal = getattr(events, "language_changed", None)
        if signal is None:
            return
        signal.connect(self._on_language_changed)
        self._language_connected = True

    def _sync_language_from_context(self) -> None:
        if self._context is None or self._language_connected:
            return
        lang = str(getattr(self._context, "language", get_language()) or get_language())
        if lang != get_language():
            set_language(lang)

    def _on_language_changed(self, language: str) -> None:
        if language and language != get_language():
            set_language(language)
        self._language_connected = True

    def _stop_qr_login_thread(self):
        if self._login_thread:
            self._login_thread.stop()
            self._retire_login_thread(self._login_thread)
            self._login_thread = None

    def _on_login_mode_changed(self):
        self._login_mode = "phone" if self._phone_mode_btn.isChecked() else "qr"
        self._qr_panel.setVisible(self._login_mode == "qr")
        self._phone_panel.setVisible(self._login_mode == "phone")
        if self._login_mode == "qr":
            self._restart_login()
        else:
            self._stop_qr_login_thread()

    def _on_login_type_changed(self):
        """Handle login type radio button change."""
        if self._qq_radio.isChecked():
            self._login_type = 'qq'
        else:
            self._login_type = 'wx'

        # Update instructions text
        self._update_instructions()
        # Restart login with new type
        if self._login_mode == "qr":
            self._restart_login()

    def _set_phone_status(self, message: str, *, error: bool = False):
        theme = current_theme()
        color = "#ff6b6b" if error else theme.text_secondary
        self._phone_status_label.setStyleSheet(f"font-size: 12px; color: {color};")
        self._phone_status_label.setText(message)

    def _validate_phone_number(self) -> bool:
        phone = str(self._phone_input.text() or "").strip()
        if not re.fullmatch(r"1\d{10}", phone):
            self._set_phone_status(t("qqmusic_phone_invalid"), error=True)
            return False
        return True

    def _validate_auth_code(self) -> bool:
        code = str(self._phone_code_input.text() or "").strip()
        if not re.fullmatch(r"\d{4,6}", code):
            self._set_phone_status(t("qqmusic_code_invalid"), error=True)
            return False
        return True

    def _map_phone_login_error(self, exc: Exception) -> str:
        message = str(exc)
        if "20276" in message:
            return t("qqmusic_phone_frequency")
        if "20274" in message:
            return t("qqmusic_phone_device_limit")
        if "20271" in message:
            return t("qqmusic_phone_code_error")
        if "captcha" in message.lower() or "verify" in message.lower():
            return t("qqmusic_phone_captcha_required")
        return f"{t('qqmusic_login_failed')}: {message}" if message else t("qqmusic_login_failed")

    def _update_instructions(self):
        """Update instructions based on login type."""
        app_name = "WeChat" if self._login_type == 'wx' else "QQ"
        if get_language() == "zh":
            app_name = "微信" if self._login_type == 'wx' else "QQ"
        self._instructions_label.setText(t("qqmusic_instructions").format(app=app_name))

    def _restart_login(self):
        """Restart login process - stop old thread and start new one."""
        old_thread = self._login_thread
        self._login_thread = None

        if old_thread:
            old_thread.stop()
            self._retire_login_thread(old_thread)

        self._start_login()

    def _retire_login_thread(self, thread: QRLoginThread | None) -> None:
        if thread is None or thread in self._retired_login_threads:
            return
        self._retired_login_threads.append(thread)

    def _dispatch_thread_event(self, thread, callback, *args) -> bool:
        if thread is not self._login_thread:
            return False
        callback(*args)
        return True

    def _start_login(self):
        """Start QR code login process."""
        self._progress_bar.show()
        self._refresh_button.setEnabled(False)
        self._qr_label.clear()
        self._status_label.setText(t("qqmusic_fetching_qr"))

        thread = QRLoginThread(self._login_type, http_client=self._context.http)
        thread.qr_code_ready.connect(
            lambda data, current=thread: self._dispatch_thread_event(
                current,
                self._on_qr_code_ready,
                data,
            )
        )
        thread.login_success.connect(
            lambda credential, current=thread: self._dispatch_thread_event(
                current,
                self._on_login_success,
                credential,
            )
        )
        thread.login_failed.connect(
            lambda error, current=thread: self._dispatch_thread_event(
                current,
                self._on_login_failed,
                error,
            )
        )
        thread.login_refused.connect(
            lambda current=thread: self._dispatch_thread_event(
                current,
                self._on_login_refused,
            )
        )
        thread.login_timeout.connect(
            lambda current=thread: self._dispatch_thread_event(
                current,
                self._on_login_timeout,
            )
        )
        thread.status_update.connect(
            lambda status, current=thread: self._dispatch_thread_event(
                current,
                self._on_status_update,
                status,
            )
        )
        thread.finished.connect(lambda current=thread: self._on_thread_finished(current))

        self._login_thread = thread
        thread.start()

    def _on_thread_finished(self, thread):
        """Handle thread finished event."""
        if self._login_thread is thread:
            self._login_thread = None
        if thread in self._retired_login_threads:
            self._retired_login_threads.remove(thread)
        thread.deleteLater()

    def _refresh_qr(self):
        """Refresh QR code."""
        # Disable refresh button to prevent double-click
        self._refresh_button.setEnabled(False)
        self._restart_login()

    def _send_phone_auth_code(self):
        if not self._validate_phone_number():
            return
        try:
            self._phone_client.send_phone_auth_code(self._phone_input.text().strip(), 86)
        except Exception as exc:
            self._set_phone_status(self._map_phone_login_error(exc), error=True)
            return
        self._set_phone_status(t("qqmusic_code_sent"))

    def _finish_login_success(self, credential: dict):
        self._context.settings.set("credential", credential)

        nick = credential.get("nick") or credential.get("nickname") or ""
        if not nick:
            try:
                from .qqmusic_service import QQMusicService
                service = QQMusicService(credential, http_client=getattr(self._context, "http", None))
                verify_result = service.client.verify_login()
                if isinstance(verify_result, dict) and verify_result.get("valid"):
                    nick = str(verify_result.get("nick", "") or "")
            except Exception as exc:
                logger.warning(f"Failed to get QQ Music nickname: {exc}")
        if nick:
            self._context.settings.set("nick", nick)
            logger.info(f"Got QQ Music nickname: {nick}")

        show_information(
            self,
            t("success"),
            t("qqmusic_login_success")
        )

        self.credentials_obtained.emit(credential)
        self.accept()

    def _submit_phone_login(self):
        if not self._validate_phone_number() or not self._validate_auth_code():
            return
        try:
            credential = self._phone_client.phone_authorize(
                self._phone_input.text().strip(),
                self._phone_code_input.text().strip(),
                86,
            )
        except Exception as exc:
            self._set_phone_status(self._map_phone_login_error(exc), error=True)
            return
        self._finish_login_success(credential)

    def _cancel_login(self):
        """Cancel login and close dialog."""
        if self._login_thread:
            self._login_thread.stop()
            self._retire_login_thread(self._login_thread)
            self._login_thread = None
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
            self._retire_login_thread(self._login_thread)
            self._login_thread = None
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
        self._status_label.setText(
            t("qqmusic_login_success") if t('language') != '中文' else "登录成功！正在保存凭证...")

        try:
            self._finish_login_success(credential)
        except Exception as e:
            logger.error(f"Failed to save credentials: {e}")
            show_warning(
                self,
                t("error"),
                f"{t('error')}:\n{str(e)}"
            )

    @Slot(str)
    def _on_login_failed(self, error: str):
        """Handle login failed event."""
        self._progress_bar.hide()
        self._status_label.setText(t("qqmusic_login_failed"))
        show_warning(self, t("qqmusic_login_failed"), error)

    @Slot()
    def _on_login_refused(self):
        """Handle login refused event."""
        self._progress_bar.hide()
        self._status_label.setText(t("qqmusic_user_cancelled"))
        show_information(self, t("cancel"), t("qqmusic_you_cancelled"))

    @Slot()
    def _on_login_timeout(self):
        """Handle login timeout event."""
        self._progress_bar.hide()
        self._status_label.setText(t("qqmusic_qr_expired"))
        self._refresh_button.setEnabled(True)
        show_information(
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
        self.setStyleSheet(get_qss(self._STYLE_TEMPLATE))
        self._title_bar_controller.refresh_theme()
        theme = current_theme()
        if self._status_label:
            self._status_label.setStyleSheet(
                f"font-size: 14px; color: {theme.highlight}; padding: 8px; font-weight: bold;")
        if self._qr_label:
            self._qr_label.setStyleSheet(
                f"border: 2px solid {theme.background_hover}; border-radius: 8px; background: #ffffff;")
        if self._instructions_label:
            self._instructions_label.setStyleSheet(f"color: {theme.text_secondary}; font-size: 12px;")
