"""
Context menu handler for cloud file operations.
"""

import logging
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from PySide6.QtWidgets import QMenu
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QCursor

from domain.cloud import CloudFile
from system.i18n import t
from utils import format_duration

if TYPE_CHECKING:
    from services.cloud import CloudFileService
    from services.metadata import CoverService
    from system.config import ConfigManager

logger = logging.getLogger(__name__)


class CloudFileContextMenu(QObject):
    """
    Context menu handler for cloud files.

    Provides a clean interface for showing context menus and
    emits signals for actions that need to be handled by the parent.

    Signals:
        play_requested: Emitted when user wants to play a file
        insert_to_queue_requested: Emitted when user wants to insert file after current
        add_to_queue_requested: Emitted when user wants to add file to queue
        download_requested: Emitted when user wants to download a file
        edit_media_info_requested: Emitted when user wants to edit media info
        download_cover_requested: Emitted when user wants to download cover
        open_file_location_requested: Emitted when user wants to open file location
        open_in_cloud_requested: Emitted when user wants to open in cloud drive
    """

    _STYLE_TEMPLATE = """
        QMenu {
            background-color: %background_hover%;
            color: %text%;
            border: 1px solid %border%;
            border-radius: 6px;
            padding: 4px;
        }
        QMenu::item {
            padding: 8px 20px;
            border-radius: 4px;
        }
        QMenu::item:selected {
            background-color: %highlight%;
            color: #000000;
        }
        QMenu::item:disabled {
            color: %text_secondary%;
        }
    """

    play_requested = Signal(CloudFile)
    insert_to_queue_requested = Signal(CloudFile)
    add_to_queue_requested = Signal(CloudFile)
    download_requested = Signal(CloudFile)
    edit_media_info_requested = Signal(CloudFile)
    download_cover_requested = Signal(CloudFile)
    open_file_location_requested = Signal(CloudFile)
    open_in_cloud_requested = Signal(CloudFile)

    def __init__(
        self,
        cloud_file_service: "CloudFileService" = None,
        cover_service: "CoverService" = None,
        parent=None
    ):
        """
        Initialize context menu handler.

        Args:
            cloud_file_service: Service for checking file download status
            cover_service: Service for cover art operations
            parent: Parent QObject
        """
        super().__init__(parent)
        self._cloud_file_service = cloud_file_service
        self._cover_service = cover_service
        self._menu_style = ""

    def show_menu(self, file: CloudFile, current_audio_files: list = None, account_id: int = None):
        """
        Show the context menu for a file.

        Args:
            file: CloudFile to show menu for
            current_audio_files: List of current audio files (for updating local paths)
            account_id: Current account ID
        """
        if file.file_type != "audio":
            return

        # Check if file has been downloaded
        has_local_path = self._check_file_downloaded(file, current_audio_files, account_id)

        menu = QMenu()
        from system.theme import ThemeManager
        menu.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TEMPLATE))

        # Play action
        play_action = menu.addAction(t("play"))
        play_action.triggered.connect(lambda: self.play_requested.emit(file))

        menu.addSeparator()

        # File info display (non-clickable)
        info_text = self._build_info_text(file)
        info_action = menu.addAction(info_text)
        info_action.setEnabled(False)

        menu.addSeparator()

        # Queue actions
        insert_action = menu.addAction(t("insert_to_queue"))
        insert_action.triggered.connect(lambda: self.insert_to_queue_requested.emit(file))

        queue_action = menu.addAction(t("add_to_queue"))
        queue_action.triggered.connect(lambda: self.add_to_queue_requested.emit(file))

        menu.addSeparator()

        # Download action
        if has_local_path:
            download_action = menu.addAction(f"✓ {t('download')}")
            download_action.setEnabled(False)
        else:
            download_action = menu.addAction(f"⬇ {t('download')}")
            download_action.triggered.connect(lambda: self.download_requested.emit(file))

        menu.addSeparator()

        # Edit media info action
        edit_action = menu.addAction(t("edit_media_info"))
        if has_local_path:
            edit_action.triggered.connect(lambda: self.edit_media_info_requested.emit(file))
        else:
            edit_action.setEnabled(False)
            edit_action.setText(f"{t('edit_media_info')} ({t('download_first')})")

        # Download cover action
        if self._cover_service:
            download_cover_action = menu.addAction(t("download_cover_manual"))
            if has_local_path:
                download_cover_action.triggered.connect(
                    lambda: self.download_cover_requested.emit(file)
                )
            else:
                download_cover_action.setEnabled(False)
                download_cover_action.setText(
                    f"{t('download_cover_manual')} ({t('download_first')})"
                )

        # Open file location action
        open_action = menu.addAction(t("open_file_location"))
        if has_local_path:
            open_action.triggered.connect(lambda: self.open_file_location_requested.emit(file))
        else:
            open_action.setEnabled(False)
            open_action.setText(f"{t('open_file_location')} ({t('download_first')})")

        # Open in cloud drive action
        open_cloud_action = menu.addAction(t("open_in_cloud_drive"))
        open_cloud_action.triggered.connect(lambda: self.open_in_cloud_requested.emit(file))

        menu.exec_(QCursor.pos())

    def _check_file_downloaded(
        self,
        file: CloudFile,
        current_audio_files: list = None,
        account_id: int = None
    ) -> bool:
        """
        Check if a file has been downloaded.

        Args:
            file: CloudFile to check
            current_audio_files: List of current audio files
            account_id: Current account ID

        Returns:
            True if file has a valid local path
        """
        has_local_path = False

        # Check memory first
        if file.local_path:
            if Path(file.local_path).exists():
                has_local_path = True
            else:
                file.local_path = None

        # Check database if not found
        if not has_local_path and self._cloud_file_service and account_id:
            db_file = self._cloud_file_service.get_file_by_file_id(file.file_id)
            if db_file and db_file.local_path:
                if Path(db_file.local_path).exists():
                    file.local_path = db_file.local_path
                    has_local_path = True

                    # Update in current audio files list
                    if current_audio_files:
                        for audio_file in current_audio_files:
                            if audio_file.file_id == file.file_id:
                                audio_file.local_path = db_file.local_path
                                break

        return has_local_path

    def _build_info_text(self, file: CloudFile) -> str:
        """Build the info text for the context menu."""
        info_text = f"ℹ️ {t('file_info')}"
        if file.size:
            size_mb = file.size / (1024 * 1024)
            info_text += f" ({size_mb:.1f} MB)"
        if file.duration:
            info_text += f" - {format_duration(file.duration)}"
        return info_text


