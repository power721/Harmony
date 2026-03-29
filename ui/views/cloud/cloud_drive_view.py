"""
Cloud drive view for browsing and playing cloud files.

This is a refactored version that uses modular components:
- CloudFileTable: File listing with playing indicator
- CloudFileDownloadThread: Background download
- CloudMediaInfoDialog: Media info editing
- CloudFileContextMenu: Right-click menu handling
"""

import logging
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QAbstractItemView,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QDialog,
)
from PySide6.QtCore import Qt, Signal, QTimer

from ui.dialogs.message_dialog import MessageDialog, Yes, No

from domain.cloud import CloudAccount, CloudFile
from services.cloud.quark_service import QuarkDriveService
from services.cloud.baidu_service import BaiduDriveService
from ui.dialogs.cloud_login_dialog import CloudLoginDialog
from ui.dialogs.provider_select_dialog import ProviderSelectDialog
from system.i18n import t
from system.event_bus import EventBus

from .file_table import CloudFileTable
from .download_thread import CloudFileDownloadThread
from .dialogs import show_media_info_dialog
from .context_menu import CloudFileContextMenu, CloudAccountContextMenu

if TYPE_CHECKING:
    from services.cloud import CloudAccountService, CloudFileService
    from services.library import LibraryService
    from services.playback import PlaybackService
    from services.metadata import CoverService
    from system.config import ConfigManager

logger = logging.getLogger(__name__)


