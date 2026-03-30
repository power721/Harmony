"""
Tests for PlaylistItem domain model.
"""

import pytest
from domain.playlist_item import PlaylistItem
from domain.track import Track, TrackSource
from domain.cloud import CloudFile


class TestPlaylistItem:
    """Test PlaylistItem domain model."""

    def test_default_initialization(self):
        """Test playlist item with default values."""
        item = PlaylistItem()
        assert item.source == TrackSource.LOCAL
        assert item.track_id is None
        assert item.cloud_file_id is None
        assert item.cloud_account_id is None
        assert item.local_path == ""
        assert item.title == ""
        assert item.artist == ""
        assert item.album == ""
        assert item.duration == 0.0
        assert item.cover_path is None
        assert item.needs_download is False
        assert item.needs_metadata is True
        assert item.cloud_file_size is None

    def test_from_track(self, sample_track_data):
        """Test creating PlaylistItem from Track."""
        track = Track(**sample_track_data)
        item = PlaylistItem.from_track(track)

        assert item.source == TrackSource.LOCAL
        assert item.track_id == track.id
        assert item.local_path == track.path
        assert item.title == track.title
        assert item.artist == track.artist
        assert item.album == track.album
        assert item.duration == track.duration
        assert item.cover_path == track.cover_path
        assert item.needs_download is False
        assert item.needs_metadata is False

    def test_from_online_track(self):
        """Test creating PlaylistItem from online track (empty path)."""
        track = Track(
            id=1,
            path="",  # Empty path indicates online track
            title="Online Song",
            artist="Online Artist",
            source=TrackSource.QQ,
            cloud_file_id="song_mid_123"
        )
        item = PlaylistItem.from_track(track)

        assert item.source == TrackSource.QQ
        assert item.cloud_file_id == "song_mid_123"
        assert item.needs_download is True

    def test_from_cloud_file_without_local_path(self, sample_cloud_file_data):
        """Test creating PlaylistItem from CloudFile without local path."""
        cloud_file = CloudFile(**sample_cloud_file_data)
        item = PlaylistItem.from_cloud_file(cloud_file, account_id=1)

        assert item.source == TrackSource.QUARK
        assert item.cloud_file_id == cloud_file.file_id
        assert item.cloud_account_id == 1
        assert item.title == cloud_file.name
        assert item.duration == cloud_file.duration
        assert item.needs_download is True  # No local path
        assert item.needs_metadata is True
        assert item.cloud_file_size == cloud_file.size

    def test_from_cloud_file_with_local_path(self, sample_cloud_file_data):
        """Test creating PlaylistItem from CloudFile with local path."""
        cloud_file = CloudFile(**sample_cloud_file_data)
        item = PlaylistItem.from_cloud_file(
            cloud_file, account_id=1, local_path="/cache/song.mp3"
        )

        assert item.local_path == "/cache/song.mp3"
        assert item.needs_download is False  # Has local path

    def test_from_cloud_file_baidu(self, sample_cloud_file_data):
        """Test creating PlaylistItem from Baidu CloudFile."""
        cloud_file = CloudFile(**sample_cloud_file_data)
        item = PlaylistItem.from_cloud_file(cloud_file, account_id=1, provider="BAIDU")

        assert item.source == TrackSource.BAIDU

    def test_from_dict_local_track(self):
        """Test creating PlaylistItem from dict for local track."""
        data = {
            "id": 1,
            "path": "/music/song.mp3",
            "title": "Test Song",
            "artist": "Test Artist",
            "album": "Test Album",
            "duration": 180.0,
        }
        item = PlaylistItem.from_dict(data)

        assert item.source == TrackSource.LOCAL
        assert item.track_id == 1
        assert item.local_path == "/music/song.mp3"

    def test_from_dict_cloud_file(self):
        """Test creating PlaylistItem from dict for cloud file."""
        data = {
            "cloud_file_id": "quark_123",
            "cloud_account_id": 1,
            "path": "/cache/song.mp3",
            "title": "Cloud Song",
            "duration": 240.0,
        }
        item = PlaylistItem.from_dict(data)

        assert item.source == TrackSource.QUARK
        assert item.cloud_file_id == "quark_123"
        assert item.cloud_account_id == 1

    def test_from_dict_with_source(self):
        """Test creating PlaylistItem from dict with source field."""
        data = {
            "id": 1,
            "source": "QQ",
            "cloud_file_id": "song_mid",
            "title": "Online Song",
        }
        item = PlaylistItem.from_dict(data)

        assert item.source == TrackSource.QQ

    def test_to_dict(self):
        """Test converting PlaylistItem to dict."""
        item = PlaylistItem(
            track_id=1,
            local_path="/music/song.mp3",
            title="Test Song",
            artist="Test Artist",
            duration=180.0,
        )
        data = item.to_dict()

        assert data["id"] == 1
        assert data["path"] == "/music/song.mp3"
        assert data["title"] == "Test Song"
        assert data["artist"] == "Test Artist"
        assert data["source"] == "Local"

    def test_is_cloud_property(self):
        """Test is_cloud property."""
        local_item = PlaylistItem(source=TrackSource.LOCAL)
        assert local_item.is_cloud is False

        cloud_item = PlaylistItem(source=TrackSource.QUARK)
        assert cloud_item.is_cloud is True

        qq_item = PlaylistItem(source=TrackSource.QQ)
        assert qq_item.is_cloud is True

    def test_is_local_property(self):
        """Test is_local property."""
        local_item = PlaylistItem(source=TrackSource.LOCAL)
        assert local_item.is_local is True

        cloud_item = PlaylistItem(source=TrackSource.QUARK)
        assert cloud_item.is_local is False

    def test_is_ready_property(self):
        """Test is_ready property."""
        # Local item with path
        item = PlaylistItem(local_path="/music/song.mp3", needs_download=False)
        assert item.is_ready is True

        # Cloud item without path
        item = PlaylistItem(local_path="", needs_download=True)
        assert item.is_ready is False

        # Cloud item with cached path
        item = PlaylistItem(local_path="/cache/song.mp3", needs_download=False)
        assert item.is_ready is True

    def test_display_title_with_title(self):
        """Test display_title with title set."""
        item = PlaylistItem(title="My Song")
        assert item.display_title == "My Song"

    def test_display_title_without_title(self):
        """Test display_title falls back to filename."""
        item = PlaylistItem(local_path="/music/song.mp3")
        assert item.display_title == "song.mp3"

    def test_display_title_without_path(self):
        """Test display_title with no path."""
        item = PlaylistItem()
        assert item.display_title == "Unknown Track"

    def test_display_artist(self):
        """Test display_artist property."""
        item = PlaylistItem(artist="Artist")
        assert item.display_artist == "Artist"

        item_no_artist = PlaylistItem()
        assert item_no_artist.display_artist == "Unknown Artist"

    def test_str_representation(self):
        """Test string representation."""
        item = PlaylistItem(title="Test Song", artist="Test Artist")
        str_repr = str(item)
        assert "PlaylistItem" in str_repr
        assert "local" in str_repr
        assert "Test Song" in str_repr

    def test_repr_representation(self):
        """Test detailed representation."""
        item = PlaylistItem(
            title="Test", track_id=1, cloud_file_id="quark_123", local_path="/test.mp3"
        )
        repr_str = repr(item)
        assert "PlaylistItem" in repr_str
        assert "track_id=1" in repr_str
        assert "cloud_file_id=quark_123" in repr_str

    def test_to_play_queue_item(self):
        """Test converting to PlayQueueItem."""
        item = PlaylistItem(
            source=TrackSource.LOCAL,
            track_id=1,
            local_path="/music/song.mp3",
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            duration=180.0,
        )
        queue_item = item.to_play_queue_item(position=5)

        assert queue_item.position == 5
        assert queue_item.source == "Local"
        assert queue_item.track_id == 1
        assert queue_item.title == "Test Song"

    def test_to_play_queue_item_cloud(self):
        """Test converting cloud PlaylistItem to PlayQueueItem."""
        item = PlaylistItem(
            source=TrackSource.QUARK,
            cloud_file_id="quark_123",
            cloud_account_id=1,
            local_path="/cache/song.mp3",
            title="Cloud Song",
        )
        queue_item = item.to_play_queue_item(position=1)

        assert queue_item.source == "QUARK"
        assert queue_item.cloud_file_id == "quark_123"

    def test_to_play_queue_item_online(self):
        """Test converting online PlaylistItem to PlayQueueItem."""
        item = PlaylistItem(
            source=TrackSource.QQ,
            cloud_file_id="song_mid_123",
            local_path="/cache/online/song.mp3",
            title="Online Song",
            artist="Online Artist",
            album="Online Album",
            duration=200.0,
        )
        queue_item = item.to_play_queue_item(position=0)

        assert queue_item.source == "QQ"
        assert queue_item.cloud_file_id == "song_mid_123"
        assert queue_item.title == "Online Song"
        assert queue_item.artist == "Online Artist"

    def test_from_play_queue_item_local(self, temp_dir):
        """Test creating from PlayQueueItem for local track."""
        from domain.playback import PlayQueueItem

        queue_item = PlayQueueItem(
            position=1,
            source="Local",
            track_id=1,
            local_path="/music/song.mp3",
            title="Test Song",
        )
        playlist_item = PlaylistItem.from_play_queue_item(queue_item)

        assert playlist_item.source == TrackSource.LOCAL
        assert playlist_item.track_id == 1
        assert playlist_item.local_path == "/music/song.mp3"
        assert playlist_item.cover_path is None  # No db provided

    def test_from_play_queue_item_cloud(self):
        """Test creating from PlayQueueItem for cloud file."""
        from domain.playback import PlayQueueItem

        queue_item = PlayQueueItem(
            position=1,
            source="QUARK",
            cloud_file_id="quark_123",
            cloud_account_id=1,
            local_path="/cache/song.mp3",
            title="Cloud Song",
        )
        playlist_item = PlaylistItem.from_play_queue_item(queue_item)

        assert playlist_item.source == TrackSource.QUARK
        assert playlist_item.cloud_file_id == "quark_123"
        assert playlist_item.cloud_account_id == 1

    def test_from_play_queue_item_online(self):
        """Test creating from PlayQueueItem for online track."""
        from domain.playback import PlayQueueItem

        queue_item = PlayQueueItem(
            position=1,
            source="QQ",
            cloud_file_id="song_mid_123",
            local_path="/cache/online/song.mp3",
            title="Online Song",
            artist="Online Artist",
            album="Online Album",
            duration=200.0,
        )
        playlist_item = PlaylistItem.from_play_queue_item(queue_item)

        assert playlist_item.source == TrackSource.QQ
        assert playlist_item.cloud_file_id == "song_mid_123"
        assert playlist_item.title == "Online Song"
        assert playlist_item.artist == "Online Artist"

    def test_with_metadata(self):
        """Test with_metadata method for immutable update."""
        item = PlaylistItem(
            source=TrackSource.LOCAL,
            track_id=1,
            local_path="/music/song.mp3",
            title="Original Title",
            artist="Original Artist",
        )

        # Update metadata
        updated = item.with_metadata(
            cover_path="/covers/album.jpg",
            title="Updated Title",
            duration=180.0,
        )

        # Original should be unchanged
        assert item.title == "Original Title"
        assert item.cover_path is None

        # Updated should have new values
        assert updated.title == "Updated Title"
        assert updated.cover_path == "/covers/album.jpg"
        assert updated.duration == 180.0
        # Unchanged fields should remain
        assert updated.track_id == 1
        assert updated.source == TrackSource.LOCAL

    # --- download_failed tests ---

    def test_default_download_failed_is_false(self):
        """Test download_failed defaults to False."""
        item = PlaylistItem()
        assert item.download_failed is False

    def test_is_ready_false_when_download_failed(self):
        """Test is_ready returns False when download_failed is True."""
        item = PlaylistItem(local_path="/music/song.mp3", needs_download=False, download_failed=True)
        assert item.is_ready is False

    def test_is_ready_true_when_not_failed(self):
        """Test is_ready returns True when download_failed is False."""
        item = PlaylistItem(local_path="/music/song.mp3", needs_download=False, download_failed=False)
        assert item.is_ready is True

    def test_to_dict_includes_download_failed(self):
        """Test to_dict includes download_failed."""
        item = PlaylistItem(download_failed=True)
        data = item.to_dict()
        assert data.get("download_failed") is True

    def test_from_dict_reads_download_failed(self):
        """Test from_dict reads download_failed."""
        data = {"path": "/music/song.mp3", "download_failed": True}
        item = PlaylistItem.from_dict(data)
        assert item.download_failed is True

    def test_with_metadata_download_failed(self):
        """Test with_metadata can update download_failed."""
        item = PlaylistItem(download_failed=False)
        updated = item.with_metadata(download_failed=True)
        assert updated.download_failed is True
        assert item.download_failed is False

    def test_to_play_queue_item_includes_download_failed(self):
        """Test to_play_queue_item includes download_failed."""
        item = PlaylistItem(download_failed=True)
        queue_item = item.to_play_queue_item(position=0)
        assert queue_item.download_failed is True

    def test_from_play_queue_item_reads_download_failed(self):
        """Test from_play_queue_item reads download_failed."""
        from domain.playback import PlayQueueItem
        queue_item = PlayQueueItem(position=0, source="QUARK", download_failed=True)
        playlist_item = PlaylistItem.from_play_queue_item(queue_item)
        assert playlist_item.download_failed is True

    def test_from_cloud_file_lowercase_provider(self, sample_cloud_file_data):
        """Test from_cloud_file with lowercase provider."""
        cloud_file = CloudFile(**sample_cloud_file_data)
        item = PlaylistItem.from_cloud_file(cloud_file, account_id=1, provider="quark")
        assert item.source == TrackSource.QUARK

        item2 = PlaylistItem.from_cloud_file(cloud_file, account_id=1, provider="baidu")
        assert item2.source == TrackSource.BAIDU

    def test_from_dict_legacy_path_field(self):
        """Test from_dict with old 'path' field for backward compatibility."""
        data = {
            "path": "/music/song.mp3",
            "title": "Legacy Song",
        }
        item = PlaylistItem.from_dict(data)
        assert item.local_path == "/music/song.mp3"
        assert item.title == "Legacy Song"

    def test_from_dict_invalid_source_fallback(self):
        """Test from_dict falls back when source is invalid."""
        data = {
            "source": "INVALID_SOURCE",
            "cloud_file_id": "fid_123",
            "title": "Song",
        }
        item = PlaylistItem.from_dict(data)
        # Falls back to QUARK because cloud_file_id is present
        assert item.source == TrackSource.QUARK

    def test_with_metadata_preserves_cloud_fields(self):
        """Test with_metadata preserves cloud-related fields."""
        item = PlaylistItem(
            source=TrackSource.QUARK,
            cloud_file_id="quark_123",
            cloud_account_id=1,
            cloud_file_size=5242880,
            title="Original",
        )
        updated = item.with_metadata(title="Updated")
        assert updated.source == TrackSource.QUARK
        assert updated.cloud_file_id == "quark_123"
        assert updated.cloud_account_id == 1
        assert updated.cloud_file_size == 5242880

    def test_to_dict_completeness(self):
        """Test to_dict includes all expected keys."""
        item = PlaylistItem(
            track_id=1,
            local_path="/music/song.mp3",
            title="Song",
            artist="Artist",
            album="Album",
            duration=180.0,
            cover_path="/cover.jpg",
            source=TrackSource.LOCAL,
            cloud_file_id="fid_1",
            cloud_account_id=2,
            needs_download=True,
            needs_metadata=False,
            download_failed=False,
            cloud_file_size=1024,
        )
        data = item.to_dict()
        assert "id" in data
        assert "path" in data
        assert "title" in data
        assert "artist" in data
        assert "album" in data
        assert "duration" in data
        assert "cover_path" in data
        assert "source" in data
        assert "cloud_file_id" in data
        assert "cloud_account_id" in data
        assert "needs_download" in data
        assert "needs_metadata" in data
        assert "download_failed" in data
        assert "is_cloud" in data