class CloudAccountContextMenu(QObject):
    """
    Context menu handler for cloud accounts.

    Signals:
        get_info_requested: Emitted when user wants to get account info
        change_download_dir_requested: Emitted when user wants to change download directory
        update_cookie_requested: Emitted when user wants to update cookie
        delete_requested: Emitted when user wants to delete account
    """

    _STYLE_TEMPLATE = """
        QMenu {
            background-color: %background_hover%;
            color: %text%;
            border: 1px solid %border%;
            border-radius: 6px;
            padding: 4px;
        }
        QMenu::item {
            padding: 8px 20px;
            border-radius: 4px;
        }
        QMenu::item:selected {
            background-color: %highlight%;
            color: #000000;
        }
    """

    get_info_requested = Signal(object)  # CloudAccount
    change_download_dir_requested = Signal()
    update_cookie_requested = Signal(object)  # CloudAccount
    delete_requested = Signal(object)  # CloudAccount

    def __init__(self, parent=None):
        super().__init__(parent)
        self._menu_style = ""

    def show_menu(self, account):
        """Show context menu for an account."""
        menu = QMenu()
        from system.theme import ThemeManager
        menu.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TEMPLATE))

        # Account info action
        info_action = menu.addAction("ℹ️ " + t("get_account_info"))
        info_action.triggered.connect(lambda: self.get_info_requested.emit(account))

        menu.addSeparator()

        # Change download directory action
        change_dir_action = menu.addAction("📁 " + t("change_download_dir"))
        change_dir_action.triggered.connect(lambda: self.change_download_dir_requested.emit())

        # Update cookie action
        update_cookie_action = menu.addAction("🔑 " + t("update_cookie"))
        update_cookie_action.triggered.connect(lambda: self.update_cookie_requested.emit(account))

        menu.addSeparator()

        # Delete action
        delete_action = menu.addAction("🗑️ " + t("delete_account"))
        delete_action.triggered.connect(lambda: self.delete_requested.emit(account))

        menu.exec_(QCursor.pos())