class CloudDriveView(QWidget):
    """
    View for browsing and playing cloud drive files.

    This view coordinates between:
    - CloudAccountService: Account management
    - CloudFileService: File metadata
    - LibraryService: Track database
    - PlaybackService: Audio playback

    Signals:
        track_double_clicked: Emitted when a track is double-clicked (temp file path)
        play_cloud_files: Emitted to play multiple cloud files
    """

    _STYLE_TEMPLATE = """
        QLabel#accountListTitle {
            color: %highlight%;
            font-size: 20px;
            font-weight: bold;
            margin-bottom: 10px;
        }
        QPushButton#addAccountBtn {
            background-color: %highlight%;
            color: %background%;
            border: none;
            padding: 10px 15px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 13px;
        }
        QPushButton#addAccountBtn:hover {
            background-color: %highlight_hover%;
        }
        QListWidget#accountList {
            background: transparent;
            border: none;
        }
        QListWidget#accountList::item {
            padding: 12px;
            color: %text_secondary%;
            border-radius: 8px;
            margin: 2px 0px;
        }
        QListWidget#accountList::item:selected {
            background-color: %highlight%;
            color: %background%;
            font-weight: bold;
        }
        QListWidget#accountList::item:hover {
            background-color: %background_hover%;
            color: %highlight%;
        }
        QListWidget#accountList::item:selected:hover {
            background-color: %highlight_hover%;
            color: %background%;
        }
        QLabel#accountTitle {
            color: %highlight%;
            font-size: 24px;
            font-weight: bold;
        }
        QLabel#pathLabel {
            color: %text_secondary%;
            font-size: 14px;
            padding: 0 10px;
        }
        QLabel#emptyLabel {
            color: %text_secondary%;
            font-size: 14px;
        }
        QLabel#statusLabel {
            color: %text_secondary%;
            font-size: 12px;
            padding: 5px;
        }
    """

    track_double_clicked = Signal(str)
    play_cloud_files = Signal(str, int, list, float)

    def __init__(
        self,
        cloud_account_service: "CloudAccountService",
        cloud_file_service: "CloudFileService",
        library_service: "LibraryService",
        player: "PlaybackService",
        config_manager: "ConfigManager" = None,
        cover_service: "CoverService" = None,
        parent=None
    ):
        """
        Initialize the cloud drive view.

        Args:
            cloud_account_service: Service for cloud account management
            cloud_file_service: Service for cloud file operations
            library_service: Service for library operations
            player: Playback service for audio control
            config_manager: Configuration manager
            cover_service: Service for cover art operations
            parent: Parent widget
        """
        super().__init__(parent)

        # Services
        self._cloud_account_service = cloud_account_service
        self._cloud_file_service = cloud_file_service
        self._library_service = library_service
        self._player = player
        self._config_manager = config_manager
        self._cover_service = cover_service

        # State
        self._current_account: Optional[CloudAccount] = None
        self._current_parent_id = "0"
        self._navigation_history = []
        self._current_audio_files: List[CloudFile] = []
        self._last_playing_fid = ""
        self._last_position = 0.0
        self._fid_path = []
        self._current_playing_file_id = ""
        self._data_loaded = False

        # Context menus
        self._file_context_menu = CloudFileContextMenu(
            cloud_file_service=cloud_file_service,
            cover_service=cover_service,
            parent=self
        )
        self._account_context_menu = CloudAccountContextMenu(parent=self)

        # Register for theme change notifications
        from system.theme import ThemeManager
        ThemeManager.instance().register_widget(self)

        # Setup UI
        self._setup_ui()
        self._setup_connections()
        self._setup_event_bus()

        # Apply themed stylesheet
        self.refresh_theme()

    def _setup_ui(self):
        """Setup the main UI layout."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Splitter for account list and file list
        splitter = QSplitter(Qt.Horizontal)

        # Left side - account list
        account_list_widget = self._create_account_list()
        splitter.addWidget(account_list_widget)

        # Right side - file content
        file_content = self._create_file_content()
        splitter.addWidget(file_content)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        layout.addWidget(splitter)

    def _create_account_list(self) -> QWidget:
        """Create the account list widget."""
        widget = QWidget()
        widget.setObjectName("accountListPanel")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 20, 15, 10)
        layout.setSpacing(10)

        # Title
        self._account_list_title = QLabel(t("cloud_drive"))
        self._account_list_title.setObjectName("accountListTitle")
        layout.addWidget(self._account_list_title)

        # Add account button
        self._add_account_btn = QPushButton(t("add_account"))
        self._add_account_btn.setObjectName("addAccountBtn")
        self._add_account_btn.setCursor(Qt.PointingHandCursor)
        self._add_account_btn.clicked.connect(self._add_account)
        layout.addWidget(self._add_account_btn)

        # Account list
        self._account_list = QListWidget()
        self._account_list.setObjectName("accountList")
        self._account_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._account_list.setFocusPolicy(Qt.NoFocus)
        self._account_list.setCursor(Qt.PointingHandCursor)
        self._account_list.itemClicked.connect(self._on_account_selected)
        self._account_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._account_list.customContextMenuRequested.connect(
            self._show_account_context_menu
        )
        layout.addWidget(self._account_list)

        return widget

    def _create_file_content(self) -> QWidget:
        """Create the file content widget."""
        widget = QWidget()
        widget.setObjectName("fileContentPanel")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 10)
        layout.setSpacing(10)

        # Header
        header_layout = QHBoxLayout()

        self._account_title = QLabel(t("select_account"))
        self._account_title.setObjectName("accountTitle")
        header_layout.addWidget(self._account_title)

        header_layout.addStretch()

        # Navigation button
        self._back_btn = QPushButton("← " + t("back"))
        self._back_btn.setObjectName("backBtn")
        self._back_btn.setCursor(Qt.PointingHandCursor)
        self._back_btn.setEnabled(False)
        self._back_btn.clicked.connect(self._navigate_back)
        header_layout.addWidget(self._back_btn)

        # Path label
        self._path_label = QLabel("/")
        self._path_label.setObjectName("pathLabel")
        header_layout.addWidget(self._path_label)

        layout.addLayout(header_layout)

        # Stacked widget for different states
        self._stack = QStackedWidget()

        # Empty state page
        empty_page = QWidget()
        empty_layout = QVBoxLayout()
        empty_label = QLabel(t("add_cloud_account"))
        empty_label.setObjectName("emptyLabel")
        empty_label.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(empty_label)
        empty_page.setLayout(empty_layout)
        self._stack.addWidget(empty_page)

        # File browser page using CloudFileTable
        browser_page = QWidget()
        browser_layout = QVBoxLayout(browser_page)
        browser_layout.setContentsMargins(0, 0, 0, 0)

        # Use the new CloudFileTable component
        self._file_table = CloudFileTable()
        self._file_table.set_player(self._player)
        browser_layout.addWidget(self._file_table)

        self._stack.addWidget(browser_page)

        layout.addWidget(self._stack)

        # Status label
        self._status_label = QLabel()
        self._status_label.setObjectName("statusLabel")
        layout.addWidget(self._status_label)

        return widget

    def _setup_connections(self):
        """Setup signal connections for components."""
        # File table signals
        self._file_table.folder_double_clicked.connect(self._navigate_to_folder)
        self._file_table.audio_double_clicked.connect(self._play_audio_file)
        self._file_table.context_menu_requested.connect(self._show_file_context_menu)

        # File context menu signals
        self._file_context_menu.play_requested.connect(self._play_audio_file)
        self._file_context_menu.insert_to_queue_requested.connect(self._insert_to_queue)
        self._file_context_menu.add_to_queue_requested.connect(self._add_to_queue)
        self._file_context_menu.download_requested.connect(self._download_file)
        self._file_context_menu.edit_media_info_requested.connect(self._edit_media_info)
        self._file_context_menu.download_cover_requested.connect(self._download_cover)
        self._file_context_menu.open_file_location_requested.connect(self._open_file_location)
        self._file_context_menu.open_in_cloud_requested.connect(self._open_in_cloud_drive)

        # Account context menu signals
        self._account_context_menu.get_info_requested.connect(self._get_account_info)
        self._account_context_menu.change_download_dir_requested.connect(self._change_download_dir)
        self._account_context_menu.update_cookie_requested.connect(self._update_account_cookie)
        self._account_context_menu.delete_requested.connect(self._delete_account)

    def _setup_event_bus(self):
        """Setup EventBus connections."""
        self._event_bus = EventBus.instance()
        self._event_bus.download_started.connect(self._on_event_bus_download_started)
        self._event_bus.download_completed.connect(self._on_event_bus_download_completed)
        self._event_bus.track_changed.connect(self._on_track_changed)
        self._event_bus.playback_state_changed.connect(self._on_playback_state_changed)

    # === Account Management ===

    def _load_accounts(self):
        """Load cloud accounts from service."""
        accounts = self._cloud_account_service.get_accounts()
        self._populate_account_list(accounts)

        if accounts:
            self._stack.setCurrentIndex(1)

            # Restore last selected account
            if not self._current_account:
                saved_account_id = self._config_manager.get_cloud_account_id() if self._config_manager else None
                target_item = None

                if saved_account_id:
                    # Find the saved account in the list
                    for i in range(self._account_list.count()):
                        item = self._account_list.item(i)
                        account = item.data(Qt.UserRole)
                        if account and account.id == saved_account_id:
                            target_item = item
                            break

                # Fall back to first account if saved not found
                if not target_item:
                    target_item = self._account_list.item(0)

                if target_item:
                    self._account_list.setCurrentItem(target_item)
                    self._on_account_selected(target_item)
        else:
            self._stack.setCurrentIndex(0)

    def _populate_account_list(self, accounts: List[CloudAccount]):
        """Populate the account list widget."""
        self._account_list.clear()

        for account in accounts:
            provider_label = t("baidu") if account.provider == "baidu" else t("quark")
            display_name = f"[{provider_label}] {account.account_name}"
            item = QListWidgetItem(display_name)
            item.setData(Qt.UserRole, account)
            self._account_list.addItem(item)

            if self._current_account and account.id == self._current_account.id:
                self._account_list.setCurrentItem(item)

        if not accounts:
            self._stack.setCurrentIndex(0)
        else:
            self._stack.setCurrentIndex(1)

    def _on_account_selected(self, item: QListWidgetItem):
        """Handle account selection."""
        account = item.data(Qt.UserRole)
        if account:
            self._current_account = account

            # Save selected account ID
            if self._config_manager:
                self._config_manager.set_cloud_account_id(account.id)

            # Restore last saved folder path
            saved_path = account.last_folder_path if account.last_folder_path else "/"
            self._path_label.setText(saved_path)

            if account.provider == "baidu":
                self._current_parent_id = saved_path
                self._fid_path = saved_path.strip("/").split("/") if saved_path != "/" else []
            else:
                if account.last_fid_path and account.last_fid_path != "0":
                    self._fid_path = account.last_fid_path.strip("/").split("/")
                    if self._fid_path == [""]:
                        self._fid_path = []
                else:
                    self._fid_path = []

                if self._fid_path:
                    self._current_parent_id = self._fid_path[-1]
                else:
                    self._current_parent_id = "0"

            self._navigation_history.clear()

            can_go_back = len(self._fid_path) > 0 or (
                saved_path != "/" if account.provider == "baidu" else False
            )
            self._back_btn.setEnabled(can_go_back)

            self._last_playing_fid = account.last_playing_fid
            self._last_position = account.last_position

            self._update_file_view()

    def _add_account(self):
        """Add a new cloud account."""
        select_dialog = ProviderSelectDialog(self)
        if select_dialog.exec() != QDialog.Accepted:
            return

        provider = select_dialog.get_selected_provider()
        if not provider:
            return

        dialog = CloudLoginDialog(provider, self)
        dialog.login_success.connect(lambda info: self._on_login_success(info, provider))
        dialog.exec()

    def _on_login_success(self, account_info: dict, provider: str = "quark"):
        """Handle successful login."""
        account_id = self._cloud_account_service.create_account(
            provider=provider,
            account_name=account_info.get("account_email", f"{provider.capitalize()} Account"),
            account_email=account_info.get("account_email", ""),
            access_token=account_info.get("access_token", ""),
        )

        accounts = self._cloud_account_service.get_accounts()
        self._populate_account_list(accounts)

        if accounts:
            for i in range(self._account_list.count()):
                item = self._account_list.item(i)
                account = item.data(Qt.UserRole)
                if account.id == account_id:
                    self._account_list.setCurrentItem(item)
                    self._current_account = account
                    self._update_file_view()
                    break

    # === File Management ===

    def _update_file_view(self):
        """Update the file view based on current account."""
        if not self._current_account:
            self._account_title.setText(t("select_account"))
            self._stack.setCurrentIndex(0)
            return

        self._account_title.setText(self._current_account.account_name)
        self._stack.setCurrentIndex(1)
        self._load_files()

    def _load_files(self):
        """Load files for current directory."""
        if not self._current_account:
            return

        self._status_label.setText(t("loading_files"))

        service = BaiduDriveService if self._current_account.provider == "baidu" else QuarkDriveService
        dir_path = self._current_parent_id

        result = service.get_file_list(self._current_account.access_token, dir_path)

        if isinstance(result, tuple):
            files, updated_token = result
        else:
            files, updated_token = result, None

        if updated_token:
            self._cloud_account_service.update_token(self._current_account.id, updated_token)
            self._current_account.access_token = updated_token

        if files and len(files) > 0:
            self._current_parent_id = files[0].parent_id
            can_go_back = self._current_parent_id != "0"
            self._back_btn.setEnabled(can_go_back)
            self._cloud_file_service.cache_files(self._current_account.id, files)

        files = self._cloud_file_service.get_files(
            self._current_account.id, self._current_parent_id
        )

        self._current_audio_files = [f for f in files if f.file_type == "audio"]

        # Use the CloudFileTable component
        self._file_table.populate(files, self._current_playing_file_id)
        self._status_label.setText(f"{len(files)} {t('items')}")

    # === Navigation ===

    def _navigate_to_folder(self, file: CloudFile):
        """Navigate to a folder."""
        parent_id = self._current_parent_id
        current_path = self._path_label.text()

        self._navigation_history.append((parent_id, current_path))

        if current_path == "/":
            new_path = f"/{file.name}"
        else:
            new_path = f"{current_path}/{file.name}"

        if self._current_account and self._current_account.provider == "baidu":
            folder_path = file.metadata if file.metadata else new_path
            self._current_parent_id = folder_path
        else:
            self._fid_path.append(file.file_id)
            self._current_parent_id = file.file_id

        self._path_label.setText(new_path)
        self._back_btn.setEnabled(True)

        self._load_files()

    def _navigate_back(self):
        """Navigate to previous folder."""
        is_baidu = self._current_account and self._current_account.provider == "baidu"

        if self._navigation_history:
            parent_id, path = self._navigation_history.pop()

            if not is_baidu and self._fid_path:
                self._fid_path.pop()

            self._current_parent_id = parent_id
            self._path_label.setText(path)

            if is_baidu:
                self._back_btn.setEnabled(path != "/")
            else:
                self._back_btn.setEnabled(
                    len(self._navigation_history) > 0 or len(self._fid_path) > 0
                )

            self._load_files()

        elif is_baidu:
            current_path = self._path_label.text()
            if current_path != "/":
                path_parts = current_path.rstrip("/").split("/")
                if len(path_parts) > 1:
                    parent_path = "/".join(path_parts[:-1])
                    if not parent_path:
                        parent_path = "/"
                else:
                    parent_path = "/"

                self._current_parent_id = parent_path
                self._path_label.setText(parent_path)
                self._back_btn.setEnabled(parent_path != "/")
                self._load_files()
            else:
                self._back_btn.setEnabled(False)

        elif len(self._fid_path) > 0:
            self._fid_path.pop()

            if len(self._fid_path) > 0:
                parent_folder_id = self._fid_path[-1]
            else:
                parent_folder_id = "0"

            current_path = self._path_label.text()
            if current_path != "/":
                path_parts = current_path.rstrip("/").split("/")
                if len(path_parts) > 1:
                    parent_path = "/".join(path_parts[:-1])
                    if not parent_path:
                        parent_path = "/"
                else:
                    parent_path = "/"
            else:
                parent_path = "/"

            self._current_parent_id = parent_folder_id
            self._path_label.setText(parent_path)
            self._back_btn.setEnabled(len(self._fid_path) > 0)

            self._load_files()

    # === Playback ===

    def _play_audio_file(self, file: CloudFile, start_position: float = None):
        """Play an audio file from cloud."""
        if self._current_playing_file_id and self._current_playing_file_id != file.file_id:
            self._file_table.update_playing_status(self._current_playing_file_id, False)

        self._current_playing_file_id = file.file_id
        self._file_table.update_playing_status(file.file_id, True)

        if self._current_account:
            fid_path_str = "/" + "/".join(self._fid_path) if self._fid_path else "0"
            current_path = self._path_label.text()

            self._cloud_account_service.update_folder(
                self._current_account.id,
                self._current_parent_id,
                current_path,
                "0",
                fid_path_str
            )

            if start_position is not None:
                actual_start_position = start_position
            elif self._last_playing_fid == file.file_id:
                actual_start_position = self._last_position
            else:
                actual_start_position = 0.0

            if actual_start_position > 0:
                time_str = f"{int(actual_start_position // 60)}:{int(actual_start_position % 60):02d}"
                self._status_label.setText(
                    f"🎵 {t('resume_play')}: {file.name} ({t('resume_from', time=time_str)})"
                )

            self._cloud_account_service.update_playing_state(
                self._current_account.id,
                playing_fid=file.file_id,
                position=actual_start_position
            )

        try:
            file_index = next(
                i for i, f in enumerate(self._current_audio_files)
                if f.file_id == file.file_id
            )
        except StopIteration:
            file_index = 0

        # Check for existing local file
        local_file_path = None
        if self._current_account:
            db_file = self._cloud_file_service.get_file_by_file_id(file.file_id)
            if db_file and db_file.local_path:
                db_path = Path(db_file.local_path)
                if db_path.exists():
                    local_file_path = db_path

        if not local_file_path:
            if self._config_manager:
                download_dir = Path(self._config_manager.get_cloud_download_dir())
            else:
                download_dir = Path("data/cloud_downloads")

            if not download_dir.is_absolute():
                download_dir = Path.cwd() / download_dir

            from utils.helpers import sanitize_filename
            safe_filename = sanitize_filename(file.name)
            local_file_path = download_dir / safe_filename

        file_exists_and_valid = False
        if local_file_path.exists() and file.size:
            actual_size = local_file_path.stat().st_size
            size_diff = abs(actual_size - file.size)
            tolerance = file.size * 0.01

            if size_diff <= tolerance:
                file_exists_and_valid = True
                if actual_start_position == 0:
                    self._status_label.setText(f"{t('using_cached_file')}: {file.name}")

                self._on_file_exists(
                    str(local_file_path), file_index, self._current_audio_files,
                    file.name, actual_start_position
                )
                return

        if not file_exists_and_valid:
            size_info = ""
            if file.size:
                size_mb = file.size / (1024 * 1024)
                size_info = f" ({size_mb:.1f} MB)"
            self._status_label.setText(f"{t('downloading')} {file.name}{size_info}...")

        db_local_path = None
        if self._current_account:
            db_file = self._cloud_file_service.get_file_by_file_id(file.file_id)
            if db_file and db_file.local_path:
                db_local_path = db_file.local_path

        download_thread = CloudFileDownloadThread(
            self._current_account.access_token,
            file,
            file_index,
            self._current_audio_files,
            self._config_manager,
            self,
            db_local_path,
            self._current_account.provider,
        )
        download_thread.finished.connect(
            lambda path: self._on_file_downloaded(
                path, file_index, self._current_audio_files, file.name, actual_start_position
            )
        )
        download_thread.file_exists.connect(
            lambda path: self._on_file_exists(
                path, file_index, self._current_audio_files, file.name, actual_start_position
            )
        )
        download_thread.token_updated.connect(self._on_token_updated)
        download_thread.start()

    def _on_file_exists(self, temp_path: str, file_index: int, audio_files: list,
                        file_name: str, start_position: float = 0.0):
        """Handle when file already exists locally."""
        import os

        if temp_path and os.path.exists(temp_path):
            if start_position == 0:
                self._status_label.setText(f"{t('using_cached_file')} - {file_name}")

            if file_index < len(audio_files):
                cloud_file = audio_files[file_index]
                if self._current_account:
                    self._cloud_file_service.update_local_path(
                        cloud_file.file_id,
                        self._current_account.id,
                        temp_path
                    )
                    self._cloud_account_service.update_playing_state(
                        self._current_account.id,
                        playing_fid=cloud_file.file_id,
                        local_path=temp_path
                    )

            self.play_cloud_files.emit(temp_path, file_index, audio_files, start_position)

            if file_index < len(self._current_audio_files):
                for i, f in enumerate(self._current_audio_files):
                    if f.file_id == self._current_audio_files[file_index].file_id:
                        from domain.cloud import CloudFile as CloudFileModel
                        updated_file = CloudFileModel(
                            id=f.id,
                            account_id=f.account_id,
                            file_id=f.file_id,
                            parent_id=f.parent_id,
                            name=f.name,
                            file_type=f.file_type,
                            size=f.size,
                            mime_type=f.mime_type,
                            duration=f.duration,
                            metadata=f.metadata,
                            local_path=temp_path,
                            created_at=f.created_at,
                            updated_at=f.updated_at
                        )
                        self._current_audio_files[i] = updated_file
                        break
        else:
            self._status_label.setText(t("download_failed"))

    def _on_file_downloaded(self, temp_path: str, file_index: int, audio_files: list,
                            file_name: str = None, start_position: float = 0.0):
        """Handle completed file download."""
        if temp_path:
            import os

            if os.path.exists(temp_path):
                if not file_name and file_index < len(audio_files):
                    file_name = audio_files[file_index].name
                elif not file_name:
                    file_name = "Unknown"

                file_size = os.path.getsize(temp_path)
                size_mb = file_size / (1024 * 1024)

                if start_position == 0:
                    self._status_label.setText(
                        f"✅ {t('download_complete')}: {file_name} ({size_mb:.1f} MB)"
                    )
                    QTimer.singleShot(5000, lambda: self._status_label.setText(""))

                if file_index < len(audio_files):
                    cloud_file = audio_files[file_index]
                    if self._current_account:
                        self._cloud_file_service.update_local_path(
                            cloud_file.file_id,
                            self._current_account.id,
                            temp_path
                        )
                        self._cloud_account_service.update_playing_state(
                            self._current_account.id,
                            playing_fid=cloud_file.file_id,
                            local_path=temp_path
                        )

                self.play_cloud_files.emit(temp_path, file_index, audio_files, start_position)

                if file_index < len(self._current_audio_files):
                    for i, f in enumerate(self._current_audio_files):
                        if f.file_id == self._current_audio_files[file_index].file_id:
                            from domain.cloud import CloudFile as CloudFileModel
                            updated_file = CloudFileModel(
                                id=f.id,
                                account_id=f.account_id,
                                file_id=f.file_id,
                                parent_id=f.parent_id,
                                name=f.name,
                                file_type=f.file_type,
                                size=f.size,
                                mime_type=f.mime_type,
                                duration=f.duration,
                                metadata=f.metadata,
                                local_path=temp_path,
                                created_at=f.created_at,
                                updated_at=f.updated_at
                            )
                            self._current_audio_files[i] = updated_file

                            self._file_table.update_file_local_path(f.file_id, temp_path)
                            break
            else:
                self._status_label.setText(t("download_failed"))
        else:
            self._status_label.setText(t("download_failed"))

    def _on_token_updated(self, updated_token: str):
        """Handle updated access token."""
        if self._current_account and updated_token:
            self._cloud_account_service.update_token(self._current_account.id, updated_token)
            self._current_account.access_token = updated_token

    # === Queue Operations ===

    def _insert_to_queue(self, file: CloudFile):
        """Insert file to queue after current track."""
        # This will be handled by the parent window
        self.track_double_clicked.emit(file.file_id)

    def _add_to_queue(self, file: CloudFile):
        """Add file to queue."""
        # This will be handled by the parent window
        self.track_double_clicked.emit(file.file_id)

    # === Context Menus ===

    def _show_file_context_menu(self, pos, file: CloudFile):
        """Show context menu for file."""
        self._file_context_menu.show_menu(file, self._current_audio_files,
                                          self._current_account.id if self._current_account else None)

    def _show_account_context_menu(self, pos):
        """Show context menu for account."""
        item = self._account_list.itemAt(pos)
        if not item:
            return

        account = item.data(Qt.UserRole)
        if account:
            self._account_context_menu.show_menu(account)

    # === File Operations ===

    def _download_file(self, file: CloudFile):
        """Download a cloud file without playing it."""
        if not self._current_account:
            return

        from utils.helpers import sanitize_filename

        if self._config_manager:
            download_dir = Path(self._config_manager.get_cloud_download_dir())
        else:
            download_dir = Path("data/cloud_downloads")

        if not download_dir.is_absolute():
            download_dir = Path.cwd() / download_dir

        safe_filename = sanitize_filename(file.name)
        local_file_path = download_dir / safe_filename

        if local_file_path.exists() and file.size:
            actual_size = local_file_path.stat().st_size
            size_diff = abs(actual_size - file.size)
            tolerance = file.size * 0.01

            if size_diff <= tolerance:
                if self._current_account:
                    self._cloud_file_service.update_local_path(
                        file.file_id,
                        self._current_account.id,
                        str(local_file_path)
                    )
                file.local_path = str(local_file_path)
                for audio_file in self._current_audio_files:
                    if audio_file.file_id == file.file_id:
                        audio_file.local_path = str(local_file_path)
                        break
                self._status_label.setText(f"✓ {file.name} {t('file_already_exists')}")
                self._file_table.update_file_local_path(file.file_id, str(local_file_path))
                return

        size_info = ""
        if file.size:
            size_mb = file.size / (1024 * 1024)
            size_info = f" ({size_mb:.1f} MB)"
        self._status_label.setText(f"{t('downloading')} {file.name}{size_info}...")

        file_index = 0
        try:
            file_index = next(
                i for i, f in enumerate(self._current_audio_files)
                if f.file_id == file.file_id
            )
        except StopIteration:
            pass

        download_thread = CloudFileDownloadThread(
            self._current_account.access_token,
            file,
            file_index,
            self._current_audio_files,
            self._config_manager,
            self,
            provider=self._current_account.provider,
        )
        download_thread.finished.connect(
            lambda path: self._on_download_only_completed(path, file)
        )
        download_thread.file_exists.connect(
            lambda path: self._on_download_only_completed(path, file)
        )
        download_thread.token_updated.connect(self._on_token_updated)
        download_thread.start()

    def _on_download_only_completed(self, local_path: str, file: CloudFile):
        """Handle completed download (without playback)."""
        if local_path:
            import os
            if os.path.exists(local_path):
                file_size = os.path.getsize(local_path)
                size_mb = file_size / (1024 * 1024)
                self._status_label.setText(
                    f"✅ {t('download_complete')}: {file.name} ({size_mb:.1f} MB)"
                )
                QTimer.singleShot(5000, lambda: self._status_label.setText(""))

                if self._current_account:
                    self._cloud_file_service.update_local_path(
                        file.file_id,
                        self._current_account.id,
                        local_path
                    )

                for audio_file in self._current_audio_files:
                    if audio_file.file_id == file.file_id:
                        audio_file.local_path = local_path
                        break

                self._file_table.update_file_local_path(file.file_id, local_path)
        else:
            self._status_label.setText(f"{t('download_failed')}: {file.name}")

    def _edit_media_info(self, file: CloudFile):
        """Edit media info for a cloud file."""
        if show_media_info_dialog(file, self._library_service, self):
            self._status_label.setText(f"✓ {t('metadata_saved')}")

    def _download_cover(self, file: CloudFile):
        """Download cover art for a cloud file."""
        if not file.local_path:
            logger.warning(f"Cannot download cover: file not downloaded - {file.name}")
            return

        from services.metadata import MetadataService
        from ui.dialogs import CoverDownloadDialog
        from domain.track import Track

        # Extract metadata from the downloaded file
        metadata = MetadataService.extract_metadata(file.local_path)

        # Create a temporary Track object for the dialog
        track = Track(
            id=0,
            title=metadata.get("title") or file.name,
            artist=metadata.get("artist") or "",
            album=metadata.get("album") or "",
            duration=file.duration or metadata.get("duration") or 0.0,
            path=file.local_path
        )

        def save_cover_callback(track, cover_path, cover_data):
            """Embed cover into the cloud file and save to cache."""
            try:
                import mutagen
                from mutagen.id3 import ID3, APIC
                from mutagen.mp3 import MP3
                from mutagen.flac import FLAC
                from mutagen.mp4 import MP4
                from mutagen.oggvorbis import OggVorbis
                import base64

                path = Path(file.local_path)
                if not path.exists():
                    logger.error(f"File not found: {file.local_path}")
                    return False

                suffix = path.suffix.lower()
                audio = mutagen.File(file_path=file.local_path)

                if suffix == ".mp3" and isinstance(audio, MP3):
                    if audio.tags is None:
                        audio.add_tags()
                    audio.tags.delall("APIC")
                    audio.tags.add(APIC(
                        encoding=3,
                        mime="image/jpeg",
                        type=3,
                        desc="Cover",
                        data=cover_data
                    ))
                    audio.save()
                elif suffix == ".flac" and isinstance(audio, FLAC):
                    audio["pictures"] = []
                    from mutagen.flac import Picture
                    pic = Picture()
                    pic.type = 3
                    pic.mime = "image/jpeg"
                    pic.desc = "Cover"
                    pic.data = cover_data
                    audio.add_picture(pic)
                    audio.save()
                elif suffix in {".m4a", ".mp4"} and isinstance(audio, MP4):
                    audio["covr"] = [cover_data]
                    audio.save()
                elif suffix in {".ogg", ".oga"} and isinstance(audio, OggVorbis):
                    import base64
                    audio["metadata_block_picture"] = [
                        base64.b64encode(
                            mutagen.flac.Picture(
                                type=3, mime="image/jpeg",
                                desc="Cover", data=cover_data
                            ).write()
                        ).decode("ascii")
                    ]
                    audio.save()
                else:
                    logger.warning(f"Unsupported format for cover embedding: {suffix}")
                    # Cover is still saved to cache by the dialog, so just accept
                    return True

                logger.info(f"Cover embedded into {file.name}")
                self._status_label.setText(f"✓ {t('metadata_saved')}")
                return True
            except Exception as e:
                logger.error(f"Failed to embed cover into {file.name}: {e}")
                return False

        dialog = CoverDownloadDialog(
            [track],
            self._cover_service,
            self,
            save_callback=save_cover_callback
        )
        dialog.exec()

    def _open_file_location(self, file: CloudFile):
        """Open file location in file manager."""
        if file.local_path:
            import subprocess
            import sys

            path = Path(file.local_path)
            if path.exists():
                if sys.platform == "win32":
                    subprocess.run(["explorer", "/select,", str(path)])
                elif sys.platform == "darwin":
                    subprocess.run(["open", "-R", str(path)])
                else:
                    subprocess.run(["xdg-open", str(path.parent)])

    def _open_in_cloud_drive(self, file: CloudFile):
        """Open file in cloud drive web interface."""
        import webbrowser

        if self._current_account:
            if self._current_account.provider == "baidu":
                url = f"https://pan.baidu.com/disk/main#/index?path={file.metadata}"
            else:
                url = f"https://pan.quark.cn/list#/list/{file.parent_id}"
            webbrowser.open(url)

    # === Account Operations ===

    def _get_account_info(self, account: CloudAccount):
        """Get and display account information."""
        self._status_label.setText(f"{t('loading')} {t('account_info')}...")

        service = BaiduDriveService if account.provider == "baidu" else QuarkDriveService

        result = service.get_account_info(account.access_token, account.account_email)

        if isinstance(result, tuple):
            account_info, updated_token = result
        else:
            account_info, updated_token = result, None

        if updated_token:
            self._cloud_account_service.update_token(account.id, updated_token)
            account.access_token = updated_token
            if self._current_account and self._current_account.id == account.id:
                self._current_account.access_token = updated_token

        if account_info:
            self._show_account_info_dialog(account, account_info)
            self._status_label.setText("")
        else:
            self._status_label.setText(t("failed_to_get_account_info"))
            MessageDialog.warning(self, t("error"), t("failed_to_get_account_info"))

    def _show_account_info_dialog(self, account: CloudAccount, account_info: dict):
        """Show account information dialog."""
        member_type = account_info.get("member_type", "unknown")
        is_vip = account_info.get("is_vip", False)
        if member_type in ("vip", "VIP"):
            member_type_display = t("member_vip")
        elif member_type in ("svip", "SUPER_VIP"):
            member_type_display = t("member_svip")
        elif member_type in ("premium",):
            member_type_display = t("member_premium")
        elif is_vip:
            member_type_display = t("member_vip")
        else:
            member_type_display = t("member_normal")

        created_at_str = self._format_timestamp(account_info.get("created_at"))
        exp_at_str = self._format_timestamp(account_info.get("exp_at"))

        total_capacity_str = self._format_capacity(account_info.get("total_capacity", 0))
        used_capacity_str = self._format_capacity(account_info.get("use_capacity", 0))

        total_cap = account_info.get("total_capacity", 0)
        used_cap = account_info.get("use_capacity", 0)
        if total_cap > 0:
            usage_percent = (used_cap / total_cap) * 100
            usage_str = f"{usage_percent:.1f}%"
        else:
            usage_str = "N/A"

        info_text = f"""
{t("account_name")}: {account_info.get("nickname", account.account_name)}
{t("member_type")}: {member_type_display}
{t("account_created")}: {created_at_str}
{t("vip_expires")}: {exp_at_str}
{t("storage_used")}: {used_capacity_str} / {total_capacity_str} ({usage_str})
"""

        MessageDialog.information(self, t("account_info"), info_text.strip())

    def _format_timestamp(self, timestamp_ms: int) -> str:
        """Format millisecond timestamp to readable date string."""
        if not timestamp_ms:
            return "N/A"

        try:
            from datetime import datetime
            timestamp_sec = timestamp_ms / 1000
            dt = datetime.fromtimestamp(timestamp_sec)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            logger.error(f"Error formatting timestamp: {e}", exc_info=True)
            return "N/A"

    def _format_capacity(self, bytes_size: int) -> str:
        """Format bytes to readable size string."""
        if not bytes_size or bytes_size == 0:
            return "0 GB"

        try:
            tb = bytes_size / (1024 ** 4)
            gb = bytes_size / (1024 ** 3)
            mb = bytes_size / (1024 ** 2)

            if tb >= 1:
                return f"{tb:.2f} TB"
            elif gb >= 1:
                return f"{gb:.2f} GB"
            else:
                return f"{mb:.2f} MB"
        except Exception as e:
            logger.error(f"Error formatting capacity: {e}", exc_info=True)
            return "N/A"

    def _change_download_dir(self):
        """Change the download directory."""
        from PySide6.QtWidgets import QFileDialog

        current_dir = self._config_manager.get_cloud_download_dir() if self._config_manager else "data/cloud_downloads"

        new_dir = QFileDialog.getExistingDirectory(
            self, t("select_download_dir"), current_dir
        )

        if new_dir and self._config_manager:
            self._config_manager.set_cloud_download_dir(new_dir)
            self._status_label.setText(f"✓ {t('download_dir_changed')}")

    def _update_account_cookie(self, account: CloudAccount):
        """Update cookie for an account."""
        dialog = CloudLoginDialog(provider=account.provider, parent=self)
        dialog.login_success.connect(
            lambda result: self._on_cookie_updated(account, result)
        )
        dialog.exec()

    def _on_cookie_updated(self, account: CloudAccount, result: dict):
        """Handle cookie update from login dialog."""
        new_token = result.get("access_token", "")
        if new_token:
            self._cloud_account_service.update_token(account.id, new_token)
            self._load_accounts()
            self._status_label.setText(f"✓ {t('cookie_updated')}")

    def _delete_account(self, account: CloudAccount):
        """Delete a cloud account."""
        reply = MessageDialog.question(
            self,
            t("delete_account"),
            t("confirm_delete_account").format(name=account.account_name),
            Yes | No,
            No
        )

        if reply == Yes:
            self._cloud_account_service.delete_account(account.id)
            self._load_accounts()
            self._status_label.setText(f"✓ {t('account_deleted')}")

    # === Event Bus Handlers ===

    def _on_event_bus_download_started(self, file_id: str):
        """Handle download start from EventBus."""
        file_name = None
        file_size = None
        for f in self._current_audio_files:
            if f.file_id == file_id:
                file_name = f.name
                file_size = f.size
                break

        if file_name:
            size_info = ""
            if file_size:
                size_mb = file_size / (1024 * 1024)
                size_info = f" ({size_mb:.1f} MB)"
            self._status_label.setText(f"{t('downloading')} {file_name}{size_info}...")

    def _on_event_bus_download_completed(self, file_id: str, local_path: str):
        """Handle download completion from EventBus."""
        file_name = ""
        for f in self._current_audio_files:
            if f.file_id == file_id:
                f.local_path = local_path
                file_name = f.name
                self._file_table.update_file_local_path(file_id, local_path)
                break

        import os
        if local_path and os.path.exists(local_path):
            file_size = os.path.getsize(local_path)
            size_mb = file_size / (1024 * 1024)
            self._status_label.setText(f"✅ {t('download_complete')}: {file_name} ({size_mb:.1f} MB)")
            QTimer.singleShot(5000, lambda: self._status_label.setText(""))

    def _on_track_changed(self, track_item):
        """Handle track change event."""
        if hasattr(track_item, 'cloud_file_id') and track_item.cloud_file_id:
            self._current_playing_file_id = track_item.cloud_file_id
            self._file_table.update_playing_status(track_item.cloud_file_id, True)

    def _on_playback_state_changed(self, state: str):
        """Handle playback state change event."""
        pass

    # === Public API ===

    def refresh_ui(self):
        """Refresh the UI with latest data."""
        self._load_accounts()
        self._data_loaded = True

        self._account_list_title.setText(t("cloud_drive"))
        self._add_account_btn.setText(t("add_account"))
        self._back_btn.setText("← " + t("back"))
        self._account_title.setText(
            self._current_account.account_name if self._current_account else t("select_account")
        )

        # Refresh file table headers
        if hasattr(self, '_file_table'):
            self._file_table.refresh_ui()

    def refresh_theme(self):
        """Apply themed styles using ThemeManager tokens."""
        from system.theme import ThemeManager
        self.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TEMPLATE))

    def showEvent(self, event):
        """Handle show event."""
        super().showEvent(event)
        if not self._data_loaded:
            self._load_accounts()

    def restore_playback_state(
        self,
        account_id: int,
        file_path: str,
        file_fid: str,
        auto_play: bool = False,
        position: float = 0.0
    ):
        """Restore playback state for a specific file."""
        # Find and select the account
        for i in range(self._account_list.count()):
            item = self._account_list.item(i)
            account = item.data(Qt.UserRole)
            if account.id == account_id:
                self._account_list.setCurrentItem(item)
                self._current_account = account
                break

        if not self._current_account:
            return

        # Navigate to the file's folder and play it
        self._fast_restore_playback(account_id, file_fid, file_path, position)

    def _fast_restore_playback(
        self,
        account_id: int,
        file_fid: str,
        local_path: str,
        start_position: float
    ):
        """Fast restore playback using local path if available."""
        if local_path and Path(local_path).exists():
            # Find the file in current audio files
            file_to_play = None
            file_index = 0
            for i, audio_file in enumerate(self._current_audio_files):
                if audio_file.file_id == file_fid:
                    file_to_play = audio_file
                    file_index = i
                    break

            if file_to_play:
                self._play_audio_file(file_to_play, start_position)
            else:
                # Emit signal to play the local file directly
                self.play_cloud_files.emit(local_path, 0, [], start_position)
        else:
            # Need to select and play from file list
            self._select_and_play_file_by_fid(file_fid, start_position > 0)

    def _select_and_play_file_by_fid(self, file_fid: str, auto_play: bool = False):
        """Select and optionally play a file by its FID."""
        self._file_table.select_and_scroll_to_file(file_fid)

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
