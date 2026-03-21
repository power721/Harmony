"""
Tests for PlaylistItem domain model.
"""

import pytest
from domain.playlist_item import PlaylistItem
from domain.track import Track
from domain.cloud import CloudFile, CloudProvider


class TestPlaylistItem:
    """Test PlaylistItem domain model."""

    def test_default_initialization(self):
        """Test playlist item with default values."""
        item = PlaylistItem()
        assert item.source_type == CloudProvider.LOCAL
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

        assert item.source_type == CloudProvider.LOCAL
        assert item.track_id == track.id
        assert item.local_path == track.path
        assert item.title == track.title
        assert item.artist == track.artist
        assert item.album == track.album
        assert item.duration == track.duration
        assert item.cover_path == track.cover_path
        assert item.needs_download is False
        assert item.needs_metadata is False

    def test_from_cloud_file_without_local_path(self, sample_cloud_file_data):
        """Test creating PlaylistItem from CloudFile without local path."""
        cloud_file = CloudFile(**sample_cloud_file_data)
        item = PlaylistItem.from_cloud_file(cloud_file, account_id=1)

        assert item.source_type == CloudProvider.QUARK
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

        assert item.source_type == CloudProvider.LOCAL
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

        assert item.source_type == CloudProvider.QUARK
        assert item.cloud_file_id == "quark_123"
        assert item.cloud_account_id == 1

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
        assert data["source_type"] == "local"

    def test_is_cloud_property(self):
        """Test is_cloud property."""
        local_item = PlaylistItem(source_type=CloudProvider.LOCAL)
        assert local_item.is_cloud is False

        cloud_item = PlaylistItem(source_type=CloudProvider.QUARK)
        assert cloud_item.is_cloud is True

    def test_is_local_property(self):
        """Test is_local property."""
        local_item = PlaylistItem(source_type=CloudProvider.LOCAL)
        assert local_item.is_local is True

        cloud_item = PlaylistItem(source_type=CloudProvider.QUARK)
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
            track_id=1,
            local_path="/music/song.mp3",
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            duration=180.0,
        )
        queue_item = item.to_play_queue_item(position=5)

        assert queue_item.position == 5
        assert queue_item.source_type == "local"
        assert queue_item.track_id == 1
        assert queue_item.title == "Test Song"

    def test_to_play_queue_item_cloud(self):
        """Test converting cloud PlaylistItem to PlayQueueItem."""
        item = PlaylistItem(
            source_type=CloudProvider.QUARK,
            cloud_file_id="quark_123",
            cloud_account_id=1,
            local_path="/cache/song.mp3",
            title="Cloud Song",
        )
        queue_item = item.to_play_queue_item(position=1)

        assert queue_item.source_type == "cloud"
        assert queue_item.cloud_type == "quark"
        assert queue_item.cloud_file_id == "quark_123"

    def test_from_play_queue_item_local(self, temp_dir):
        """Test creating from PlayQueueItem for local track."""
        from domain.playback import PlayQueueItem

        queue_item = PlayQueueItem(
            position=1,
            source_type="local",
            track_id=1,
            local_path="/music/song.mp3",
            title="Test Song",
        )
        playlist_item = PlaylistItem.from_play_queue_item(queue_item, db=None)

        assert playlist_item.source_type == CloudProvider.LOCAL
        assert playlist_item.track_id == 1
        assert playlist_item.local_path == "/music/song.mp3"
        assert playlist_item.cover_path is None  # No db provided

    def test_from_play_queue_item_cloud(self):
        """Test creating from PlayQueueItem for cloud file."""
        from domain.playback import PlayQueueItem

        queue_item = PlayQueueItem(
            position=1,
            source_type="cloud",
            cloud_type="quark",
            cloud_file_id="quark_123",
            cloud_account_id=1,
            local_path="/cache/song.mp3",
            title="Cloud Song",
        )
        playlist_item = PlaylistItem.from_play_queue_item(queue_item, db=None)

        assert playlist_item.source_type == CloudProvider.QUARK
        assert playlist_item.cloud_file_id == "quark_123"
        assert playlist_item.cloud_account_id == 1

    def test_to_play_queue_item_online(self):
        """Test converting online PlaylistItem to PlayQueueItem."""
        item = PlaylistItem(
            source_type=CloudProvider.ONLINE,
            cloud_file_id="song_mid_123",
            local_path="/cache/online/song.mp3",
            title="Online Song",
            artist="Online Artist",
            album="Online Album",
            duration=200.0,
        )
        queue_item = item.to_play_queue_item(position=0)

        assert queue_item.source_type == "online"
        assert queue_item.cloud_type == "QQ"
        assert queue_item.cloud_file_id == "song_mid_123"
        assert queue_item.title == "Online Song"
        assert queue_item.artist == "Online Artist"

    def test_from_play_queue_item_online(self):
        """Test creating from PlayQueueItem for online track."""
        from domain.playback import PlayQueueItem

        queue_item = PlayQueueItem(
            position=1,
            source_type="online",
            cloud_type="QQ",
            cloud_file_id="song_mid_123",
            local_path="/cache/online/song.mp3",
            title="Online Song",
            artist="Online Artist",
            album="Online Album",
            duration=200.0,
        )
        playlist_item = PlaylistItem.from_play_queue_item(queue_item, db=None)

        assert playlist_item.source_type == CloudProvider.ONLINE
        assert playlist_item.cloud_file_id == "song_mid_123"
        assert playlist_item.title == "Online Song"
        assert playlist_item.artist == "Online Artist"
