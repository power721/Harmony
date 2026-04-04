"""
Cloud drive view for browsing and playing cloud files.

This is a refactored version that uses modular components:
- CloudFileTable: File listing with playing indicator
- CloudFileDownloadThread: Background download
- CloudMediaInfoDialog: Media info editing
- CloudFileContextMenu: Right-click menu handling
"""

import json
import logging
import shutil
from html import escape
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

from PySide6.QtCore import Qt, Signal, QTimer
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
    QLineEdit,
)

from domain.cloud import CloudAccount, CloudFile
from services.cloud.cache_paths import build_cloud_cache_path
from services.cloud.baidu_service import BaiduDriveService
from services.cloud.quark_service import QuarkDriveService
from services.cloud.share_search_service import ShareSearchService, ShareSong
from system.event_bus import EventBus
from system.i18n import t
from ui.dialogs.cloud_login_dialog import CloudLoginDialog
from ui.dialogs.message_dialog import MessageDialog, Yes, No
from ui.dialogs.provider_select_dialog import ProviderSelectDialog
from .context_menu import CloudFileContextMenu, CloudAccountContextMenu
from .download_thread import CloudFileDownloadThread
from .file_table import CloudFileTable

if TYPE_CHECKING:
    from services.cloud import CloudAccountService, CloudFileService
    from services.library import LibraryService
    from services.playback import PlaybackService
    from services.metadata import CoverService
    from system.config import ConfigManager

logger = logging.getLogger(__name__)


