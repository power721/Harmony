"""
Tests for cloud view components.
"""

import pytest
import tempfile
from unittest.mock import Mock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel

from domain.cloud import CloudFile, CloudAccount
from ui.dialogs.message_dialog import Yes, No
from ui.views.cloud.cloud_drive_view import CloudDriveView
from ui.views.cloud.file_table import CloudFileTable
from ui.views.cloud.context_menu import CloudFileContextMenu, CloudAccountContextMenu
from system.theme import ThemeManager


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture(autouse=True)
def reset_theme_singleton():
    """Reset ThemeManager singleton before and after each test."""
    ThemeManager._instance = None
    yield
    ThemeManager._instance = None


@pytest.fixture
def mock_config():
    """Mock config manager for ThemeManager."""
    config = Mock()
    config.get.return_value = 'dark'
    return config


class TestCloudFileTable:
    """Tests for CloudFileTable widget."""

    def test_init(self, qapp, mock_config):
        """Test table initialization."""
        ThemeManager.instance(mock_config)
        table = CloudFileTable()
        assert table is not None
        assert table._table.columnCount() == 5

    def test_populate_empty(self, qapp, mock_config):
        """Test populating with empty list."""
        ThemeManager.instance(mock_config)
        table = CloudFileTable()
        table.populate([])
        assert table._table.rowCount() == 0

    def test_populate_with_files(self, qapp, mock_config):
        """Test populating with files."""
        ThemeManager.instance(mock_config)
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

    def test_update_playing_status(self, qapp, mock_config):
        """Test updating playing status."""
        ThemeManager.instance(mock_config)
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

    def test_update_file_local_path(self, qapp, mock_config):
        """Test updating local path."""
        ThemeManager.instance(mock_config)
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

    def test_get_current_files(self, qapp, mock_config):
        """Test getting current files."""
        ThemeManager.instance(mock_config)
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

    def test_clear(self, qapp, mock_config):
        """Test clearing the table."""
        ThemeManager.instance(mock_config)
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
        assert hasattr(menu, 'delete_from_cloud_requested')


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


