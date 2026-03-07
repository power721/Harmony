"""
Cloud drive view for browsing and playing cloud files.
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QStackedWidget,
    QMessageBox,
    QMenu,
    QAbstractItemView,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QApplication,
)
from PySide6.QtCore import Qt, Signal, QThread, QTimer
from PySide6.QtGui import QCursor, QColor, QBrush
from typing import List, Optional
import tempfile
import os
from database.models import CloudAccount, CloudFile
from services.quark_drive_service import QuarkDriveService
from ui.cloud_login_dialog import CloudLoginDialog
from utils import t, format_duration


class CloudDriveView(QWidget):
    """View for browsing and playing cloud drive files"""

    track_double_clicked = Signal(str)  # Signal for playing track (temp file path)
    play_cloud_files = Signal(
        str, int, list
    )  # Signal for playing multiple cloud files (temp_path, index, cloud_files)

    def __init__(self, db_manager, player, config_manager=None, parent=None):
        super().__init__(parent)
        self._db = db_manager
        self._player = player
        self._config_manager = config_manager
        self._current_account: Optional[CloudAccount] = None
        self._current_parent_id = "0"  # Root folder
        self._navigation_history = []  # For back navigation
        self._current_audio_files = []  # Track audio files in current folder

        self._setup_ui()
        self._load_accounts()

    def _setup_ui(self):
        """Setup UI components"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Splitter for account list and file list
        splitter = QSplitter(Qt.Horizontal)

        # Left side - account list
        account_list_widget = self._create_account_list()
        splitter.addWidget(account_list_widget)

        # Right side - file list content
        file_content = self._create_file_content()
        splitter.addWidget(file_content)

        splitter.setStretchFactor(0, 1)  # Account list gets 1/4
        splitter.setStretchFactor(1, 3)  # File list gets 3/4

        layout.addWidget(splitter)

        # Apply styles
        self._apply_styles()

    def _create_account_list(self) -> QWidget:
        """Create the account list widget."""
        widget = QWidget()
        widget.setObjectName("accountListPanel")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 20, 15, 10)
        layout.setSpacing(10)

        # Title
        self._account_list_title = QLabel("☁️ " + t("accounts"))
        self._account_list_title.setStyleSheet("""
            color: #1db954;
            font-size: 20px;
            font-weight: bold;
            margin-bottom: 10px;
        """)
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
        self._account_list.setAlternatingRowColors(True)
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
        self._account_title.setStyleSheet("""
            color: #1db954;
            font-size: 24px;
            font-weight: bold;
        """)
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
        self._path_label.setStyleSheet("""
            color: #c0c0c0;
            font-size: 14px;
            padding: 0 10px;
        """)
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
        empty_label.setStyleSheet("color: #808080; font-size: 14px;")
        empty_layout.addWidget(empty_label)
        empty_page.setLayout(empty_layout)
        self._stack.addWidget(empty_page)

        # File browser page
        browser_page = QWidget()
        browser_layout = QVBoxLayout()

        # File table with same styling as LibraryView
        self._file_table = QTableWidget()
        self._file_table.setObjectName("cloudFilesTable")
        self._file_table.setColumnCount(4)
        self._file_table.setHorizontalHeaderLabels([t("title"), t("type"), t("size"), t("duration")])

        # Configure table to match LibraryView
        self._file_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._file_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._file_table.setAlternatingRowColors(True)
        self._file_table.verticalHeader().setVisible(False)

        # Set column resize modes - Title gets all remaining space
        header = self._file_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Title column stretches
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Type auto-size
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Size auto-size
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Duration auto-size

        self._file_table.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._file_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._file_table.customContextMenuRequested.connect(self._show_context_menu)
        self._file_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._file_table.setFocusPolicy(Qt.NoFocus)

        browser_layout.addWidget(self._file_table)

        browser_page.setLayout(browser_layout)
        self._stack.addWidget(browser_page)

        layout.addWidget(self._stack)

        # Status bar
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(
            "color: #808080; font-size: 13px; padding: 8px 0px;"
        )
        layout.addWidget(self._status_label)

        return widget

    def _apply_styles(self):
        """Apply modern widget styles."""
        self.setStyleSheet("""
            QWidget#accountListPanel {
                background-color: #141414;
                border-right: 1px solid #2a2a2a;
            }
            QWidget#fileContentPanel {
                background-color: #141414;
            }
            QPushButton#addAccountBtn {
                background: #1db954;
                color: #000000;
                border: none;
                padding: 10px 16px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton#addAccountBtn:hover {
                background: #1ed760;
            }
            QPushButton#backBtn {
                background: transparent;
                border: 2px solid #404040;
                color: #c0c0c0;
                padding: 8px 15px;
                border-radius: 6px;
                font-weight: 500;
            }
            QPushButton#backBtn:hover {
                border-color: #1db954;
                color: #1db954;
                background-color: rgba(29, 185, 84, 0.1);
            }
            QPushButton#backBtn:disabled {
                border-color: #2a2a2a;
                color: #404040;
            }
            QListWidget#accountList {
                background-color: #1e1e1e;
                border: none;
                border-radius: 8px;
                padding: 4px;
            }
            QListWidget#accountList::item {
                padding: 12px 16px;
                color: #e0e0e0;
                border-radius: 4px;
                margin: 2px 0;
            }
            QListWidget#accountList::item:selected {
                background-color: #1db954;
                color: #000000;
                font-weight: 600;
            }
            QListWidget#accountList::item:hover {
                background-color: #2a2a2a;
            }
            QListWidget#accountList::item:selected:hover {
                background-color: #1ed760;
            }
            QTableWidget#cloudFilesTable {
                background-color: #1e1e1e;
                border: none;
                border-radius: 8px;
                gridline-color: #2a2a2a;
            }
            QTableWidget#cloudFilesTable::item {
                padding: 12px 8px;
                color: #e0e0e0;
                border: none;
                border-bottom: 1px solid #2a2a2a;
            }
            QTableWidget#cloudFilesTable::item:alternate {
                background-color: #252525;
            }
            QTableWidget#cloudFilesTable::item:!alternate {
                background-color: #1e1e1e;
            }
            QTableWidget#cloudFilesTable::item:selected {
                background-color: #1db954;
                color: #ffffff;
                font-weight: 500;
            }
            QTableWidget#cloudFilesTable::item:selected:!alternate {
                background-color: #1db954;
            }
            QTableWidget#cloudFilesTable::item:selected:alternate {
                background-color: #1ed760;
            }
            QTableWidget#cloudFilesTable::item:hover {
                background-color: #2d2d2d;
            }
            QTableWidget#cloudFilesTable::item:selected:hover {
                background-color: #1ed760;
            }
            QTableWidget#cloudFilesTable::item:focus {
                outline: none;
                border: none;
            }
            QTableWidget#cloudFilesTable:focus {
                outline: none;
                border: none;
            }
            QTableWidget#cloudFilesTable QHeaderView::section {
                background-color: #2a2a2a;
                color: #1db954;
                padding: 14px 12px;
                border: none;
                border-bottom: 2px solid #1db954;
                border-radius: 0px;
                font-weight: bold;
                font-size: 13px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            QTableWidget#cloudFilesTable QScrollBar:vertical {
                background-color: #1e1e1e;
                width: 12px;
                border-radius: 6px;
                margin: 0px;
            }
            QTableWidget#cloudFilesTable QScrollBar::handle:vertical {
                background-color: #404040;
                border-radius: 6px;
                min-height: 40px;
            }
            QTableWidget#cloudFilesTable QScrollBar::handle:vertical:hover {
                background-color: #505050;
            }
            QTableWidget#cloudFilesTable QScrollBar:horizontal {
                background-color: #1e1e1e;
                height: 12px;
                border-radius: 6px;
            }
            QTableWidget#cloudFilesTable QScrollBar::handle:horizontal {
                background-color: #404040;
                border-radius: 6px;
                min-width: 40px;
            }
            QTableWidget#cloudFilesTable QScrollBar::handle:horizontal:hover {
                background-color: #505050;
            }
            QTableWidget#cloudFilesTable QScrollBar::add-line, QScrollBar::sub-line {
                height: 0px;
                width: 0px;
            }
        """)

    def _load_accounts(self):
        """Load available cloud accounts"""
        accounts = self._db.get_cloud_accounts(provider="quark")
        self._populate_account_list(accounts)

        # Don't auto-load files on startup
        # Files will only load when user clicks on an account

    def _populate_account_list(self, accounts: List[CloudAccount]):
        """Populate the account list widget."""
        self._account_list.clear()

        for account in accounts:
            item = QListWidgetItem(account.account_name)
            item.setData(Qt.UserRole, account)

            # Set as selected if it's the current account
            if self._current_account and account.id == self._current_account.id:
                self._account_list.setCurrentItem(item)

            self._account_list.addItem(item)

        # Update status
        if not accounts:
            self._stack.setCurrentIndex(0)  # Show empty
        else:
            self._stack.setCurrentIndex(1)  # Show browser

    def _on_account_selected(self, item: QListWidgetItem):
        """Handle account selection."""
        account = item.data(Qt.UserRole)
        if account:
            self._current_account = account
            self._current_parent_id = (
                account.last_folder_id if account.last_folder_id else "0"
            )
            self._path_label.setText(
                account.last_folder_path if account.last_folder_path else "/"
            )
            self._navigation_history.clear()
            self._back_btn.setEnabled(self._current_parent_id != "0")
            self._update_file_view()

    def _update_file_view(self):
        """Update the file view based on current account."""
        if not self._current_account:
            self._account_title.setText(t("select_account"))
            self._stack.setCurrentIndex(0)
            return

        # Update title
        self._account_title.setText(self._current_account.account_name)
        self._stack.setCurrentIndex(1)

        # Load files
        self._load_files()

    def _add_account(self):
        """Add a new cloud account."""
        dialog = CloudLoginDialog(self)
        dialog.login_success.connect(self._on_login_success)
        dialog.exec()

    def _on_login_success(self, account_info: dict):
        """Handle successful login."""
        account_id = self._db.create_cloud_account(
            provider="quark",
            account_name=account_info.get("account_email", "Quark Account"),
            account_email=account_info.get("account_email", ""),
            access_token=account_info.get("access_token", ""),
        )

        # Reload accounts
        accounts = self._db.get_cloud_accounts(provider="quark")
        self._populate_account_list(accounts)

        # Select the new account
        if accounts:
            for i in range(self._account_list.count()):
                item = self._account_list.item(i)
                account = item.data(Qt.UserRole)
                if account.id == account_id:
                    self._account_list.setCurrentItem(item)
                    self._current_account = account
                    self._update_file_view()
                    break

    def _load_files(self):
        """Load files for current directory."""
        if not self._current_account:
            return

        self._status_label.setText(t("loading_files"))

        # Get files from service (returns tuple: files, updated_token)
        result = QuarkDriveService.get_file_list(
            self._current_account.access_token, self._current_parent_id
        )

        # Handle tuple return value
        if isinstance(result, tuple):
            files, updated_token = result
        else:
            files, updated_token = result, None

        # Update token if changed
        if updated_token:
            self._db.update_cloud_account_token(self._current_account.id, updated_token)
            self._current_account.access_token = updated_token

        # Cache files in database
        self._db.cache_cloud_files(self._current_account.id, files)

        # Reload files from database to get local_path information
        files = self._db.get_cloud_files(self._current_account.id, self._current_parent_id)

        # Save audio files for playlist playback
        self._current_audio_files = [f for f in files if f.file_type == "audio"]

        # Update table
        self._populate_table(files)
        self._status_label.setText(f"{len(files)} " + t("items"))

    def _populate_table(self, files: List[CloudFile]):
        """Populate table with files."""
        self._file_table.setRowCount(0)
        self._file_table.setUpdatesEnabled(False)

        try:
            for row, file in enumerate(files):
                self._file_table.insertRow(row)

                # Name
                name_item = QTableWidgetItem(file.name)
                name_item.setData(Qt.UserRole, file)
                name_item.setForeground(QBrush(QColor("#e0e0e0")))

                if file.file_type == "folder":
                    name_item.setText("📁 " + file.name)

                self._file_table.setItem(row, 0, name_item)

                # Type
                type_item = QTableWidgetItem(self._get_file_type_label(file.file_type))
                type_item.setForeground(QBrush(QColor("#b0b0b0")))
                self._file_table.setItem(row, 1, type_item)

                # Size
                size_text = ""
                if file.size:
                    size_mb = file.size / (1024 * 1024)
                    size_text = f"{size_mb:.1f} MB"
                size_item = QTableWidgetItem(size_text)
                size_item.setForeground(QBrush(QColor("#909090")))
                self._file_table.setItem(row, 2, size_item)

                # Duration (only for audio files)
                duration_text = ""
                if file.file_type == "audio" and file.duration:
                    duration_text = format_duration(file.duration)
                duration_item = QTableWidgetItem(duration_text)
                duration_item.setForeground(QBrush(QColor("#909090")))
                self._file_table.setItem(row, 3, duration_item)

        finally:
            self._file_table.setUpdatesEnabled(True)

    def _get_file_type_label(self, file_type: str) -> str:
        """Get display label for file type."""
        labels = {"folder": t("folder"), "audio": t("audio"), "other": t("file")}
        return labels.get(file_type, t("file"))

    def _on_item_double_clicked(self, item: QTableWidgetItem):
        """Handle double-click on item."""
        file = item.data(Qt.UserRole)
        if not file:
            return

        if file.file_type == "folder":
            # Navigate into folder
            self._navigate_to_folder(file.file_id, file.name)
        elif file.file_type == "audio":
            # Play audio file
            self._play_audio_file(file)

    def _navigate_to_folder(self, folder_id: str, folder_name: str):
        """Navigate to a folder."""
        self._navigation_history.append(
            (self._current_parent_id, self._path_label.text())
        )
        self._current_parent_id = folder_id

        # Update path label
        current_path = self._path_label.text()
        if current_path == "/":
            new_path = f"/{folder_name}"
        else:
            new_path = f"{current_path}/{folder_name}"
        self._path_label.setText(new_path)

        self._back_btn.setEnabled(True)

        # Save folder state
        if self._current_account:
            self._db.update_cloud_account_folder(
                self._current_account.id, folder_id, new_path
            )

        self._load_files()

    def _navigate_back(self):
        """Navigate to previous folder."""
        if self._navigation_history:
            parent_id, path = self._navigation_history.pop()
            self._current_parent_id = parent_id
            self._path_label.setText(path)

            if not self._navigation_history:
                self._back_btn.setEnabled(False)

            # Save folder state
            if self._current_account:
                self._db.update_cloud_account_folder(
                    self._current_account.id, parent_id, path
                )

            self._load_files()

    def _play_audio_file(self, file: CloudFile):
        """Play an audio file from cloud."""
        # Find index of this file in current folder's audio list
        try:
            file_index = next(
                i
                for i, f in enumerate(self._current_audio_files)
                if f.file_id == file.file_id
            )
        except StopIteration:
            file_index = 0

        # Check if file already exists locally
        from pathlib import Path
        from utils.helpers import sanitize_filename

        if self._config_manager:
            download_dir = Path(self._config_manager.get_cloud_download_dir())
        else:
            download_dir = Path("data/cloud_downloads")

        safe_filename = sanitize_filename(file.name)
        local_file_path = download_dir / safe_filename

        # Check file status
        if local_file_path.exists() and file.size:
            actual_size = local_file_path.stat().st_size
            size_diff = abs(actual_size - file.size)
            tolerance = file.size * 0.01  # 1% tolerance

            if size_diff > tolerance:
                # File size mismatch
                size_mb = file.size / (1024 * 1024)
                self._status_label.setText(f"{t('file_size_mismatch')}: {file.name} ({size_mb:.1f} MB)")
            else:
                # File exists and size matches
                self._status_label.setText(f"{t('using_cached_file')}: {file.name}")
        else:
            # File doesn't exist or no size info
            size_info = ""
            if file.size:
                size_mb = file.size / (1024 * 1024)
                size_info = f" ({size_mb:.1f} MB)"
            self._status_label.setText(f"{t('downloading')} {file.name}{size_info}...")

        # Create download thread with context info
        download_thread = CloudFileDownloadThread(
            self._current_account.access_token,
            file,
            file_index,
            self._current_audio_files,
            self._config_manager,
            self,
        )
        download_thread.finished.connect(
            lambda path: self._on_file_downloaded(
                path, file_index, self._current_audio_files, file.name
            )
        )
        download_thread.file_exists.connect(
            lambda path: self._on_file_exists(
                path, file_index, self._current_audio_files, file.name
            )
        )
        download_thread.token_updated.connect(self._on_token_updated)
        download_thread.start()

    def _on_file_exists(self, temp_path: str, file_index: int, audio_files: list, file_name: str):
        """Handle when file already exists locally."""
        import os

        if temp_path and os.path.exists(temp_path):
            self._status_label.setText(f"{t('using_cached_file')} - {file_name}")

            # Save local path to database
            if file_index < len(audio_files):
                cloud_file = audio_files[file_index]
                if self._current_account:
                    self._db.update_cloud_file_local_path(
                        cloud_file.file_id,
                        self._current_account.id,
                        temp_path
                    )

            # Emit signal with playlist info
            self.play_cloud_files.emit(temp_path, file_index, audio_files)

            # Update current audio files list with local path
            if file_index < len(self._current_audio_files):
                # Update the CloudFile object in current list
                for i, f in enumerate(self._current_audio_files):
                    if f.file_id == self._current_audio_files[file_index].file_id:
                        # Create updated CloudFile with local_path
                        from database.models import CloudFile as CloudFileModel
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
            print(f"[DEBUG] ERROR: Existing file not found: {temp_path}")
            self._status_label.setText(t("download_failed"))

    def _on_token_updated(self, updated_token: str):
        """Handle updated access token from API calls."""
        if self._current_account and updated_token:
            self._db.update_cloud_account_token(self._current_account.id, updated_token)
            self._current_account.access_token = updated_token

    def _on_file_downloaded(self, temp_path: str, file_index: int, audio_files: list, file_name: str = None):
        """Handle completed file download."""
        if temp_path:
            import os

            if os.path.exists(temp_path):
                # Get file name from parameter or audio_files list
                if not file_name and file_index < len(audio_files):
                    file_name = audio_files[file_index].name
                elif not file_name:
                    file_name = "Unknown"

                # Get file size for display
                file_size = os.path.getsize(temp_path)
                size_mb = file_size / (1024 * 1024)

                self._status_label.setText(f"{t('download_complete')}: {file_name} ({size_mb:.1f} MB)")

                # Save local path to database
                if file_index < len(audio_files):
                    cloud_file = audio_files[file_index]
                    if self._current_account:
                        self._db.update_cloud_file_local_path(
                            cloud_file.file_id,
                            self._current_account.id,
                            temp_path
                        )

                # Emit signal with playlist info
                self.play_cloud_files.emit(temp_path, file_index, audio_files)

                # Update current audio files list with local path
                if file_index < len(self._current_audio_files):
                    # Update the CloudFile object in current list
                    for i, f in enumerate(self._current_audio_files):
                        if f.file_id == self._current_audio_files[file_index].file_id:
                            # Create updated CloudFile with local_path
                            from database.models import CloudFile as CloudFileModel
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
                print(f"[DEBUG] ERROR: Downloaded file does not exist: {temp_path}")
                self._status_label.setText(t("download_failed"))
        else:
            print(f"[DEBUG] ERROR: Download returned empty path")
            self._status_label.setText(t("download_failed"))

    def _show_context_menu(self, pos):
        """Show context menu for file."""
        item = self._file_table.itemAt(pos)
        if not item:
            return

        file = item.data(Qt.UserRole)
        if not file or file.file_type != "audio":
            return

        # Check if file has been downloaded
        has_local_path = file.local_path

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 1px solid #404040;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #1db954;
                color: #000000;
            }
            QMenu::item:disabled {
                color: #808080;
            }
        """)

        play_action = menu.addAction(t("play"))
        play_action.triggered.connect(lambda: self._play_audio_file(file))

        menu.addSeparator()

        # Add file info action
        info_text = f"ℹ️ {t('file_info')}"
        if file.size:
            size_mb = file.size / (1024 * 1024)
            info_text += f" ({size_mb:.1f} MB)"
        if file.duration:
            from utils import format_duration
            info_text += f" - {format_duration(file.duration)}"

        info_action = menu.addAction(info_text)
        info_action.setEnabled(False)  # Just for display, not clickable

        menu.addSeparator()

        queue_action = menu.addAction(t("add_to_queue"))
        queue_action.triggered.connect(lambda: self._add_to_queue(file))

        menu.addSeparator()

        # Edit media info action - only available if file is downloaded
        edit_action = menu.addAction(t("edit_media_info"))
        if has_local_path:
            edit_action.triggered.connect(lambda: self._edit_media_info(file))
        else:
            edit_action.setEnabled(False)
            edit_action.setText(f"{t('edit_media_info')} ({t('download_first')})")

        # Open file location action - only available if file is downloaded
        open_action = menu.addAction(t("open_file_location"))
        if has_local_path:
            open_action.triggered.connect(lambda: self._open_file_location(file))
        else:
            open_action.setEnabled(False)
            open_action.setText(f"{t('open_file_location')} ({t('download_first')})")

        menu.exec_(QCursor.pos())

    def _show_account_context_menu(self, pos):
        """Show context menu for account."""
        item = self._account_list.itemAt(pos)
        if not item:
            return

        account = item.data(Qt.UserRole)
        if not account:
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 1px solid #404040;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #1db954;
                color: #000000;
            }
        """)

        # Add account info action
        info_action = menu.addAction("ℹ️ " + t("get_account_info"))
        info_action.triggered.connect(lambda: self._get_account_info(account))

        menu.addSeparator()

        # Add change download directory action
        change_dir_action = menu.addAction("📁 " + t("change_download_dir"))
        change_dir_action.triggered.connect(lambda: self._change_download_dir())

        menu.addSeparator()

        # Add delete action
        delete_action = menu.addAction("🗑️ " + t("delete_account"))
        delete_action.triggered.connect(lambda: self._delete_account(account))

        menu.exec_(QCursor.pos())

    def _get_account_info(self, account: CloudAccount):
        """Get and display account information."""
        print(f"[DEBUG] Getting account info for: {account.account_name}")

        self._status_label.setText(f"{t('loading')} {t('account_info')}...")

        # Get account info from service (returns tuple: info, updated_token)
        result = QuarkDriveService.get_account_info(
            account.access_token, account.account_email
        )

        # Handle tuple return value
        if isinstance(result, tuple):
            account_info, updated_token = result
        else:
            account_info, updated_token = result, None

        # Update token if changed
        if updated_token:
            self._db.update_cloud_account_token(account.id, updated_token)
            account.access_token = updated_token
            # Also update current account if it's the same
            if self._current_account and self._current_account.id == account.id:
                self._current_account.access_token = updated_token

        if account_info:
            # Show account info dialog
            self._show_account_info_dialog(account, account_info)
            self._status_label.setText("")
        else:
            self._status_label.setText(t("failed_to_get_account_info"))
            QMessageBox.warning(self, t("error"), t("failed_to_get_account_info"))

    def _show_account_info_dialog(self, account: CloudAccount, account_info: dict):
        """Show account information dialog."""
        dialog = QMessageBox(self)
        dialog.setWindowTitle(t("account_info"))

        # Format timestamps
        created_at_str = self._format_timestamp(account_info.get("created_at"))
        exp_at_str = self._format_timestamp(account_info.get("exp_at"))

        # Format capacity
        total_capacity_str = self._format_capacity(
            account_info.get("total_capacity", 0)
        )
        used_capacity_str = self._format_capacity(account_info.get("use_capacity", 0))

        # Calculate usage percentage
        total_cap = account_info.get("total_capacity", 0)
        used_cap = account_info.get("use_capacity", 0)
        if total_cap > 0:
            usage_percent = (used_cap / total_cap) * 100
            usage_str = f"{usage_percent:.1f}%"
        else:
            usage_str = "N/A"

        # Build info text
        info_text = f"""
{t("account_name")}: {account_info.get("nickname", account.account_name)}
{t("member_type")}: {account_info.get("member_type", "unknown")}
{t("account_created")}: {created_at_str}
{t("vip_expires")}: {exp_at_str}
{t("storage_used")}: {used_capacity_str} / {total_capacity_str} ({usage_str})
"""

        dialog.setText(info_text)
        dialog.setIcon(QMessageBox.Information)
        dialog.setStandardButtons(QMessageBox.Ok)

        # Style the dialog
        dialog.setStyleSheet("""
            QMessageBox {
                background-color: #1e1e1e;
            }
            QMessageBox QLabel {
                color: #e0e0e0;
                font-size: 13px;
            }
        """)

        dialog.exec()

    def _format_timestamp(self, timestamp_ms: int) -> str:
        """Format millisecond timestamp to readable date string."""
        if not timestamp_ms:
            return "N/A"

        try:
            from datetime import datetime

            # Convert milliseconds to seconds
            timestamp_sec = timestamp_ms / 1000
            dt = datetime.fromtimestamp(timestamp_sec)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            print(f"[DEBUG] Error formatting timestamp: {e}")
            return "N/A"

    def _format_capacity(self, bytes_size: int) -> str:
        """Format bytes to readable size string (TB/GB/MB)."""
        if not bytes_size or bytes_size == 0:
            return "0 GB"

        try:
            tb = bytes_size / (1024**4)
            gb = bytes_size / (1024**3)
            mb = bytes_size / (1024**2)

            if tb >= 1:
                return f"{tb:.2f} TB"
            elif gb >= 1:
                return f"{gb:.2f} GB"
            else:
                return f"{mb:.2f} MB"
        except Exception as e:
            print(f"[DEBUG] Error formatting capacity: {e}")
            return "N/A"

    def _delete_account(self, account: CloudAccount):
        """Delete a cloud account."""
        reply = QMessageBox.question(
            self,
            t("delete_account"),
            f"{t('delete_account_confirm')}\n\n{account.account_name}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self._db.delete_cloud_account(account.id)

            # Reload accounts
            accounts = self._db.get_cloud_accounts(provider="quark")
            self._populate_account_list(accounts)

            # Reset current account if needed
            if self._current_account and self._current_account.id == account.id:
                self._current_account = None
                self._update_file_view()

    def _add_to_queue(self, file: CloudFile):
        """Add file to play queue."""
        # TODO: Implement queue addition
        pass

    def _edit_media_info(self, file: CloudFile):
        """Edit media info for downloaded cloud file."""
        from PySide6.QtWidgets import (
            QDialog,
            QVBoxLayout,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QDialogButtonBox,
            QPushButton,
            QFormLayout,
            QMessageBox,
        )
        from services import MetadataService
        from pathlib import Path

        if not file.local_path:
            QMessageBox.warning(self, "Error", "File not downloaded")
            return

        # Extract current metadata from file
        current_metadata = MetadataService.extract_metadata(file.local_path)

        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"{t('edit_media_info_title')} - {file.name}")
        dialog.setMinimumWidth(450)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #2a2a2a;
                color: #e0e0e0;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 13px;
            }
            QLineEdit {
                background-color: #1a1a1a;
                color: #e0e0e0;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #1db954;
            }
            QPushButton {
                background-color: #1db954;
                color: #000000;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1ed760;
            }
            QPushButton[role="cancel"] {
                background-color: #404040;
                color: #e0e0e0;
            }
            QPushButton[role="cancel"]:hover {
                background-color: #505050;
            }
        """)

        layout = QVBoxLayout(dialog)
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        form_layout.setLabelAlignment(Qt.AlignRight)

        # Title field
        title_input = QLineEdit(current_metadata.get("title") or file.name)
        title_input.setPlaceholderText(t("enter_title"))
        form_layout.addRow(t("title") + ":", title_input)

        # Artist field
        artist_input = QLineEdit(current_metadata.get("artist") or "")
        artist_input.setPlaceholderText(t("enter_artist"))
        form_layout.addRow(t("artist") + ":", artist_input)

        # Album field
        album_input = QLineEdit(current_metadata.get("album") or "")
        album_input.setPlaceholderText(t("enter_album"))
        form_layout.addRow(t("album") + ":", album_input)

        # Show file information
        try:
            track_file = Path(file.local_path)
            file_size = track_file.stat().st_size
            file_size_str = self._format_file_size(file_size)

            # Get audio codec info using mutagen
            import mutagen

            audio_info = mutagen.File(file.local_path)
            media_info = []

            if audio_info and hasattr(audio_info, "info"):
                info = audio_info.info
                # Bitrate
                if hasattr(info, "bitrate") and info.bitrate:
                    media_info.append(f"{info.bitrate // 1000} kbps")

                # Sample rate
                if hasattr(info, "sample_rate") and info.sample_rate:
                    media_info.append(f"{info.sample_rate // 1000} kHz")

                # Length/Duration
                if hasattr(info, "length") and info.length:
                    minutes = int(info.length // 60)
                    seconds = int(info.length % 60)
                    media_info.append(f"{minutes}:{seconds:02d}")

            # Format (codec)
            if audio_info:
                mime_type = audio_info.mime if hasattr(audio_info, "mime") else []
                if mime_type:
                    format_str = mime_type[0].split("/")[-1].upper()
                    media_info.append(format_str)
                else:
                    # Try to get format from type
                    if hasattr(audio_info, "type"):
                        media_info.append(audio_info.type)

            # Create info text
            file_info_text = f"{file_size_str}"
            if media_info:
                file_info_text += f" | {' | '.join(media_info)}"

            info_label = QLabel(file_info_text)
            info_label.setStyleSheet("color: #808080; font-size: 11px;")

            # File path
            path_label = QLabel(file.local_path)
            path_label.setStyleSheet("color: #606060; font-size: 10px;")
            path_label.setWordWrap(True)

            # Add both labels in a vertical layout
            info_container = QWidget()
            info_layout = QVBoxLayout(info_container)
            info_layout.setContentsMargins(0, 0, 0, 0)
            info_layout.setSpacing(2)
            info_layout.addWidget(info_label)
            info_layout.addWidget(path_label)

            form_layout.addRow(t("file") + ":", info_container)

        except Exception as e:
            # Fallback to just show path if there's an error
            path_label = QLabel(file.local_path)
            path_label.setStyleSheet("color: #808080; font-size: 11px;")
            path_label.setWordWrap(True)
            form_layout.addRow(t("file") + ":", path_label)

        layout.addLayout(form_layout)

        # Buttons
        buttons = QDialogButtonBox()
        ok_button = QPushButton(t("save"))
        cancel_button = QPushButton(t("cancel"))
        cancel_button.setProperty("role", "cancel")

        buttons.addButton(ok_button, QDialogButtonBox.AcceptRole)
        buttons.addButton(cancel_button, QDialogButtonBox.RejectRole)

        layout.addWidget(buttons)

        def save_changes():
            new_title = title_input.text().strip() or file.name
            new_artist = artist_input.text().strip()
            new_album = album_input.text().strip()

            # Save to file
            success = MetadataService.save_metadata(
                file.local_path,
                title=new_title,
                artist=new_artist,
                album=new_album,
            )

            if success:
                # Update database cache (update cloud file name if title changed)
                if new_title != file.name:
                    # Update the file display name in database
                    self._db.cache_cloud_files(self._current_account.id, [file])

                QMessageBox.information(self, t("success"), t("media_saved"))

                # Refresh the file list to show updated metadata
                self._load_files()
            else:
                QMessageBox.warning(self, "Error", t("media_save_failed"))

            dialog.accept()

        ok_button.clicked.connect(save_changes)
        cancel_button.clicked.connect(dialog.reject)

        dialog.exec_()

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def _open_file_location(self, file: CloudFile):
        """Open the file location in system file manager."""
        if not file.local_path:
            return

        import platform
        import subprocess
        import shutil
        from pathlib import Path
        from PySide6.QtWidgets import QMessageBox

        file_path = Path(file.local_path)
        if not file_path.exists():
            QMessageBox.warning(self, "Error", t("file_not_found"))
            return

        try:
            system = platform.system()

            if system == "Windows":
                subprocess.Popen(["explorer", "/select," + str(file_path)])

            elif system == "Darwin":
                subprocess.Popen(["open", "-R", str(file_path)])

            else:
                # Linux
                # Try to select file in supported file managers
                file_managers = {
                    "nautilus": ["nautilus", "--select", str(file_path)],
                    "dolphin": ["dolphin", "--select", str(file_path)],
                    "caja": ["caja", "--select", str(file_path)],
                    "nemo": ["nemo", str(file_path)],
                }

                for fm, cmd in file_managers.items():
                    if shutil.which(fm):
                        subprocess.Popen(cmd)
                        return

                # fallback - open directory only
                subprocess.Popen(["xdg-open", str(file_path.parent)])

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open file location: {e}")

    def _change_download_dir(self):
        """Change the cloud download directory."""
        if not self._config_manager:
            return

        current_dir = self._config_manager.get_cloud_download_dir()

        # Open directory selection dialog
        from PySide6.QtWidgets import QFileDialog

        new_dir = QFileDialog.getExistingDirectory(
            self,
            t("select_download_dir"),
            current_dir,
        )

        if new_dir:
            self._config_manager.set_cloud_download_dir(new_dir)
            self._status_label.setText(f"{t('cloud_download_dir')}: {new_dir}")

    def refresh_ui(self):
        """Refresh UI texts after language change."""
        # Update account list title
        self._account_list_title.setText("☁️ " + t("accounts"))

        # Update button texts
        self._add_account_btn.setText(t("add_account"))
        if hasattr(self, "_back_btn"):
            self._back_btn.setText("← " + t("back"))

        # Update table headers
        if hasattr(self, "_file_table"):
            self._file_table.setHorizontalHeaderLabels(
                [t("title"), t("type"), t("size"), t("duration")]
            )

        # Update title based on state
        if self._current_account:
            self._account_title.setText(self._current_account.account_name)
        else:
            self._account_title.setText(t("select_account"))

        # Update empty state label
        if self._stack.count() > 0:
            empty_page = self._stack.widget(0)
            if empty_page:
                empty_label = empty_page.findChild(QLabel, "emptyLabel")
                if empty_label:
                    empty_label.setText(t("add_cloud_account"))

    def restore_playback_state(self, account_id: int, file_path: str, file_fid: str, auto_play: bool = False):
        """
        Restore previous cloud playback state.

        Args:
            account_id: Account ID to select
            file_path: Parent folder ID to load
            file_fid: File ID to highlight (optional)
            auto_play: Whether to auto-play the file (default: False)
        """
        # Store file_fid and auto_play for later use
        self._restore_file_fid = file_fid
        self._restore_auto_play = auto_play

        # Select the account
        accounts = self._db.get_cloud_accounts()
        target_account = None

        for account in accounts:
            if account.id == account_id:
                target_account = account
                break

        if not target_account:
            print(f"[DEBUG] Account {account_id} not found for state restoration")
            return False

        # Set current account
        self._current_account = target_account
        self._current_parent_id = file_path

        # Update UI to show selected account
        for i in range(self._account_list.count()):
            item = self._account_list.item(i)
            account = item.data(Qt.UserRole)
            if account.id == account_id:
                self._account_list.setCurrentItem(item)
                break

        # Update account title
        self._account_title.setText(target_account.account_name)

        # Load files for the folder
        self._load_files()

        # If file_fid is provided, try to select/highlight and optionally play the file
        if file_fid and hasattr(self, '_file_table'):
            # Use QTimer to wait for table to populate, then select/play the file
            QTimer.singleShot(500, lambda: self._select_and_play_file_by_fid(file_fid, auto_play))

        return True

    def _select_and_play_file_by_fid(self, file_fid: str, auto_play: bool = False):
        """Select and optionally play a file in the table by its file ID."""
        if not hasattr(self, '_file_table'):
            return

        for row in range(self._file_table.rowCount()):
            item = self._file_table.item(row, 0)
            if item and item.data(Qt.UserRole):
                cloud_file = item.data(Qt.UserRole)
                if hasattr(cloud_file, 'file_id') and cloud_file.file_id == file_fid:
                    # Select the file
                    self._file_table.selectRow(row)
                    self._file_table.scrollToItem(item)

                    # Auto-play the file if requested and it's an audio file
                    if auto_play and cloud_file.file_type == 'audio':
                        print(f"[DEBUG] Auto-playing restored cloud file: {cloud_file.name}")
                        # Use a small delay to ensure UI is ready
                        QTimer.singleShot(300, lambda: self._play_audio_file(cloud_file))
                    break

    def _select_file_by_fid(self, file_fid: str):
        """Select a file in the table by its file ID (without playing)."""
        if not hasattr(self, '_file_table'):
            return

        for row in range(self._file_table.rowCount()):
            item = self._file_table.item(row, 0)
            if item and item.data(Qt.UserRole):
                cloud_file = item.data(Qt.UserRole)
                if hasattr(cloud_file, 'file_id') and cloud_file.file_id == file_fid:
                    self._file_table.selectRow(row)
                    self._file_table.scrollToItem(item)
                    break


class CloudFileDownloadThread(QThread):
    """Thread for downloading cloud files."""

    finished = Signal(str)  # Emits local file path
    token_updated = Signal(str)  # Emits updated access token
    file_exists = Signal(str)  # Emits local file path when file already exists

    def __init__(
        self,
        access_token: str,
        file: CloudFile,
        file_index: int = 0,
        audio_files: list = None,
        config_manager=None,
        parent=None,
    ):
        super().__init__(parent)
        self._access_token = access_token
        self._file = file
        self._file_index = file_index
        self._audio_files = audio_files or []
        self._config_manager = config_manager
        print(
            f"[DEBUG] CloudFileDownloadThread created for file: {file.name} (ID: {file.file_id}), index: {file_index}"
        )

    def run(self):
        """Download file in background thread."""
        import os
        from pathlib import Path

        # Get download directory from config
        if self._config_manager:
            download_dir = self._config_manager.get_cloud_download_dir()
        else:
            download_dir = "data/cloud_downloads"

        # Create download directory if it doesn't exist
        download_path = Path(download_dir)
        download_path.mkdir(parents=True, exist_ok=True)

        # Use original filename
        from utils.helpers import sanitize_filename
        safe_filename = sanitize_filename(self._file.name)
        local_file_path = download_path / safe_filename

        # Check if file already exists and has correct size
        if local_file_path.exists():
            file_size = local_file_path.stat().st_size
            expected_size = self._file.size if self._file.size else 0

            # If we have expected size, verify it matches
            if expected_size > 0:
                # Allow 1% tolerance for file size differences (metadata, etc.)
                size_diff = abs(file_size - expected_size)
                tolerance = expected_size * 0.01  # 1% tolerance

                if size_diff <= tolerance:
                    # File size matches, use existing file
                    print(f"[DEBUG] File already exists with correct size: {local_file_path} ({file_size} bytes)")
                    self.file_exists.emit(str(local_file_path))
                    return
                else:
                    # File size mismatch, need to re-download
                    print(f"[DEBUG] File exists but size mismatch: expected ~{expected_size}, got {file_size}. Will re-download.")
            else:
                # No size info available, use existing file
                print(f"[DEBUG] File exists (no size verification): {local_file_path} ({file_size} bytes)")
                self.file_exists.emit(str(local_file_path))
                return

        # Get download URL
        result = QuarkDriveService.get_download_url(
            self._access_token, self._file.file_id
        )

        # Handle tuple return value
        if isinstance(result, tuple):
            url, updated_token = result
        else:
            url, updated_token = result, None

        # Emit token update signal if changed
        if updated_token:
            self.token_updated.emit(updated_token)

        if url:
            # If file exists and size mismatch, delete it first
            if local_file_path.exists():
                expected_size = self._file.size if self._file.size else 0
                if expected_size > 0:
                    actual_size = local_file_path.stat().st_size
                    size_diff = abs(actual_size - expected_size)
                    tolerance = expected_size * 0.01

                    if size_diff > tolerance:
                        print(f"[DEBUG] Deleting old file with wrong size: {local_file_path}")
                        local_file_path.unlink()

            # Download to persistent location
            success = QuarkDriveService.download_file(
                url, str(local_file_path), self._access_token
            )

            if success:
                # Verify downloaded file size
                if local_file_path.exists():
                    downloaded_size = local_file_path.stat().st_size
                    expected_size = self._file.size if self._file.size else 0

                    if expected_size > 0:
                        size_diff = abs(downloaded_size - expected_size)
                        tolerance = expected_size * 0.01  # 1% tolerance

                        if size_diff <= tolerance:
                            print(f"[DEBUG] File downloaded and verified: {local_file_path} ({downloaded_size} bytes)")
                            self.finished.emit(str(local_file_path))
                            return
                        else:
                            print(f"[DEBUG] Downloaded file size mismatch: expected ~{expected_size}, got {downloaded_size}")
                            # Delete incomplete file
                            local_file_path.unlink()
                            self.finished.emit("")
                    else:
                        # No size info, assume download was successful
                        print(f"[DEBUG] File downloaded (no size verification): {local_file_path} ({downloaded_size} bytes)")
                        self.finished.emit(str(local_file_path))
                        return
                else:
                    print(f"[DEBUG] Download succeeded but file not found: {local_file_path}")
                    self.finished.emit("")
            else:
                print(f"[DEBUG] Download failed for file: {self._file.name}")
                self.finished.emit("")
        else:
            print(f"[DEBUG] Failed to get download URL for file: {self._file.name}")
            print(f"[DEBUG] File ID: {self._file.file_id}")
            print(
                f"[DEBUG] Token length: {len(self._access_token) if self._access_token else 0}"
            )
            self.finished.emit("")