class BreadcrumbLabel(QLabel):
    """Clickable breadcrumb label that stores plain path text."""

    breadcrumb_clicked = Signal(str, int)

    def __init__(self, path: str = "/", parent=None):
        super().__init__(parent)
        self._path_text = "/"
        self._text_color = "#ffffff"
        self.setTextFormat(Qt.RichText)
        self.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.setOpenExternalLinks(False)
        self.linkActivated.connect(self._on_link_activated)
        self.setText(path)

    def setText(self, text: str):
        """Set plain path text and render breadcrumb links."""
        normalized = self._normalize_path(text)
        self._path_text = normalized
        super().setText(self._to_breadcrumb_html(normalized))

    def text(self) -> str:
        """Return the plain path text instead of rich text."""
        return self._path_text

    def set_breadcrumb_color(self, color: str):
        """Set explicit breadcrumb text color for rich text links."""
        if color:
            self._text_color = color
            super().setText(self._to_breadcrumb_html(self._path_text))

    @staticmethod
    def _normalize_path(path: str) -> str:
        path = (path or "").strip()
        if not path:
            return "/"
        if not path.startswith("/"):
            path = f"/{path}"
        if len(path) > 1:
            path = path.rstrip("/")
        return path or "/"

    def _to_breadcrumb_html(self, path: str) -> str:
        parts = [p for p in path.strip("/").split("/") if p]
        links = [f'<a href="0" style="text-decoration:none; color:{self._text_color};">/</a>']
        for idx, part in enumerate(parts, start=1):
            links.append(
                f'<a href="{idx}" style="text-decoration:none; color:{self._text_color};">{escape(part)}</a>'
            )
        return f" <span style=\"color:{self._text_color};\">&gt;</span> ".join(links)

    def _on_link_activated(self, link: str):
        """Emit clicked breadcrumb level and target path."""
        try:
            level = max(0, int(link))
        except ValueError:
            return
        parts = [p for p in self._path_text.strip("/").split("/") if p]
        level = min(level, len(parts))
        target_path = "/" if level == 0 else "/" + "/".join(parts[:level])
        self.breadcrumb_clicked.emit(target_path, level)


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
        QLabel#breadcrumbPathLabel {
            color: %text%;
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
        QPushButton#batchDownloadBtn {
            background-color: %highlight%;
            color: %background%;
            border: none;
            padding: 6px 14px;
            border-radius: 6px;
            font-weight: bold;
            font-size: 12px;
        }
        QPushButton#batchDownloadBtn:hover {
            background-color: %highlight_hover%;
        }
        QPushButton#batchDownloadBtn:disabled {
            background-color: %border%;
            color: %text_secondary%;
        }
        QPushButton#cancelDownloadsBtn {
            background-color: transparent;
            color: %text_secondary%;
            border: 1px solid %border%;
            padding: 6px 14px;
            border-radius: 6px;
            font-size: 12px;
        }
        QPushButton#cancelDownloadsBtn:hover {
            background-color: %background_hover%;
            color: %highlight%;
            border-color: %highlight%;
        }
    """

    _SEARCH_INPUT_STYLE_TEMPLATE = """
        QLineEdit {
            background-color: %background_hover%;
            color: %text%;
            border: 2px solid %border%;
            border-radius: 20px;
            padding: 10px 15px;
            font-size: 14px;
        }
        QLineEdit:focus {
            border: 2px solid %highlight%;
            background-color: %background_hover%;
        }
        QLineEdit::placeholder {
            color: %text_secondary%;
        }
        QLineEdit::clear-button {
            subcontrol-origin: padding;
            subcontrol-position: right;
            width: 18px;
            height: 18px;
            margin-right: 8px;
            border-radius: 9px;
            background-color: %border%;
        }
        QLineEdit::clear-button:hover {
            background-color: %background_hover%;
            border: 1px solid %border%;
        }
        QLineEdit::clear-button:pressed {
            background-color: %background_alt%;
        }
    """

    _SEARCH_BUTTON_STYLE_TEMPLATE = """
        QPushButton {
            background: %background_alt%;
            color: %text%;
            border: none;
            padding: 8px 15px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background: %border%;
        }
        QPushButton:pressed {
            background: %text_secondary%;
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
        self._share_mode = False
        self._share_pwd_id = ""
        self._share_stoken = ""
        self._share_root_title = ""
        self._share_history: List[tuple[str, str]] = []
        self._share_search_result = None
        self._share_search_keyword = ""
        self._share_search_page = 1
        self._share_search_total_pages = 0
        self._share_search_limit = 20
        self._pre_share_browse_state: Optional[dict] = None

        # Batch download state
        self._download_queue: List[CloudFile] = []
        self._is_downloading = False
        self._current_download_thread = None
        self._batch_total = 0
        self._batch_completed = 0

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

        self._account_title = QLabel(t("select_account"))
        self._account_title.setObjectName("accountTitle")
        self._account_title.setVisible(False)

        # Share search toolbar
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(0, 0, 0, 0)

        self._share_search_input = QLineEdit()
        self._share_search_input.setPlaceholderText(t("cloud_share_search_placeholder"))
        self._share_search_input.setClearButtonEnabled(True)
        self._share_search_input.returnPressed.connect(self._search_shares)
        self._share_search_input.textChanged.connect(self._on_share_search_text_changed)
        search_layout.addWidget(self._share_search_input)

        self._share_search_btn = QPushButton(t("search"))
        self._share_search_btn.setCursor(Qt.PointingHandCursor)
        self._share_search_btn.setFixedHeight(50)
        self._share_search_btn.clicked.connect(self._search_shares)
        search_layout.addWidget(self._share_search_btn)

        self._share_prev_btn = QPushButton("◀")
        self._share_prev_btn.setCursor(Qt.PointingHandCursor)
        self._share_prev_btn.setEnabled(False)
        self._share_prev_btn.setVisible(False)
        self._share_prev_btn.clicked.connect(self._go_share_prev_page)
        search_layout.addWidget(self._share_prev_btn)

        self._share_page_label = QLabel("1/1")
        self._share_page_label.setObjectName("pathLabel")
        self._share_page_label.setVisible(False)
        search_layout.addWidget(self._share_page_label)

        self._share_next_btn = QPushButton("▶")
        self._share_next_btn.setCursor(Qt.PointingHandCursor)
        self._share_next_btn.setEnabled(False)
        self._share_next_btn.setVisible(False)
        self._share_next_btn.clicked.connect(self._go_share_next_page)
        search_layout.addWidget(self._share_next_btn)

        layout.addLayout(search_layout)

        self._share_results_list = QListWidget()
        self._share_results_list.setVisible(False)
        self._share_results_list.itemSelectionChanged.connect(self._on_share_result_selection_changed)
        self._share_results_list.itemClicked.connect(self._on_share_result_clicked)
        layout.addWidget(self._share_results_list)

        # Toolbar for batch download
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)

        self._batch_download_btn = QPushButton(t("batch_download"))
        self._batch_download_btn.setObjectName("batchDownloadBtn")
        self._batch_download_btn.setCursor(Qt.PointingHandCursor)
        self._batch_download_btn.clicked.connect(self._download_selected_files)
        self._batch_download_btn.setVisible(False)
        toolbar_layout.addWidget(self._batch_download_btn)

        self._cancel_downloads_btn = QPushButton(t("cancel_downloads"))
        self._cancel_downloads_btn.setObjectName("cancelDownloadsBtn")
        self._cancel_downloads_btn.setCursor(Qt.PointingHandCursor)
        self._cancel_downloads_btn.clicked.connect(self._cancel_downloads)
        self._cancel_downloads_btn.setVisible(False)
        toolbar_layout.addWidget(self._cancel_downloads_btn)

        self._share_save_selected_btn = QPushButton(t("save_selected_to_cloud"))
        self._share_save_selected_btn.setObjectName("batchDownloadBtn")
        self._share_save_selected_btn.setCursor(Qt.PointingHandCursor)
        self._share_save_selected_btn.clicked.connect(self._save_selected_share_items)
        self._share_save_selected_btn.setVisible(False)
        self._share_save_selected_btn.setEnabled(False)
        toolbar_layout.addWidget(self._share_save_selected_btn)

        toolbar_layout.addStretch()

        # Navigation button
        self._back_btn = QPushButton("← " + t("back"))
        self._back_btn.setObjectName("backBtn")
        self._back_btn.setCursor(Qt.PointingHandCursor)
        self._back_btn.setEnabled(False)
        self._back_btn.clicked.connect(self._navigate_back)
        toolbar_layout.addWidget(self._back_btn)

        # Path label
        self._path_label = BreadcrumbLabel("/")
        self._path_label.setObjectName("breadcrumbPathLabel")
        self._path_label.breadcrumb_clicked.connect(self._on_breadcrumb_clicked)
        toolbar_layout.addWidget(self._path_label)

        layout.addLayout(toolbar_layout)

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
        self._file_table.selection_changed.connect(self._update_share_save_button_state)

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
            self._clear_share_search_results(reset_view=False)
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

    # === Share Search ===

    def _search_shares(self):
        """Search cloud share entries from remote API."""
        keyword = self._share_search_input.text().strip()
        if not keyword:
            self._clear_share_search_results()
            return
        self._share_search_keyword = keyword
        self._share_search_page = 1
        self._search_shares_page(self._share_search_page)

    def _on_share_search_text_changed(self, text: str):
        """Clear results immediately when search text is cleared."""
        if text.strip():
            return
        self._clear_share_search_results()

    def _clear_share_search_results(self, reset_view: bool = True):
        """Clear share search results and hide pagination controls."""
        if self._share_mode:
            self._clear_share_mode(reset_view=reset_view)
        if reset_view:
            self._restore_pre_share_browse_state()
        else:
            self._pre_share_browse_state = None
        self._share_search_keyword = ""
        self._share_search_result = None
        self._share_search_input.blockSignals(True)
        self._share_search_input.clear()
        self._share_search_input.blockSignals(False)
        self._share_results_list.clear()
        self._share_results_list.setVisible(False)
        self._stack.setVisible(True)
        self._update_toolbar_for_search_results(False)
        self._share_page_label.setText("1/1")
        self._share_prev_btn.setEnabled(False)
        self._share_next_btn.setEnabled(False)
        self._share_prev_btn.setVisible(False)
        self._share_next_btn.setVisible(False)
        self._share_page_label.setVisible(False)
        if self._current_account:
            self._last_playing_fid = self._current_account.last_playing_fid
            self._last_position = self._current_account.last_position
            self._update_file_view()

    def _search_shares_page(self, page: int):
        """Search cloud share entries by page."""
        keyword = self._share_search_keyword or self._share_search_input.text().strip()
        if not keyword:
            return
        self._status_label.setText(f"{t('searching')}...")
        result = ShareSearchService.search(
            keyword, page=page, limit=self._share_search_limit
        )
        self._share_search_result = result
        self._share_search_page = max(1, int(result.page or page))
        self._share_search_total_pages = max(1, int(result.total_pages or 1))
        self._share_prev_btn.setVisible(True)
        self._share_next_btn.setVisible(True)
        self._share_page_label.setVisible(True)
        self._share_page_label.setText(f"{self._share_search_page}/{self._share_search_total_pages}")
        self._share_prev_btn.setEnabled(self._share_search_page > 1)
        self._share_next_btn.setEnabled(
            self._share_search_page < self._share_search_total_pages
        )

        self._share_results_list.clear()
        for song in result.songs:
            prefix = "✓" if song.has_quark_link else "✗"
            title = f"{prefix} {song.artist} - {song.name or song.title}"
            item = QListWidgetItem(title)
            item.setData(Qt.UserRole, song)
            self._share_results_list.addItem(item)

        has_results = len(result.songs) > 0
        self._share_results_list.setVisible(has_results)
        self._stack.setVisible(False)
        self._update_toolbar_for_search_results(has_results)
        self._adjust_share_results_height()
        self._status_label.setText("")
        # self._status_label.setText(
        #     t("cloud_share_search_result_count").format(count=len(result.songs))
        # )

    def _go_share_prev_page(self):
        """Go to previous share-search page."""
        if self._share_search_page > 1:
            self._search_shares_page(self._share_search_page - 1)

    def _go_share_next_page(self):
        """Go to next share-search page."""
        if self._share_search_page < self._share_search_total_pages:
            self._search_shares_page(self._share_search_page + 1)

    def _on_share_result_selection_changed(self):
        """Show hint when selected result has no Quark link."""
        selected = self._share_results_list.selectedItems()
        if not selected:
            self._update_share_save_button_state()
            return

        song = selected[0].data(Qt.UserRole)
        has_quark = isinstance(song, ShareSong) and song.has_quark_link
        if not has_quark:
            self._status_label.setText(t("cloud_share_no_quark_link"))
        self._update_share_save_button_state()

    def _on_share_result_clicked(self, item: QListWidgetItem):
        """Parse and show file list directly when clicking a search result."""
        song = item.data(Qt.UserRole)
        if not isinstance(song, ShareSong) or not song.has_quark_link:
            self._status_label.setText(t("cloud_share_no_quark_link"))
            return
        self._parse_share_song(song)

    def _parse_selected_share(self):
        """Compatibility wrapper: parse currently selected result if any."""
        selected = self._share_results_list.selectedItems()
        if not selected:
            return
        song = selected[0].data(Qt.UserRole)
        if not isinstance(song, ShareSong) or not song.has_quark_link:
            self._status_label.setText(t("cloud_share_no_quark_link"))
            return
        self._parse_share_song(song)

    def _parse_share_song(self, song: ShareSong):
        """Parse a share song entry and display file list."""

        if not self._current_account or self._current_account.provider != "quark":
            MessageDialog.warning(self, t("error"), t("cloud_share_quark_account_required"))
            return

        pwd_id, passcode = QuarkDriveService.parse_share_url(song.quark_link or "")
        if not pwd_id:
            self._status_label.setText(t("cloud_share_parse_failed"))
            return

        stoken = QuarkDriveService.get_share_stoken(
            self._current_account.access_token, pwd_id, passcode
        )
        if not stoken:
            self._status_label.setText(t("cloud_share_parse_failed"))
            return

        self._capture_pre_share_browse_state()
        self._share_pwd_id = pwd_id
        self._share_stoken = stoken
        self._share_root_title = song.name or song.title or "share"
        self._share_history = []
        self._share_mode = True
        self._batch_download_btn.setVisible(False)
        self._cancel_downloads_btn.setVisible(False)
        self._share_results_list.setVisible(True)
        self._stack.setVisible(True)
        self._update_toolbar_for_search_results(True)
        self._adjust_share_results_height()
        self._update_share_save_button_state()

        self._path_label.setText(f"/{self._share_root_title}")
        root_items = QuarkDriveService.get_share_detail(
            self._current_account.access_token, self._share_pwd_id, self._share_stoken, "0"
        )

        # Auto-enter when root has only one folder
        dirs = [x for x in root_items if x.get("dir")]
        files = [x for x in root_items if not x.get("dir")]
        if len(dirs) == 1 and len(files) == 0:
            folder = dirs[0]
            self._share_history.append(("0", f"/{self._share_root_title}"))
            self._load_share_folder(folder.get("fid", "0"), f"/{self._share_root_title}/{folder.get('file_name', '')}")
            return

        self._load_share_items(root_items, "0")

    def _clear_share_mode(self, reset_view: bool = True):
        """Exit share mode and restore normal cloud view."""
        self._share_mode = False
        self._share_pwd_id = ""
        self._share_stoken = ""
        self._share_root_title = ""
        self._share_history = []
        self._share_save_selected_btn.setVisible(False)
        self._share_save_selected_btn.setEnabled(False)
        self._share_results_list.clearSelection()
        has_results = self._share_results_list.count() > 0
        self._share_results_list.setVisible(has_results)
        self._stack.setVisible(not has_results)
        self._update_toolbar_for_search_results(has_results)
        self._adjust_share_results_height()
        self._update_share_save_button_state()
        if reset_view and self._current_account and not has_results:
            self._update_file_view()

    def _capture_pre_share_browse_state(self):
        """Store normal cloud browsing state before entering share mode."""
        if self._share_mode or not self._current_account:
            return
        self._pre_share_browse_state = {
            "parent_id": self._current_parent_id,
            "path_label": self._path_label.text(),
            "fid_path": list(self._fid_path),
            "navigation_history": list(self._navigation_history),
            "back_enabled": self._back_btn.isEnabled(),
        }

    def _restore_pre_share_browse_state(self):
        """Restore normal cloud browsing state after leaving share search."""
        state = self._pre_share_browse_state
        if not state:
            return

        self._current_parent_id = state.get("parent_id", "0")
        self._path_label.setText(state.get("path_label", "/"))
        self._fid_path = list(state.get("fid_path", []))
        self._navigation_history = list(state.get("navigation_history", []))
        self._back_btn.setEnabled(bool(state.get("back_enabled", False)))
        self._pre_share_browse_state = None

    def _load_share_folder(self, pdir_fid: str, path_text: str):
        """Load one folder in current parsed share."""
        if not self._current_account:
            return
        items = QuarkDriveService.get_share_detail(
            self._current_account.access_token, self._share_pwd_id, self._share_stoken, pdir_fid
        )
        self._path_label.setText(path_text)
        self._load_share_items(items, pdir_fid)

    def _load_share_items(self, items: list, parent_id: str):
        """Map share detail items and render into file table."""
        files = self._map_share_items_to_cloud_files(items, parent_id)
        self._current_parent_id = parent_id
        self._current_audio_files = [f for f in files if f.file_type == "audio"]
        self._file_table.populate(files, self._current_playing_file_id)
        self._back_btn.setEnabled(bool(self._share_history))
        self._status_label.setText(f"{len(files)} {t('items')}")

    def _map_share_items_to_cloud_files(self, items: list, parent_id: str) -> List[CloudFile]:
        """Convert Quark share detail payload to CloudFile list."""
        files: List[CloudFile] = []
        audio_ext = {"mp3", "flac", "wav", "m4a", "aac", "ogg", "wma", "ape"}
        for raw in items or []:
            file_name = raw.get("file_name", "")
            is_dir = bool(raw.get("dir"))
            if is_dir:
                file_type = "folder"
            else:
                category = raw.get("category", 0)
                file_type_num = raw.get("file_type", 0)
                ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
                if category == 2 or file_type_num == 1 or ext in audio_ext:
                    file_type = "audio"
                else:
                    file_type = "other"

            metadata = json.dumps(
                {
                    "is_share": True,
                    "share_fid_token": raw.get("share_fid_token", ""),
                    "dir": is_dir,
                },
                ensure_ascii=False,
            )

            files.append(
                CloudFile(
                    file_id=str(raw.get("fid", "")),
                    parent_id=parent_id,
                    name=file_name,
                    file_type=file_type,
                    size=raw.get("size"),
                    duration=raw.get("duration"),
                    metadata=metadata,
                )
            )
        return files

    def _is_share_file(self, file: CloudFile) -> bool:
        """Whether a table row comes from parsed share result."""
        if not file.metadata:
            return False
        try:
            data = json.loads(file.metadata)
            return bool(data.get("is_share"))
        except (json.JSONDecodeError, TypeError):
            return False

    def _get_share_meta(self, file: CloudFile) -> dict:
        """Read share metadata payload from CloudFile."""
        if not file.metadata:
            return {}
        try:
            return json.loads(file.metadata)
        except (json.JSONDecodeError, TypeError):
            return {}

    def _save_selected_share_items(self):
        """Save selected items from parsed share to Harmony folder."""
        if not self._share_mode:
            return
        selected_files = self._file_table.get_selected_files()
        share_files = [f for f in selected_files if self._is_share_file(f)]
        if not share_files:
            self._status_label.setText(t("select_files_to_save"))
            return

        folder_fid = self._save_share_files(share_files)
        if folder_fid:
            self._status_label.setText(
                t("cloud_share_saved_to_folder").format(folder="Harmony", count=len(share_files))
            )
        self._update_share_save_button_state()

    def _save_share_files(self, files: List[CloudFile]) -> Optional[str]:
        """Save share files into fixed Harmony folder; return target folder fid."""
        if not self._current_account or self._current_account.provider != "quark":
            return None

        folder_fid, updated_token = QuarkDriveService.ensure_share_save_folder(
            self._current_account.access_token, "Harmony"
        )
        if updated_token:
            self._cloud_account_service.update_token(self._current_account.id, updated_token)
            self._current_account.access_token = updated_token

        if not folder_fid:
            return None

        fid_list: List[str] = []
        fid_token_list: List[str] = []
        for file in files:
            meta = self._get_share_meta(file)
            token = meta.get("share_fid_token", "")
            if not token:
                continue
            fid_list.append(file.file_id)
            fid_token_list.append(token)

        if not fid_list:
            return None

        ok = QuarkDriveService.save_share_items(
            self._current_account.access_token,
            self._share_pwd_id,
            self._share_stoken,
            fid_list,
            fid_token_list,
            folder_fid,
        )
        if not ok:
            return None
        return folder_fid

    def _play_share_audio(self, share_file: CloudFile, start_position: float = 0.0):
        """Play shared audio by saving to cloud first, then downloading for playback."""
        folder_fid = self._save_share_files([share_file])
        if not folder_fid or not self._current_account:
            self._status_label.setText(t("cloud_share_save_failed"))
            return

        result = QuarkDriveService.get_file_list(self._current_account.access_token, folder_fid)
        if isinstance(result, tuple):
            saved_files, updated_token = result
        else:
            saved_files, updated_token = result, None

        if updated_token:
            self._cloud_account_service.update_token(self._current_account.id, updated_token)
            self._current_account.access_token = updated_token

        target = None
        for item in saved_files:
            if item.file_type == "audio" and item.name == share_file.name:
                target = item
                break

        if target is None:
            for item in saved_files:
                if item.file_type == "audio":
                    target = item
                    break

        if target is None:
            self._status_label.setText(t("cloud_share_saved_but_not_found"))
            return

        # Switch to normal mode so context menu is based on saved cloud files.
        self._share_mode = False
        self._share_save_selected_btn.setVisible(False)
        self._share_save_selected_btn.setEnabled(False)
        self._share_results_list.setVisible(False)
        self._stack.setVisible(True)
        self._update_toolbar_for_search_results(False)
        self._adjust_share_results_height()

        # Reuse existing download-and-play pipeline with saved files in Harmony.
        self._current_parent_id = folder_fid
        self._path_label.setText("/Harmony")
        self._fid_path = [folder_fid]
        self._current_audio_files = [f for f in saved_files if f.file_type == "audio"]
        self._file_table.populate(saved_files, self._current_playing_file_id)
        self._back_btn.setEnabled(True)
        self._batch_download_btn.setVisible(len(self._current_audio_files) > 0)
        self._play_audio_file(target, start_position=start_position)

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

        # Show batch download button when audio files are present
        self._batch_download_btn.setVisible(len(self._current_audio_files) > 0)
        if not self._share_mode:
            self._share_save_selected_btn.setVisible(False)

        # Use the CloudFileTable component
        self._file_table.populate(files, self._current_playing_file_id)
        self._status_label.setText(f"{len(files)} {t('items')}")

    # === Navigation ===

    def _on_breadcrumb_clicked(self, target_path: str, level: int):
        """Jump directly to selected breadcrumb level."""
        if target_path == self._path_label.text():
            return

        if self._share_mode:
            self._jump_to_share_breadcrumb(target_path)
            return

        if not self._current_account:
            return

        if self._current_account.provider == "baidu":
            self._jump_to_baidu_breadcrumb(target_path)
            return

        depth = max(0, min(level, len(self._fid_path)))
        self._fid_path = self._fid_path[:depth]
        self._navigation_history = self._navigation_history[:depth]
        self._current_parent_id = self._fid_path[-1] if self._fid_path else "0"
        self._path_label.setText(target_path)
        self._back_btn.setEnabled(depth > 0)
        self._load_files()

    def _jump_to_share_breadcrumb(self, target_path: str):
        """Jump to an ancestor path while browsing parsed share folders."""
        root_path = f"/{self._share_root_title}" if self._share_root_title else "/"
        if target_path == "/":
            target_path = root_path

        if target_path == root_path:
            self._share_history = []
            self._load_share_folder("0", root_path)
            self._back_btn.setEnabled(False)
            return

        for idx, (parent_id, path) in enumerate(self._share_history):
            if path != target_path:
                continue
            self._share_history = self._share_history[:idx]
            self._load_share_folder(parent_id, path)
            self._back_btn.setEnabled(bool(self._share_history))
            return

    def _jump_to_baidu_breadcrumb(self, target_path: str):
        """Jump to an ancestor path for Baidu provider."""
        normalized = target_path if target_path.startswith("/") else f"/{target_path}"
        if len(normalized) > 1:
            normalized = normalized.rstrip("/")
        depth = 0 if normalized == "/" else len([p for p in normalized.strip("/").split("/") if p])
        self._navigation_history = self._navigation_history[:depth]
        self._fid_path = normalized.strip("/").split("/") if normalized != "/" else []
        self._current_parent_id = normalized
        self._path_label.setText(normalized)
        self._back_btn.setEnabled(normalized != "/")
        self._load_files()

    def _navigate_to_folder(self, file: CloudFile):
        """Navigate to a folder."""
        if self._share_mode and self._is_share_file(file):
            current_path = self._path_label.text()
            self._share_history.append((self._current_parent_id, current_path))
            if current_path == "/":
                new_path = f"/{file.name}"
            else:
                new_path = f"{current_path}/{file.name}"
            self._load_share_folder(file.file_id, new_path)
            return

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
        if self._share_mode:
            if not self._share_history:
                self._back_btn.setEnabled(False)
                return
            parent_id, path = self._share_history.pop()
            self._load_share_folder(parent_id, path)
            self._back_btn.setEnabled(bool(self._share_history))
            return

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
        if self._share_mode and self._is_share_file(file):
            self._play_share_audio(file, start_position or 0.0)
            return

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

            local_file_path = build_cloud_cache_path(download_dir, file)

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
        self._file_context_menu.show_menu(
            file,
            self._current_audio_files,
            self._current_account.id if self._current_account else None,
            share_mode=self._share_mode and self._is_share_file(file),
        )

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

        if self._config_manager:
            download_dir = Path(self._config_manager.get_cloud_download_dir())
        else:
            download_dir = Path("data/cloud_downloads")

        if not download_dir.is_absolute():
            download_dir = Path.cwd() / download_dir

        local_file_path = build_cloud_cache_path(download_dir, file)

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

                # Emit download_completed signal to create track in library
                EventBus.instance().download_completed.emit(file.file_id, str(local_file_path))
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

                # Emit download_completed signal to create track in library
                EventBus.instance().download_completed.emit(file.file_id, local_path)
        else:
            self._status_label.setText(f"{t('download_failed')}: {file.name}")

    # === Batch Download ===

    def _download_selected_files(self):
        """Download selected audio files sequentially."""
        if not self._current_account:
            return

        selected_files = self._file_table.get_selected_audio_files()
        if not selected_files:
            self._status_label.setText(t("select_files_to_download"))
            return

        # Filter out already-downloaded files
        to_download = []
        for f in selected_files:
            if f.local_path:
                local_path = Path(f.local_path)
                if local_path.exists() and f.size:
                    actual_size = local_path.stat().st_size
                    size_diff = abs(actual_size - f.size)
                    tolerance = f.size * 0.01
                    if size_diff <= tolerance:
                        continue
            to_download.append(f)

        if not to_download:
            self._status_label.setText(f"✓ {t('file_already_exists')}")
            return

        self._download_queue = list(to_download)
        self._batch_total = len(self._download_queue)
        self._batch_completed = 0
        self._is_downloading = True

        # Update UI
        self._batch_download_btn.setEnabled(False)
        self._cancel_downloads_btn.setVisible(True)

        self._status_label.setText(
            t("download_progress").format(current=0, total=self._batch_total)
        )

        self._process_next_download()

    def _process_next_download(self):
        """Process the next file in the download queue."""
        if not self._download_queue:
            self._on_batch_complete()
            return

        file = self._download_queue.pop(0)
        current_num = self._batch_completed + 1

        size_info = ""
        if file.size:
            size_mb = file.size / (1024 * 1024)
            size_info = f" ({size_mb:.1f} MB)"

        self._status_label.setText(
            f"{t('download_progress').format(current=current_num, total=self._batch_total)}"
            f" - {file.name}{size_info}"
        )

        # Check if file already exists at database path
        db_local_path = None
        if self._current_account:
            db_file = self._cloud_file_service.get_file_by_file_id(file.file_id)
            if db_file and db_file.local_path:
                db_local_path = db_file.local_path

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
            db_local_path,
            self._current_account.provider,
        )

        # Store reference for cancellation
        self._current_download_thread = download_thread

        download_thread.finished.connect(
            lambda path, f=file: self._on_batch_download_finished(path, f)
        )
        download_thread.file_exists.connect(
            lambda path, f=file: self._on_batch_download_finished(path, f)
        )
        download_thread.token_updated.connect(self._on_token_updated)
        download_thread.start()

    def _on_batch_download_finished(self, local_path: str, file: CloudFile):
        """Handle completion of a single batch download."""
        self._current_download_thread = None
        self._batch_completed += 1

        if local_path:
            import os
            if os.path.exists(local_path):
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
                EventBus.instance().download_completed.emit(file.file_id, local_path)
            else:
                logger.warning(f"[BatchDownload] File not found after download: {file.name}")
        else:
            logger.warning(f"[BatchDownload] Download failed: {file.name}")

        # Process next download
        self._process_next_download()

    def _on_batch_complete(self):
        """Handle completion of all batch downloads."""
        self._is_downloading = False
        self._current_download_thread = None
        self._batch_download_btn.setEnabled(True)
        self._cancel_downloads_btn.setVisible(False)

        self._status_label.setText(
            t("all_downloads_complete").format(count=self._batch_completed)
        )
        QTimer.singleShot(5000, lambda: self._status_label.setText(""))

    def _cancel_downloads(self):
        """Cancel all pending downloads."""
        self._download_queue.clear()

        if self._current_download_thread:
            self._current_download_thread.terminate()
            self._current_download_thread.wait(2000)
            self._current_download_thread = None

        self._is_downloading = False
        self._batch_download_btn.setEnabled(True)
        self._cancel_downloads_btn.setVisible(False)

        self._status_label.setText("")

    def _edit_media_info(self, file: CloudFile):
        """Edit media info for a cloud file."""
        # Get track by cloud file ID
        track = self._library_service.get_track_by_cloud_file_id(file.file_id)
        if not track:
            # Try to find by path
            if file.local_path:
                track = self._library_service.get_track_by_path(file.local_path)

        if not track:
            from ui.dialogs.message_dialog import MessageDialog
            MessageDialog.warning(self, t("error"), t("track_not_found"))
            return

        # Use EditMediaInfoDialog
        from ui.dialogs.edit_media_info_dialog import EditMediaInfoDialog
        dialog = EditMediaInfoDialog([track.id], self._library_service, self)
        if dialog.exec():
            self._status_label.setText(f"✓ {t('metadata_saved')}")

    def _download_cover(self, file: CloudFile):
        """Download cover art for a cloud file."""
        # Get track by cloud file ID
        track = self._library_service.get_track_by_cloud_file_id(file.file_id)
        if not track:
            # Try to find by path
            if file.local_path:
                track = self._library_service.get_track_by_path(file.local_path)

        if not track:
            from ui.dialogs.message_dialog import MessageDialog
            MessageDialog.warning(self, t("error"), t("track_not_found"))
            return

        # Show cover download dialog
        from ui.dialogs.universal_cover_download_dialog import UniversalCoverDownloadDialog
        from ui.strategies.track_search_strategy import TrackSearchStrategy
        from app.bootstrap import Bootstrap

        bootstrap = Bootstrap.instance()
        strategy = TrackSearchStrategy(
            [track],
            bootstrap.track_repo,
            bootstrap.event_bus
        )
        dialog = UniversalCoverDownloadDialog(strategy, self._cover_service, self)
        dialog.exec()

    def _open_file_location(self, file: CloudFile):
        """Open file location in file manager."""
        if file.local_path:
            import subprocess
            import sys

            path = Path(file.local_path)
            if not path.exists():
                MessageDialog.warning(self, "Error", t("file_not_found"))
                return

            if path.exists():
                if sys.platform == "win32":
                    subprocess.run(["explorer", "/select,", str(path)])
                elif sys.platform == "darwin":
                    subprocess.run(["open", "-R", str(path)])
                else:
                    # Linux
                    # Try to select file in supported file managers
                    file_managers = {
                        "nautilus": ["nautilus", "--select", str(path)],
                        "dolphin": ["dolphin", "--select", str(path)],
                        "caja": ["caja", "--select", str(path)],
                        "nemo": ["nemo", str(path)],
                    }

                    for fm, cmd in file_managers.items():
                        if shutil.which(fm):
                            subprocess.Popen(cmd)
                            return

                    # fallback
                    subprocess.Popen(["xdg-open", str(path.parent)])

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
        if self._current_playing_file_id:
            is_playing = state == "playing"
            self._file_table.update_playing_status(self._current_playing_file_id, is_playing)

    # === Public API ===

    def refresh_ui(self):
        """Refresh the UI with latest data."""
        self._load_accounts()
        self._data_loaded = True

        self._account_list_title.setText(t("cloud_drive"))
        self._add_account_btn.setText(t("add_account"))
        self._back_btn.setText("← " + t("back"))
        self._batch_download_btn.setText(t("batch_download"))
        self._cancel_downloads_btn.setText(t("cancel_downloads"))
        self._share_search_input.setPlaceholderText(t("cloud_share_search_placeholder"))
        self._share_search_btn.setText(t("search"))
        self._share_page_label.setText(f"{self._share_search_page}/{max(1, self._share_search_total_pages)}")
        self._share_save_selected_btn.setText(t("save_selected_to_cloud"))
        self._account_title.setText(
            self._current_account.account_name if self._current_account else t("select_account")
        )

        # Refresh file table headers
        if hasattr(self, '_file_table'):
            self._file_table.refresh_ui()

    def refresh_theme(self):
        """Apply themed styles using ThemeManager tokens."""
        from system.theme import ThemeManager
        tm = ThemeManager.instance()
        self.setStyleSheet(tm.get_qss(self._STYLE_TEMPLATE))
        self._share_search_input.setStyleSheet(tm.get_qss(self._SEARCH_INPUT_STYLE_TEMPLATE))
        self._share_search_btn.setStyleSheet(tm.get_qss(self._SEARCH_BUTTON_STYLE_TEMPLATE))
        self._path_label.set_breadcrumb_color(tm.current_theme.text)

    def _adjust_share_results_height(self):
        """Keep search results list around half-height when visible."""
        if self._share_results_list.isVisible():
            self._share_results_list.setFixedHeight(max(180, int(self.height() * 0.45)))
        else:
            self._share_results_list.setFixedHeight(0)

    def _update_toolbar_for_search_results(self, has_results: bool):
        """Hide/show toolbar controls when search results are visible."""
        if has_results:
            self._batch_download_btn.setVisible(False)
            self._back_btn.setVisible(False)
            self._path_label.setVisible(False)
        else:
            self._back_btn.setVisible(True)
            self._path_label.setVisible(True)
            if not self._share_mode:
                self._batch_download_btn.setVisible(len(self._current_audio_files) > 0)

    def _update_share_save_button_state(self):
        """Update visibility/enabled state for 'save selected' action."""
        selected_results = self._share_results_list.selectedItems()
        has_selected_share = False
        if selected_results:
            song = selected_results[0].data(Qt.UserRole)
            has_selected_share = isinstance(song, ShareSong) and song.has_quark_link

        should_show = self._share_mode and has_selected_share
        self._share_save_selected_btn.setVisible(should_show)
        if not should_show:
            self._share_save_selected_btn.setEnabled(False)
            return

        selected_files = self._file_table.get_selected_files()
        has_files = any(self._is_share_file(f) for f in selected_files)
        self._share_save_selected_btn.setEnabled(has_files)

    def showEvent(self, event):
        """Handle show event."""
        super().showEvent(event)
        if not self._data_loaded:
            self._load_accounts()
        self._adjust_share_results_height()

    def resizeEvent(self, event):
        """Update dynamic sizes on resize."""
        super().resizeEvent(event)
        self._adjust_share_results_height()

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

    def closeEvent(self, event):
        """Disconnect EventBus connections to prevent leaked signal handlers."""
        if self._event_bus:
            try:
                self._event_bus.download_started.disconnect(self._on_event_bus_download_started)
                self._event_bus.download_completed.disconnect(self._on_event_bus_download_completed)
                self._event_bus.track_changed.disconnect(self._on_track_changed)
                self._event_bus.playback_state_changed.disconnect(self._on_playback_state_changed)
            except (TypeError, RuntimeError):
                pass
        super().closeEvent(event)
