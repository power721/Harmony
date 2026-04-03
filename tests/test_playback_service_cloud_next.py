"""
Test for cloud track auto-next bug when queue is restored.

This test demonstrates the bug where automatic next track doesn't work
when the queue is restored with cloud files because _cloud_files_by_id
is not populated during queue restoration.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from domain.track import TrackSource
from domain.playlist_item import PlaylistItem
from domain.cloud import CloudFile, CloudAccount
from services.playback.playback_service import PlaybackService


class TestCloudTrackAutoNextBug:
    """Test cloud track auto-next when queue is restored."""

    @pytest.fixture
    def mock_deps(self):
        """Create mock dependencies."""
        mock_config = Mock()
        mock_config.get_play_mode.return_value = 0  # SEQUENTIAL
        mock_config.get_volume.return_value = 50
        mock_config.get_playback_source.return_value = "local"
        mock_config.get_audio_effects.return_value = {}
        mock_config.get_audio_engine.return_value = "mpv"
        mock_config.get_cloud_download_dir.return_value = "/tmp/downloads"
        mock_config.get_language.return_value = "en"
        mock_config.get.side_effect = lambda key, default=None: {
            "queue_current_index": 0,
            "queue_play_mode": 0,
            "queue_current_track_id": 0,
            "queue_current_cloud_file_id": "",
            "queue_current_local_path": "",
        }.get(key, default)

        return {
            'db_manager': Mock(),
            'config_manager': mock_config,
            'cover_service': Mock(),
            'online_download_service': Mock(),
            'event_bus': Mock(),
            'track_repo': Mock(),
            'favorite_repo': Mock(),
            'queue_repo': Mock(),
            'cloud_repo': Mock(),
            'history_repo': Mock(),
            'album_repo': Mock(),
            'artist_repo': Mock(),
        }

    @pytest.fixture
    def cloud_account(self):
        """Create a test cloud account."""
        account = CloudAccount(
            id=1,
            provider="quark",
            account_email="test@example.com",
            access_token="test_token"
        )
        return account

    @pytest.fixture
    def cloud_files(self):
        """Create test cloud files."""
        files = [
            CloudFile(
                file_id="file1",
                account_id=1,
                name="song1.mp3",
                size=1024 * 1024
            ),
            CloudFile(
                file_id="file2",
                account_id=1,
                name="song2.mp3",
                size=1024 * 1024
            ),
        ]
        return files

    def test_cloud_files_by_id_not_populated_on_queue_restore(
        self, mock_deps, cloud_account, cloud_files
    ):
        """
        Test that _cloud_files_by_id is empty after queue restore.

        This is the root cause of the bug where auto-next doesn't work
        for cloud tracks when queue is restored.
        """
        # Setup mocks
        mock_queue_repo = mock_deps['queue_repo']
        mock_cloud_repo = mock_deps['cloud_repo']
        mock_config = mock_deps['config_manager']
        mock_track_repo = mock_deps['track_repo']

        # Mock track repository methods
        mock_track_repo.get_by_cloud_file_id.return_value = None  # No existing track
        # Mock the batch fetch to return the cloud files
        mock_cloud_repo.get_files_by_file_ids.return_value = cloud_files

        # Create queue items with cloud files
        from repositories.queue_repository import PlayQueueItem

        queue_items = [
            PlayQueueItem(
                position=0,
                track_id=0,
                cloud_file_id="file1",
                cloud_account_id=1,
                title="Song 1",
                artist="Artist 1",
                album="Album 1",
                duration=180.0,
                source=TrackSource.QUARK.value,
                local_path=""
            ),
            PlayQueueItem(
                position=1,
                track_id=0,
                cloud_file_id="file2",
                cloud_account_id=1,
                title="Song 2",
                artist="Artist 2",
                album="Album 2",
                duration=200.0,
                source=TrackSource.QUARK.value,
                local_path=""
            ),
        ]

        mock_queue_repo.load.return_value = queue_items
        mock_cloud_repo.get_account_by_id.return_value = cloud_account
        mock_cloud_repo.get_file_by_file_id.return_value = cloud_files[1]  # Return second file

        # Create playback service
        service = PlaybackService(**mock_deps)

        # Restore queue (simulating app startup)
        result = service.restore_queue()

        # Verify queue was restored
        assert result is True
        assert service._cloud_account is not None
        assert service._cloud_account.id == 1

        # **FIX**: _cloud_files_by_id should now be populated!
        assert len(service._cloud_files_by_id) == 2, (
            "FIXED: _cloud_files_by_id should be populated after queue restore. "
            "This ensures play_next() can find cloud files for download."
        )
        assert "file1" in service._cloud_files_by_id
        assert "file2" in service._cloud_files_by_id

    def test_download_cloud_track_works_with_repo_fallback(
        self, mock_deps, cloud_account, cloud_files
    ):
        """
        Test that _download_cloud_track works even when _cloud_files_by_id is empty
        because of repo fallback.

        This shows that while the bug doesn't completely break downloads, it's
        inefficient because every download requires a repo lookup instead of
        using the in-memory cache.
        """
        # Setup mocks
        mock_cloud_repo = mock_deps['cloud_repo']
        mock_config = mock_deps['config_manager']

        mock_cloud_repo.get_account_by_id.return_value = cloud_account
        mock_cloud_repo.get_file_by_file_id.return_value = cloud_files[0]

        # Create playback service
        service = PlaybackService(**mock_deps)

        # Simulate queue restore scenario where _cloud_files_by_id is empty
        service._cloud_account = cloud_account
        # Intentionally leave _cloud_files_by_id empty (the bug)

        # Create a playlist item that needs download
        item = PlaylistItem(
            source=TrackSource.QUARK,
            cloud_file_id="file1",
            cloud_account_id=1,
            title="Song 1",
            needs_download=True
        )

        # Try to download - this should work because of repo fallback
        with patch('services.cloud.download_service.CloudDownloadService') as mock_download_service:
            mock_service_instance = Mock()
            mock_download_service.instance.return_value = mock_service_instance

            # Call _download_cloud_track
            service._download_cloud_track(item)

            # Verify that download WAS called because of repo fallback
            # (This works but is inefficient - requires repo lookup every time)
            mock_service_instance.download_file.assert_called_once()
            assert mock_service_instance.download_file.call_count == 1

    def test_cloud_files_by_id_populated_in_play_cloud_playlist(
        self, mock_deps, cloud_account, cloud_files
    ):
        """
        Test that _cloud_files_by_id IS populated when using play_cloud_playlist.

        This shows the contrast - play_cloud_playlist works correctly,
        but restore_queue does not.
        """
        mock_config = mock_deps['config_manager']
        mock_config.get_cloud_download_dir.return_value = "/tmp/downloads"

        # Create playback service
        service = PlaybackService(**mock_deps)

        # Play cloud playlist
        service.play_cloud_playlist(
            cloud_files=cloud_files,
            start_index=0,
            account=cloud_account,
            first_file_path="",
            start_position=0.0
        )

        # Verify _cloud_files_by_id IS populated
        assert len(service._cloud_files_by_id) == 2
        assert "file1" in service._cloud_files_by_id
        assert "file2" in service._cloud_files_by_id
