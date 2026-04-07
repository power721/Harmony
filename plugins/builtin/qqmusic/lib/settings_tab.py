from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .common import get_quality_label_key, get_selectable_qualities
from .i18n import get_language, set_language, t
from .login_dialog import QQMusicLoginDialog
from .runtime_bridge import current_theme as sdk_current_theme, register_themed_widget

logger = logging.getLogger(__name__)


class VerifyLoginThread(QThread):
    verified = Signal(bool, str, int)

    def __init__(self, credential: dict, parent=None):
        super().__init__(parent)
        self._credential = credential

    def run(self):
        try:
            from .legacy.qqmusic_service import QQMusicService

            service = QQMusicService(self._credential)
            result = service.client.verify_login()
            self.verified.emit(
                bool(result.get("valid")),
                str(result.get("nick", "") or ""),
                int(result.get("uin", 0) or 0),
            )
        except Exception as exc:
            logger.debug("Settings tab: verify login failed: %s", exc)
            self.verified.emit(False, "", 0)


class QQMusicSettingsTab(QWidget):
    _STYLE_GROUP = """
        QGroupBox {
            color: %text%;
            border: 1px solid %border%;
            border-radius: 6px;
            margin-top: 10px;
            padding-top: 10px;
            font-size: 13px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 8px;
            color: %text%;
        }
    """
    _STYLE_STATUS = """
        QLabel {
            color: %text_secondary%;
            font-size: 13px;
            padding: 4px 0;
        }
    """
    _STYLE_BUTTON = """
        QPushButton {
            background-color: %background_hover%;
            color: %text%;
            border: 1px solid %border%;
            border-radius: 4px;
            padding: 8px 16px;
            font-size: 13px;
        }
        QPushButton:hover {
            background-color: %selection%;
        }
    """
    _STYLE_INPUT = """
        QLineEdit, QComboBox {
            background-color: %background%;
            color: %text%;
            border: 1px solid %border%;
            border-radius: 4px;
            padding: 8px;
            font-size: 13px;
        }
        QLineEdit:focus, QComboBox:focus {
            border-color: %highlight%;
        }
    """

    def __init__(self, context, parent=None):
        super().__init__(parent)
        self._context = context
        self._language_connected = False
        self._verify_thread: Optional[VerifyLoginThread] = None

        self._outer_layout = QVBoxLayout(self)
        self._outer_layout.setContentsMargins(0, 0, 0, 0)

        self._setup_ui()
        self._load_settings()
        self._connect_language_events()

        ui = getattr(self._context, "ui", None)
        if ui is not None and hasattr(ui, "theme") and hasattr(ui.theme, "register_widget"):
            ui.theme.register_widget(self)
        else:
            register_themed_widget(self)

        self.refresh_ui()

    def _setup_ui(self):
        # QQ Music Settings Tab
        self._qqmusic_tab = QWidget()
        self._outer_layout.addWidget(self._qqmusic_tab)

        qqmusic_layout = QVBoxLayout(self._qqmusic_tab)
        qqmusic_layout.setContentsMargins(9, 9, 9, 9)
        qqmusic_layout.setSpacing(10)

        # Quality settings
        self._quality_group = QGroupBox(t("qqmusic_quality"))
        quality_layout = QHBoxLayout()
        self._quality_label = QLabel(t("qqmusic_quality"))
        self._quality_combo = QComboBox()
        self._quality_combo.setFixedWidth(300)
        for quality in get_selectable_qualities():
            label_key = get_quality_label_key(quality)
            label = t(label_key, quality)
            self._quality_combo.addItem(label)
            self._quality_combo.setItemData(self._quality_combo.count() - 1, quality, Qt.UserRole)
        self._quality_combo.currentIndexChanged.connect(lambda *_args: self._save_settings())
        quality_layout.addWidget(self._quality_label)
        quality_layout.addWidget(self._quality_combo)
        quality_layout.addStretch()
        self._quality_group.setLayout(quality_layout)
        qqmusic_layout.addWidget(self._quality_group)

        # Download directory settings
        self._download_dir_group = QGroupBox(t("online_music_download_dir", "下载目录"))
        download_dir_layout = QHBoxLayout()
        self._download_dir_label = QLabel(t("online_music_download_dir", "下载目录"))
        self._download_dir_input = QLineEdit()
        self._download_dir_input.setPlaceholderText("data/online_cache")
        self._download_dir_input.editingFinished.connect(self._save_settings)
        self._browse_btn = QPushButton(t("online_music_browse", "浏览..."))
        self._browse_btn.setCursor(Qt.PointingHandCursor)
        self._browse_btn.clicked.connect(self._browse_download_dir)
        download_dir_layout.addWidget(self._download_dir_label)
        download_dir_layout.addWidget(self._download_dir_input)
        download_dir_layout.addWidget(self._browse_btn)
        self._download_dir_group.setLayout(download_dir_layout)
        qqmusic_layout.addWidget(self._download_dir_group)

        # Hint label for download directory
        self._download_dir_hint = QLabel(t("online_music_download_dir_hint", "设置在线音乐缓存和下载目录"))
        self._download_dir_hint.setStyleSheet("font-size: 11px;")
        self._download_dir_hint.setWordWrap(True)
        qqmusic_layout.addWidget(self._download_dir_hint)

        # QQ Music instructions
        self._qqmusic_instructions_label = QLabel(
            f"<b>{t('qqmusic_login')}</b><br><br>"
            f"{t('qqmusic_faster_api_hint', t('qqmusic_account_hint'))}"
        )
        self._qqmusic_instructions_label.setWordWrap(True)
        qqmusic_layout.addWidget(self._qqmusic_instructions_label)

        # QQ Music credential status
        self._qqmusic_status_label = QLabel()
        self._qqmusic_status_label.setWordWrap(True)
        qqmusic_layout.addWidget(self._qqmusic_status_label)
        self._status_label = self._qqmusic_status_label

        # QQ Music buttons
        qqmusic_button_layout = QHBoxLayout()

        self._qqmusic_qr_btn = QPushButton(t("qqmusic_qr_login", t("qqmusic_login")))
        self._qqmusic_qr_btn.setCursor(Qt.PointingHandCursor)
        self._qqmusic_qr_btn.clicked.connect(self._open_qqmusic_qr_login)
        qqmusic_button_layout.addWidget(self._qqmusic_qr_btn)

        self._qqmusic_logout_btn = QPushButton(t("qqmusic_clear", t("clear_credentials")))
        self._qqmusic_logout_btn.setCursor(Qt.PointingHandCursor)
        self._qqmusic_logout_btn.clicked.connect(self._qqmusic_logout)
        qqmusic_button_layout.addWidget(self._qqmusic_logout_btn)

        qqmusic_layout.addLayout(qqmusic_button_layout)

        # Update status after buttons are created
        self._update_qqmusic_status()

        qqmusic_layout.addStretch()

    def _theme_get_qss(self, template: str) -> str:
        ui = getattr(self._context, "ui", None)
        if ui is not None and hasattr(ui, "theme") and hasattr(ui.theme, "get_qss"):
            return ui.theme.get_qss(template)
        return template

    def _theme_current(self):
        ui = getattr(self._context, "ui", None)
        if ui is not None and hasattr(ui, "theme") and hasattr(ui.theme, "current_theme"):
            return ui.theme.current_theme()
        return sdk_current_theme()

    def _connect_language_events(self) -> None:
        events = getattr(self._context, "events", None)
        if events is None or self._language_connected:
            return
        signal = getattr(events, "language_changed", None)
        if signal is None:
            return
        signal.connect(self._on_language_changed)
        self._language_connected = True

    def _sync_language_from_context(self) -> None:
        if self._language_connected:
            return
        lang = str(getattr(self._context, "language", get_language()) or get_language())
        if lang != get_language():
            set_language(lang)

    def _on_language_changed(self, language: str) -> None:
        if language and language != get_language():
            set_language(language)
        self._language_connected = True
        self.refresh_ui()

    def _load_settings(self) -> None:
        quality = str(self._context.settings.get("quality", "320"))
        for i in range(self._quality_combo.count()):
            if self._quality_combo.itemData(i, Qt.UserRole) == quality:
                self._quality_combo.setCurrentIndex(i)
                break

        download_dir = str(
            self._context.settings.get("download_dir", "data/online_cache")
            or "data/online_cache"
        )
        self._download_dir_input.setText(download_dir)

    def _save(self):
        self._save_settings()

    def _save_settings(self) -> None:
        self._context.settings.set("quality", self._quality_combo.currentData(Qt.UserRole))
        self._context.settings.set(
            "download_dir",
            self._download_dir_input.text().strip() or "data/online_cache",
        )

    def _browse_download_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            t("online_music_select_dir", "选择下载目录"),
            self._download_dir_input.text().strip() or "data/online_cache",
        )
        if path:
            self._download_dir_input.setText(path)
            self._save_settings()

    def _update_qqmusic_status(self):
        credential = self._context.settings.get("credential", None)
        if credential:
            musicid = credential.get("musicid", "")
            login_type = credential.get("loginType", credential.get("login_type", 2))
            login_method = t("qqmusic_wx_login") if login_type == 1 else t("qqmusic_qq_login")

            if musicid:
                self._qqmusic_status_label.setText(
                    f"⏳ {t('qqmusic_verifying', '正在验证...')} ({login_method}: {musicid})"
                )
                self._qqmusic_logout_btn.setVisible(True)

                if self._verify_thread:
                    self._verify_thread.quit()
                    self._verify_thread.wait()

                self._verify_thread = VerifyLoginThread(credential, parent=self)
                self._verify_thread.verified.connect(
                    lambda valid, nick, uin, musicid=musicid, login_type=login_type: self._on_login_verified(
                        valid, nick, uin, musicid, login_type
                    )
                )
                self._verify_thread.start()
            else:
                self._qqmusic_status_label.setText(
                    f"⚠️ {t('qqmusic_incomplete_config', '配置不完整')}"
                )
                self._qqmusic_logout_btn.setVisible(False)
        else:
            self._qqmusic_status_label.setText(
                f"❌ {t('qqmusic_not_configured_status', t('qqmusic_not_logged_in'))}"
            )
            self._qqmusic_logout_btn.setVisible(False)

    def _on_login_verified(
        self,
        valid: bool,
        nick: str,
        _uin: int,
        musicid: str,
        login_type: int = 2,
    ):
        login_method = t("qqmusic_wx_login") if login_type == 1 else t("qqmusic_qq_login")

        if valid:
            if nick:
                self._context.settings.set("nick", nick)
            display_name = nick or self._context.settings.get("nick", "") or musicid
            self._qqmusic_status_label.setText(
                f"✅ {t('qqmusic_logged_in_status', t('qqmusic_logged_in'))} ({display_name}, {login_method}: {musicid})"
            )
        else:
            self._qqmusic_status_label.setText(
                f"❌ {t('qqmusic_login_expired', '登录已失效')} ({login_method}: {musicid})"
            )

    def _open_qqmusic_qr_login(self):
        dialog = QQMusicLoginDialog(self._context, self)
        dialog.credentials_obtained.connect(lambda _credential: self._update_qqmusic_status())
        dialog.exec()
        self._update_qqmusic_status()

    def _open_login_dialog(self):
        self._open_qqmusic_qr_login()

    def _qqmusic_logout(self):
        self._context.settings.set("credential", None)
        self._context.settings.set("nick", "")
        self._update_qqmusic_status()

    def _clear_credentials(self):
        self._qqmusic_logout()

    def refresh_ui(self) -> None:
        self._sync_language_from_context()
        self._quality_group.setTitle(t("qqmusic_quality"))
        self._quality_label.setText(t("qqmusic_quality"))
        self._download_dir_group.setTitle(t("online_music_download_dir", "下载目录"))
        self._download_dir_label.setText(t("online_music_download_dir", "下载目录"))
        self._browse_btn.setText(t("online_music_browse", "浏览..."))
        self._download_dir_hint.setText(
            t("online_music_download_dir_hint", "设置在线音乐缓存和下载目录")
        )
        self._qqmusic_instructions_label.setText(
            f"<b>{t('qqmusic_login')}</b><br><br>"
            f"{t('qqmusic_faster_api_hint', t('qqmusic_account_hint'))}"
        )
        self._qqmusic_qr_btn.setText(t("qqmusic_qr_login", t("qqmusic_login")))
        self._qqmusic_logout_btn.setText(t("qqmusic_clear", t("clear_credentials")))
        self._update_qqmusic_status()
        self.refresh_theme()

    def refresh_theme(self) -> None:
        qss = self._theme_get_qss
        theme = self._theme_current()

        self._quality_group.setStyleSheet(qss(self._STYLE_GROUP))
        self._download_dir_group.setStyleSheet(qss(self._STYLE_GROUP))
        self._quality_label.setStyleSheet(qss(self._STYLE_STATUS))
        self._download_dir_label.setStyleSheet(qss(self._STYLE_STATUS))
        self._qqmusic_status_label.setStyleSheet(qss(self._STYLE_STATUS))
        self._quality_combo.setStyleSheet(qss(self._STYLE_INPUT))
        self._download_dir_input.setStyleSheet(qss(self._STYLE_INPUT))
        for button in (self._browse_btn, self._qqmusic_qr_btn, self._qqmusic_logout_btn):
            button.setStyleSheet(qss(self._STYLE_BUTTON))
        self._download_dir_hint.setStyleSheet(f"color: {theme.text_secondary}; font-size: 11px;")
        self._qqmusic_instructions_label.setStyleSheet(f"color: {theme.text};")