class TestCloudDriveView:
    """Tests for CloudDriveView share-search state handling."""

    def test_batch_download_starts_up_to_parallel_limit(self, qapp, mock_config):
        """Batch download should immediately fill the parallel worker window."""
        ThemeManager.instance(mock_config)
        view = CloudDriveView.__new__(CloudDriveView)
        files = [
            CloudFile(id=i, account_id=1, file_id=f"file{i}", parent_id="0", name=f"Song {i}.mp3", file_type="audio")
            for i in range(4)
        ]
        view._current_account = CloudAccount(id=1, provider="quark", account_name="acc", access_token="token")
        view._file_table = Mock()
        view._file_table.get_selected_audio_files.return_value = files
        view._batch_download_btn = Mock()
        view._cancel_downloads_btn = Mock()
        view._status_label = Mock()
        view._cloud_file_service = Mock()
        view._current_audio_files = files
        view._config_manager = mock_config
        view._attach_download_thread_cleanup = Mock()
        view._on_token_updated = Mock()
        view._active_batch_download_threads = {}
        view._max_parallel_batch_downloads = 3
        started = []

        class _Signal:
            def connect(self, _callback):
                return None

        class _FakeThread:
            def __init__(self, _token, file, *_args):
                self.file = file
                self.finished = _Signal()
                self.file_exists = _Signal()
                self.token_updated = _Signal()

            def start(self):
                started.append(self.file.file_id)

        with patch("ui.views.cloud.cloud_drive_view.CloudFileDownloadThread", _FakeThread):
            CloudDriveView._download_selected_files(view)

        assert started == ["file0", "file1", "file2"]
        assert set(view._active_batch_download_threads.keys()) == {"file0", "file1", "file2"}
        assert len(view._download_queue) == 1

    def test_batch_download_completion_starts_next_waiting_file(self, qapp, mock_config):
        """When one batch worker finishes, the next queued file should start immediately."""
        ThemeManager.instance(mock_config)
        view = CloudDriveView.__new__(CloudDriveView)
        files = [
            CloudFile(id=i, account_id=1, file_id=f"file{i}", parent_id="0", name=f"Song {i}.mp3", file_type="audio")
            for i in range(4)
        ]
        view._current_account = CloudAccount(id=1, provider="quark", account_name="acc", access_token="token")
        view._file_table = Mock()
        view._status_label = Mock()
        view._cloud_file_service = Mock()
        view._current_audio_files = files
        view._config_manager = mock_config
        view._attach_download_thread_cleanup = Mock()
        view._on_token_updated = Mock()
        view._batch_total = 4
        view._batch_completed = 0
        view._download_queue = [files[3]]
        view._is_downloading = True
        view._active_batch_download_threads = {
            "file0": object(),
            "file1": object(),
            "file2": object(),
        }
        view._max_parallel_batch_downloads = 3
        view._current_download_thread = object()
        started = []

        class _Signal:
            def connect(self, _callback):
                return None

        class _FakeThread:
            def __init__(self, _token, file, *_args):
                self.file = file
                self.finished = _Signal()
                self.file_exists = _Signal()
                self.token_updated = _Signal()

            def start(self):
                started.append(self.file.file_id)

        with tempfile.NamedTemporaryFile() as tmp_file, \
                patch("ui.views.cloud.cloud_drive_view.CloudFileDownloadThread", _FakeThread), \
                patch("ui.views.cloud.cloud_drive_view.EventBus.instance", return_value=Mock(download_completed=Mock())), \
                patch("os.path.exists", return_value=True):
            CloudDriveView._on_batch_download_finished(view, tmp_file.name, files[0])

        assert started == ["file3"]
        assert "file0" not in view._active_batch_download_threads
        assert "file3" in view._active_batch_download_threads
        assert view._batch_completed == 1

    def test_batch_download_button_disabled_without_selection(self, qapp, mock_config):
        """Batch download button should be disabled when no file is selected."""
        ThemeManager.instance(mock_config)
        view = CloudDriveView(
            cloud_account_service=Mock(),
            cloud_file_service=Mock(),
            library_service=Mock(),
            player=Mock(),
            config_manager=mock_config,
            cover_service=Mock(),
        )

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
        view._current_audio_files = files
        view._batch_download_btn.setVisible(True)
        view._file_table.populate(files)

        qapp.processEvents()
        assert view._batch_download_btn.isEnabled() is False

        view._file_table._table.selectRow(0)
        qapp.processEvents()
        assert view._batch_download_btn.isEnabled() is True

        view._file_table._table.clearSelection()
        qapp.processEvents()
        assert view._batch_download_btn.isEnabled() is False

    def test_clear_share_search_results_restores_previous_path(self, qapp, mock_config):
        """Clearing share search should restore pre-share folder path/state."""
        ThemeManager.instance(mock_config)
        view = CloudDriveView(
            cloud_account_service=Mock(),
            cloud_file_service=Mock(),
            library_service=Mock(),
            player=Mock(),
            config_manager=mock_config,
            cover_service=Mock(),
        )

        view._current_account = CloudAccount(
            id=1,
            provider="quark",
            account_name="quark-test",
            access_token="token",
        )

        view._pre_share_browse_state = {
            "parent_id": "fid-music-pop",
            "path_label": "/Music/Pop",
            "fid_path": ["fid-music", "fid-music-pop"],
            "navigation_history": [("0", "/"), ("fid-music", "/Music")],
            "back_enabled": True,
        }

        view._share_mode = True
        view._share_results_list.addItem("dummy-result")
        view._current_parent_id = "share-folder-fid"
        view._path_label.setText("/share/album")
        view._fid_path = ["share-folder-fid"]
        view._navigation_history = []
        view._back_btn.setEnabled(False)

        with patch.object(view, "_update_file_view") as mock_update:
            view._clear_share_search_results()

        assert view._current_parent_id == "fid-music-pop"
        assert view._path_label.text() == "/Music/Pop"
        assert view._fid_path == ["fid-music", "fid-music-pop"]
        assert view._navigation_history == [("0", "/"), ("fid-music", "/Music")]
        assert view._back_btn.isEnabled() is True
        assert view._pre_share_browse_state is None
        mock_update.assert_called_once()

    def test_breadcrumb_click_jumps_to_ancestor_for_quark(self, qapp, mock_config):
        """Breadcrumb click should jump to selected ancestor path in Quark mode."""
        ThemeManager.instance(mock_config)
        view = CloudDriveView(
            cloud_account_service=Mock(),
            cloud_file_service=Mock(),
            library_service=Mock(),
            player=Mock(),
            config_manager=mock_config,
            cover_service=Mock(),
        )
        view._current_account = CloudAccount(
            id=1,
            provider="quark",
            account_name="quark-test",
            access_token="token",
        )
        view._share_mode = False
        view._path_label.setText("/Music/Pop")
        view._fid_path = ["fid-music", "fid-pop"]
        view._current_parent_id = "fid-pop"
        view._navigation_history = [("0", "/"), ("fid-music", "/Music")]
        view._back_btn.setEnabled(True)

        with patch.object(view, "_load_files") as mock_load_files:
            view._on_breadcrumb_clicked("/Music", 1)

        assert view._current_parent_id == "fid-music"
        assert view._fid_path == ["fid-music"]
        assert view._path_label.text() == "/Music"
        assert view._navigation_history == [("0", "/")]
        assert view._back_btn.isEnabled() is True
        mock_load_files.assert_called_once()

    def test_breadcrumb_click_jumps_to_ancestor_for_share(self, qapp, mock_config):
        """Breadcrumb click should jump to selected ancestor in share mode."""
        ThemeManager.instance(mock_config)
        view = CloudDriveView(
            cloud_account_service=Mock(),
            cloud_file_service=Mock(),
            library_service=Mock(),
            player=Mock(),
            config_manager=mock_config,
            cover_service=Mock(),
        )
        view._current_account = CloudAccount(
            id=1,
            provider="quark",
            account_name="quark-test",
            access_token="token",
        )
        view._share_mode = True
        view._share_root_title = "ShareRoot"
        view._share_history = [("0", "/ShareRoot"), ("fid-a", "/ShareRoot/A")]
        view._path_label.setText("/ShareRoot/A/B")
        view._back_btn.setEnabled(True)

        with patch.object(view, "_load_share_folder") as mock_load_share_folder:
            view._on_breadcrumb_clicked("/ShareRoot/A", 2)

        assert view._share_history == [("0", "/ShareRoot")]
        mock_load_share_folder.assert_called_once_with("fid-a", "/ShareRoot/A")

    def test_breadcrumb_renders_theme_text_color(self, qapp, mock_config):
        """Breadcrumb rich text should use theme main text color."""
        ThemeManager.instance(mock_config)
        view = CloudDriveView(
            cloud_account_service=Mock(),
            cloud_file_service=Mock(),
            library_service=Mock(),
            player=Mock(),
            config_manager=mock_config,
            cover_service=Mock(),
        )
        view._path_label.setText("/Music/Pop")

        rendered_html = QLabel.text(view._path_label).lower()
        assert "color:#ffffff" in rendered_html

    def test_open_in_cloud_drive_preserves_quark_hierarchy_for_folder(self, qapp, mock_config):
        """Quark open-in-cloud should preserve fid-name hierarchy for selected folder."""
        ThemeManager.instance(mock_config)
        view = CloudDriveView(
            cloud_account_service=Mock(),
            cloud_file_service=Mock(),
            library_service=Mock(),
            player=Mock(),
            config_manager=mock_config,
            cover_service=Mock(),
        )
        view._current_account = CloudAccount(
            id=1,
            provider="quark",
            account_name="quark-test",
            access_token="token",
        )
        view._fid_path = ["fid1", "fid2"]
        view._path_label.setText("/name1/name2")
        folder = CloudFile(
            file_id="fid3",
            parent_id="fid2",
            name="name3",
            file_type="folder",
        )

        with patch("webbrowser.open") as mock_open:
            view._open_in_cloud_drive(folder)

        mock_open.assert_called_once_with(
            "https://pan.quark.cn/list#/list/all/fid1-name1/fid2-name2/fid3-name3"
        )

    def test_delete_cloud_file_calls_quark_delete_and_refresh(self, qapp, mock_config):
        """Delete cloud file should call Quark API and refresh list on success."""
        ThemeManager.instance(mock_config)
        cloud_account_service = Mock()
        view = CloudDriveView(
            cloud_account_service=cloud_account_service,
            cloud_file_service=Mock(),
            library_service=Mock(),
            player=Mock(),
            config_manager=mock_config,
            cover_service=Mock(),
        )
        view._current_account = CloudAccount(
            id=1,
            provider="quark",
            account_name="quark-test",
            access_token="old_token",
        )
        file = CloudFile(
            file_id="fid-to-delete",
            parent_id="0",
            name="song.mp3",
            file_type="audio",
        )

        with patch("ui.views.cloud.cloud_drive_view.MessageDialog.question", return_value=Yes), patch(
            "ui.views.cloud.cloud_drive_view.QuarkDriveService.delete_files",
            return_value=(True, "new_token"),
        ) as mock_delete, patch.object(view, "_load_files") as mock_load_files:
            view._delete_cloud_file(file)

        mock_delete.assert_called_once_with("old_token", "fid-to-delete")
        cloud_account_service.update_token.assert_called_once_with(1, "new_token")
        assert view._current_account.access_token == "new_token"
        mock_load_files.assert_called_once()

    def test_delete_cloud_file_cancelled_by_user(self, qapp, mock_config):
        """Canceling the confirmation dialog should not call delete API."""
        ThemeManager.instance(mock_config)
        view = CloudDriveView(
            cloud_account_service=Mock(),
            cloud_file_service=Mock(),
            library_service=Mock(),
            player=Mock(),
            config_manager=mock_config,
            cover_service=Mock(),
        )
        view._current_account = CloudAccount(
            id=1,
            provider="quark",
            account_name="quark-test",
            access_token="old_token",
        )
        file = CloudFile(
            file_id="fid-to-delete",
            parent_id="0",
            name="song.mp3",
            file_type="audio",
        )

        with patch("ui.views.cloud.cloud_drive_view.MessageDialog.question", return_value=No), patch(
            "ui.views.cloud.cloud_drive_view.QuarkDriveService.delete_files"
        ) as mock_delete:
            view._delete_cloud_file(file)

        mock_delete.assert_not_called()

    def test_delete_cloud_file_calls_baidu_delete_and_refresh(self, qapp, mock_config):
        """Delete cloud file should call Baidu API and refresh list on success."""
        ThemeManager.instance(mock_config)
        view = CloudDriveView(
            cloud_account_service=Mock(),
            cloud_file_service=Mock(),
            library_service=Mock(),
            player=Mock(),
            config_manager=mock_config,
            cover_service=Mock(),
        )
        view._current_account = CloudAccount(
            id=1,
            provider="baidu",
            account_name="baidu-test",
            access_token="baidu_token",
        )
        file = CloudFile(
            file_id="123456",
            parent_id="/music",
            name="song.mp3",
            file_type="audio",
            metadata="/music/song.mp3",
        )

        with patch("ui.views.cloud.cloud_drive_view.MessageDialog.question", return_value=Yes), patch(
            "ui.views.cloud.cloud_drive_view.BaiduDriveService.delete_files",
            return_value=(True, None),
        ) as mock_delete, patch.object(view, "_load_files") as mock_load_files:
            view._delete_cloud_file(file)

        mock_delete.assert_called_once_with("baidu_token", "/music/song.mp3")
        mock_load_files.assert_called_once()

    def test_load_files_clears_cached_folder_when_remote_listing_empty(self, qapp, mock_config):
        """Empty remote folder listings should still refresh cached folder state."""
        ThemeManager.instance(mock_config)
        cloud_file_service = Mock()
        cloud_file_service.get_files.return_value = []
        view = CloudDriveView(
            cloud_account_service=Mock(),
            cloud_file_service=cloud_file_service,
            library_service=Mock(),
            player=Mock(),
            config_manager=mock_config,
            cover_service=Mock(),
        )
        view._current_account = CloudAccount(
            id=1,
            provider="quark",
            account_name="quark-test",
            access_token="token",
        )
        view._current_parent_id = "folder_A"

        with patch(
            "ui.views.cloud.cloud_drive_view.QuarkDriveService.get_file_list",
            return_value=([], None),
        ):
            view._load_files()

        cloud_file_service.cache_files.assert_called_once_with(1, [], parent_id="folder_A")
        cloud_file_service.get_files.assert_called_once_with(1, "folder_A")
        assert view._file_table._table.rowCount() == 0
