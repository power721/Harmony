"""
Cloud drive view for browsing and playing cloud files.
"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QTableWidget, QTableWidgetItem,
                               QHeaderView, QStackedWidget, QMessageBox, QMenu,
                               QAbstractItemView, QListWidget, QListWidgetItem,
                               QSplitter, QApplication)
from PySide6.QtCore import Qt, Signal, QThread, QTimer
from PySide6.QtGui import QCursor, QColor, QBrush
from typing import List, Optional
import tempfile
import os
from database.models import CloudAccount, CloudFile
from services.quark_drive_service import QuarkDriveService
from ui.cloud_login_dialog import CloudLoginDialog
from utils import t


class CloudDriveView(QWidget):
    """View for browsing and playing cloud drive files"""

    track_double_clicked = Signal(str)  # Signal for playing track (temp file path)
    play_cloud_files = Signal(str, int, list)  # Signal for playing multiple cloud files (temp_path, index, cloud_files)

    def __init__(self, db_manager, player, parent=None):
        super().__init__(parent)
        self._db = db_manager
        self._player = player
        self._current_account: Optional[CloudAccount] = None
        self._current_parent_id = '0'  # Root folder
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
        self._account_list.customContextMenuRequested.connect(self._show_account_context_menu)
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
        self._file_table.setColumnCount(3)
        self._file_table.setHorizontalHeaderLabels([t("title"), t("type"), t("size")])

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
        accounts = self._db.get_cloud_accounts(provider='quark')
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
            self._current_parent_id = '0'  # Reset to root
            self._navigation_history.clear()
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
            provider='quark',
            account_name=account_info.get('account_email', 'Quark Account'),
            account_email=account_info.get('account_email', ''),
            access_token=account_info.get('access_token', '')
        )

        # Reload accounts
        accounts = self._db.get_cloud_accounts(provider='quark')
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
            self._current_account.access_token,
            self._current_parent_id
        )

        # Handle tuple return value
        if isinstance(result, tuple):
            files, updated_token = result
        else:
            files, updated_token = result, None

        # Update token if changed
        if updated_token:
            print(f"[DEBUG] Updating account token with new __puus cookie")
            self._db.update_cloud_account_token(self._current_account.id, updated_token)
            self._current_account.access_token = updated_token

        # Cache files in database
        self._db.cache_cloud_files(self._current_account.id, files)

        # Save audio files for playlist playback
        self._current_audio_files = [f for f in files if f.file_type == 'audio']
        print(f"[DEBUG] Found {len(self._current_audio_files)} audio files in current folder")

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

                if file.file_type == 'folder':
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

        finally:
            self._file_table.setUpdatesEnabled(True)

    def _get_file_type_label(self, file_type: str) -> str:
        """Get display label for file type."""
        labels = {
            'folder': t("folder"),
            'audio': t("audio"),
            'other': t("file")
        }
        return labels.get(file_type, t("file"))

    def _on_item_double_clicked(self, item: QTableWidgetItem):
        """Handle double-click on item."""
        file = item.data(Qt.UserRole)
        if not file:
            return

        if file.file_type == 'folder':
            # Navigate into folder
            self._navigate_to_folder(file.file_id, file.name)
        elif file.file_type == 'audio':
            # Play audio file
            self._play_audio_file(file)

    def _navigate_to_folder(self, folder_id: str, folder_name: str):
        """Navigate to a folder."""
        self._navigation_history.append((self._current_parent_id, self._path_label.text()))
        self._current_parent_id = folder_id

        # Update path label
        current_path = self._path_label.text()
        if current_path == "/":
            new_path = f"/{folder_name}"
        else:
            new_path = f"{current_path}/{folder_name}"
        self._path_label.setText(new_path)

        self._back_btn.setEnabled(True)
        self._load_files()

    def _navigate_back(self):
        """Navigate to previous folder."""
        if self._navigation_history:
            parent_id, path = self._navigation_history.pop()
            self._current_parent_id = parent_id
            self._path_label.setText(path)

            if not self._navigation_history:
                self._back_btn.setEnabled(False)

            self._load_files()

    def _play_audio_file(self, file: CloudFile):
        """Play an audio file from cloud."""
        print(f"[DEBUG] User requested to play file: {file.name} (ID: {file.file_id})")
        print(f"[DEBUG] Current account: {self._current_account.account_name if self._current_account else 'None'}")

        # Find index of this file in current folder's audio list
        try:
            file_index = next(i for i, f in enumerate(self._current_audio_files) if f.file_id == file.file_id)
        except StopIteration:
            file_index = 0

        print(f"[DEBUG] File index in audio list: {file_index}/{len(self._current_audio_files)}")

        self._status_label.setText(f"{t('downloading')} {file.name}...")

        # Create download thread with context info
        download_thread = CloudFileDownloadThread(
            self._current_account.access_token,
            file,
            file_index,
            self._current_audio_files,
            self
        )
        download_thread.finished.connect(lambda path: self._on_file_downloaded(path, file_index, self._current_audio_files))
        download_thread.token_updated.connect(self._on_token_updated)
        download_thread.start()

    def _on_token_updated(self, updated_token: str):
        """Handle updated access token from API calls."""
        if self._current_account and updated_token:
            print(f"[DEBUG] Updating account token with __puus cookie")
            self._db.update_cloud_account_token(self._current_account.id, updated_token)
            self._current_account.access_token = updated_token

    def _on_file_downloaded(self, temp_path: str, file_index: int, audio_files: list):
        """Handle completed file download."""
        print(f"[DEBUG] Download completed for file at index {file_index}")
        print(f"[DEBUG] Temp file path: {temp_path}")
        print(f"[DEBUG] Total audio files in playlist: {len(audio_files)}")

        if temp_path:
            import os
            if os.path.exists(temp_path):
                file_size = os.path.getsize(temp_path)
                print(f"[DEBUG] Downloaded file size: {file_size} bytes ({file_size/(1024*1024):.2f} MB)")

                # Get file name from audio_files list
                if file_index < len(audio_files):
                    file_name = audio_files[file_index].name
                    self._status_label.setText(f"{t('playing')} {file_name}")
                else:
                    self._status_label.setText(t("playing"))

                # Emit signal with playlist info
                self.play_cloud_files.emit(temp_path, file_index, audio_files)
            else:
                print(f"[DEBUG] ERROR: Temp file does not exist: {temp_path}")
                self._status_label.setText(t("download_failed"))
        else:
            print(f"[DEBUG] ERROR: Download returned empty temp path")
            self._status_label.setText(t("download_failed"))

    def _show_context_menu(self, pos):
        """Show context menu for file."""
        item = self._file_table.itemAt(pos)
        if not item:
            return

        file = item.data(Qt.UserRole)
        if not file or file.file_type != 'audio':
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

        play_action = menu.addAction(t("play"))
        play_action.triggered.connect(lambda: self._play_audio_file(file))

        menu.addSeparator()

        queue_action = menu.addAction(t("add_to_queue"))
        queue_action.triggered.connect(lambda: self._add_to_queue(file))

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
            account.access_token,
            account.account_email
        )

        # Handle tuple return value
        if isinstance(result, tuple):
            account_info, updated_token = result
        else:
            account_info, updated_token = result, None

        # Update token if changed
        if updated_token:
            print(f"[DEBUG] Updating account token with __puus cookie")
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
            QMessageBox.warning(
                self,
                t("error"),
                t("failed_to_get_account_info")
            )

    def _show_account_info_dialog(self, account: CloudAccount, account_info: dict):
        """Show account information dialog."""
        dialog = QMessageBox(self)
        dialog.setWindowTitle(t("account_info"))

        # Format timestamps
        created_at_str = self._format_timestamp(account_info.get('created_at'))
        exp_at_str = self._format_timestamp(account_info.get('exp_at'))

        # Format capacity
        total_capacity_str = self._format_capacity(account_info.get('total_capacity', 0))
        used_capacity_str = self._format_capacity(account_info.get('use_capacity', 0))

        # Calculate usage percentage
        total_cap = account_info.get('total_capacity', 0)
        used_cap = account_info.get('use_capacity', 0)
        if total_cap > 0:
            usage_percent = (used_cap / total_cap) * 100
            usage_str = f"{usage_percent:.1f}%"
        else:
            usage_str = "N/A"

        # Build info text
        info_text = f"""
{t('account_name')}: {account_info.get('nickname', account.account_name)}
{t('member_type')}: {account_info.get('member_type', 'unknown')}
{t('account_created')}: {created_at_str}
{t('vip_expires')}: {exp_at_str}
{t('storage_used')}: {used_capacity_str} / {total_capacity_str} ({usage_str})
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
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            print(f"[DEBUG] Error formatting timestamp: {e}")
            return "N/A"

    def _format_capacity(self, bytes_size: int) -> str:
        """Format bytes to readable size string (TB/GB/MB)."""
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
            print(f"[DEBUG] Error formatting capacity: {e}")
            return "N/A"

    def _delete_account(self, account: CloudAccount):
        """Delete a cloud account."""
        reply = QMessageBox.question(
            self,
            t("delete_account"),
            f"{t('delete_account_confirm')}\n\n{account.account_name}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self._db.delete_cloud_account(account.id)

            # Reload accounts
            accounts = self._db.get_cloud_accounts(provider='quark')
            self._populate_account_list(accounts)

            # Reset current account if needed
            if self._current_account and self._current_account.id == account.id:
                self._current_account = None
                self._update_file_view()

    def _add_to_queue(self, file: CloudFile):
        """Add file to play queue."""
        # TODO: Implement queue addition
        pass

    def refresh_ui(self):
        """Refresh UI texts after language change."""
        # Update account list title
        self._account_list_title.setText("☁️ " + t("accounts"))

        # Update button texts
        self._add_account_btn.setText(t("add_account"))
        if hasattr(self, '_back_btn'):
            self._back_btn.setText("← " + t("back"))

        # Update table headers
        if hasattr(self, '_file_table'):
            self._file_table.setHorizontalHeaderLabels([t("title"), t("type"), t("size")])

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


class CloudFileDownloadThread(QThread):
    """Thread for downloading cloud files."""

    finished = Signal(str)  # Emits temp file path
    token_updated = Signal(str)  # Emits updated access token

    def __init__(self, access_token: str, file: CloudFile, file_index: int = 0, audio_files: list = None, parent=None):
        super().__init__(parent)
        self._access_token = access_token
        self._file = file
        self._file_index = file_index
        self._audio_files = audio_files or []
        print(f"[DEBUG] CloudFileDownloadThread created for file: {file.name} (ID: {file.file_id}), index: {file_index}")

    def run(self):
        """Download file in background thread."""
        print(f"[DEBUG] Starting download thread for file: {self._file.name}")

        # Get download URL
        print(f"[DEBUG] Fetching download URL...")
        result = QuarkDriveService.get_download_url(
            self._access_token,
            self._file.file_id
        )

        # Handle tuple return value
        if isinstance(result, tuple):
            url, updated_token = result
        else:
            url, updated_token = result, None

        # Emit token update signal if changed
        if updated_token:
            print(f"[DEBUG] Download URL call returned updated token")
            self.token_updated.emit(updated_token)

        if url:
            print(f"[DEBUG] Download URL obtained, starting file download...")
            # Download to temp file
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
                temp_path = f.name

            print(f"[DEBUG] Temporary file created: {temp_path}")

            success = QuarkDriveService.download_file(
                url,
                temp_path,
                self._access_token
            )

            print(f"[DEBUG] Download result: {'SUCCESS' if success else 'FAILED'}")

            if success:
                print(f"[DEBUG] Emitting finished signal with temp path: {temp_path}")
                self.finished.emit(temp_path)
                return
            else:
                print(f"[DEBUG] Download failed, emitting empty signal")
                self.finished.emit("")
        else:
            print(f"[DEBUG] Failed to get download URL for file: {self._file.name}")
            print(f"[DEBUG] File ID: {self._file.file_id}")
            print(f"[DEBUG] Token length: {len(self._access_token) if self._access_token else 0}")
            self.finished.emit("")
