"""
Tests for cloud view components.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from domain.cloud import CloudFile, CloudAccount
from ui.views.cloud.file_table import CloudFileTable
from ui.views.cloud.context_menu import CloudFileContextMenu, CloudAccountContextMenu
from ui.views.cloud.dialogs import CloudMediaInfoDialog


# Ensure QApplication exists for widget tests
@pytest.fixture(scope="module")
def qapp():
    """Create QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class TestCloudFileTable:
    """Tests for CloudFileTable widget."""

    def test_init(self, qapp):
        """Test table initialization."""
        table = CloudFileTable()
        assert table is not None
        assert table._table.columnCount() == 5

    def test_populate_empty(self, qapp):
        """Test populating with empty list."""
        table = CloudFileTable()
        table.populate([])
        assert table._table.rowCount() == 0

    def test_populate_with_files(self, qapp):
        """Test populating with files."""
        table = CloudFileTable()

        files = [
            CloudFile(
                id=1,
                account_id=1,
                file_id="file1",
                parent_id="0",
                name="Test Song.mp3",
                file_type="audio",
                size=1024000,
                duration=180.0,
            ),
            CloudFile(
                id=2,
                account_id=1,
                file_id="folder1",
                parent_id="0",
                name="Music Folder",
                file_type="folder",
                size=0,
            ),
        ]

        table.populate(files)

        assert table._table.rowCount() == 2

        # Check first row (audio file)
        name_item = table._table.item(0, 0)
        assert name_item is not None
        file_data = name_item.data(Qt.UserRole)
        assert file_data.file_id == "file1"

        # Check second row (folder)
        folder_item = table._table.item(1, 0)
        assert folder_item is not None
        assert "📁" in folder_item.text()

    def test_update_playing_status(self, qapp):
        """Test updating playing status."""
        table = CloudFileTable()

        files = [
            CloudFile(
                id=1,
                account_id=1,
                file_id="file1",
                parent_id="0",
                name="Test Song.mp3",
                file_type="audio",
                size=1024000,
            ),
        ]

        table.populate(files)
        table.update_playing_status("file1", True)

        # Check that the file has playing indicator
        name_item = table._table.item(0, 0)
        assert "▶️" in name_item.text() or "⏸️" in name_item.text()

    def test_update_file_local_path(self, qapp):
        """Test updating local path."""
        table = CloudFileTable()

        files = [
            CloudFile(
                id=1,
                account_id=1,
                file_id="file1",
                parent_id="0",
                name="Test Song.mp3",
                file_type="audio",
            ),
        ]

        table.populate(files)
        table.update_file_local_path("file1", "/path/to/file.mp3")

        # Check status column shows checkmark
        status_item = table._table.item(0, 4)
        assert status_item.text() == "✓"

    def test_get_current_files(self, qapp):
        """Test getting current files."""
        table = CloudFileTable()

        files = [
            CloudFile(
                id=1,
                account_id=1,
                file_id="file1",
                parent_id="0",
                name="Test.mp3",
                file_type="audio",
            ),
        ]

        table.populate(files)
        current_files = table.get_current_files()

        assert len(current_files) == 1
        assert current_files[0].file_id == "file1"

    def test_clear(self, qapp):
        """Test clearing the table."""
        table = CloudFileTable()

        files = [
            CloudFile(
                id=1,
                account_id=1,
                file_id="file1",
                parent_id="0",
                name="Test.mp3",
                file_type="audio",
            ),
        ]

        table.populate(files)
        table.clear()

        assert table._table.rowCount() == 0


class TestCloudFileContextMenu:
    """Tests for CloudFileContextMenu."""

    def test_init(self, qapp):
        """Test context menu initialization."""
        menu = CloudFileContextMenu()
        assert menu is not None

    def test_signals_exist(self, qapp):
        """Test that all expected signals exist."""
        menu = CloudFileContextMenu()

        assert hasattr(menu, 'play_requested')
        assert hasattr(menu, 'insert_to_queue_requested')
        assert hasattr(menu, 'add_to_queue_requested')
        assert hasattr(menu, 'download_requested')
        assert hasattr(menu, 'edit_media_info_requested')
        assert hasattr(menu, 'download_cover_requested')
        assert hasattr(menu, 'open_file_location_requested')
        assert hasattr(menu, 'open_in_cloud_requested')


class TestCloudAccountContextMenu:
    """Tests for CloudAccountContextMenu."""

    def test_init(self, qapp):
        """Test context menu initialization."""
        menu = CloudAccountContextMenu()
        assert menu is not None

    def test_signals_exist(self, qapp):
        """Test that all expected signals exist."""
        menu = CloudAccountContextMenu()

        assert hasattr(menu, 'get_info_requested')
        assert hasattr(menu, 'change_download_dir_requested')
        assert hasattr(menu, 'update_cookie_requested')
        assert hasattr(menu, 'delete_requested')


class TestCloudMediaInfoDialog:
    """Tests for CloudMediaInfoDialog."""

    def test_init_requires_local_path(self, qapp):
        """Test that dialog requires file with local_path."""
        mock_library_service = Mock()

        file = CloudFile(
            id=1,
            account_id=1,
            file_id="file1",
            parent_id="0",
            name="Test.mp3",
            file_type="audio",
        )

        # Dialog should handle missing local_path gracefully
        # (show_media_info_dialog will show warning instead)
        from ui.views.cloud.dialogs import show_media_info_dialog

        result = show_media_info_dialog(file, mock_library_service, None)
        assert result is False  # Should return False when no local_path


class TestCloudFile:
    """Additional tests for CloudFile domain model."""

    def test_local_path_property(self):
        """Test that local_path can be set and retrieved."""
        file = CloudFile(
            id=1,
            account_id=1,
            file_id="file1",
            parent_id="0",
            name="Test.mp3",
            file_type="audio",
        )

        assert file.local_path is None

        file.local_path = "/path/to/file.mp3"
        assert file.local_path == "/path/to/file.mp3"

    def test_file_type_audio(self):
        """Test audio file type."""
        file = CloudFile(
            id=1,
            account_id=1,
            file_id="file1",
            parent_id="0",
            name="Test.mp3",
            file_type="audio",
        )

        assert file.file_type == "audio"

    def test_file_type_folder(self):
        """Test folder file type."""
        file = CloudFile(
            id=1,
            account_id=1,
            file_id="folder1",
            parent_id="0",
            name="Music",
            file_type="folder",
        )

        assert file.file_type == "folder"


class TestCloudAccount:
    """Additional tests for CloudAccount domain model."""

    def test_provider_quark(self):
        """Test Quark provider."""
        account = CloudAccount(
            id=1,
            provider="quark",
            account_name="Test Account",
            access_token="token123",
        )

        assert account.provider == "quark"

    def test_provider_baidu(self):
        """Test Baidu provider."""
        account = CloudAccount(
            id=1,
            provider="baidu",
            account_name="Baidu Account",
            access_token="cookie123",
        )

        assert account.provider == "baidu"

    def test_last_playing_state(self):
        """Test last playing state fields."""
        account = CloudAccount(
            id=1,
            provider="quark",
            account_name="Test",
            access_token="token",
            last_playing_fid="file123",
            last_position=45.5,
        )

        assert account.last_playing_fid == "file123"
        assert account.last_position == 45.5
