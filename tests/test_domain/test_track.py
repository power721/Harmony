"""
Tests for Track domain model.
"""

from datetime import datetime
from domain.track import Track, TrackId, TrackSource


class TestTrack:
    """Test Track domain model."""

    def test_default_initialization(self):
        """Test track with default values."""
        track = Track()
        assert track.id is None
        assert track.path == ""
        assert track.title == ""
        assert track.artist == ""
        assert track.album == ""
        assert track.duration == 0.0
        assert track.cover_path is None
        assert track.cloud_file_id is None
        assert isinstance(track.created_at, datetime)

    def test_full_initialization(self, sample_track_data):
        """Test track with all fields populated."""
        track = Track(**sample_track_data)
        assert track.id == 1
        assert track.path == "/music/test.mp3"
        assert track.title == "Test Song"
        assert track.artist == "Test Artist"
        assert track.album == "Test Album"
        assert track.duration == 180.5
        assert track.cover_path == "/covers/test.jpg"

    def test_display_name_with_title(self):
        """Test display_name returns title when available."""
        track = Track(title="My Song")
        assert track.display_name == "My Song"

    def test_display_name_without_title(self):
        """Test display_name falls back to filename."""
        track = Track(path="/music/unknown.mp3")
        assert track.display_name == "unknown.mp3"

    def test_display_name_without_path(self):
        """Test display_name with empty path."""
        track = Track(path="")
        assert track.display_name == "Unknown"

    def test_artist_album_with_both(self):
        """Test artist_album with both artist and album."""
        track = Track(artist="Artist", album="Album")
        assert track.artist_album == "Artist - Album"

    def test_artist_album_same_artist_album(self):
        """Test artist_album when artist and album are the same."""
        track = Track(artist="Artist", album="Artist")
        assert track.artist_album == "Artist"

    def test_artist_album_only_artist(self):
        """Test artist_album with only artist."""
        track = Track(artist="Artist", album="")
        assert track.artist_album == "Artist"

    def test_artist_album_empty(self):
        """Test artist_album with no artist or album."""
        track = Track(artist="", album="")
        assert track.artist_album == "Unknown"

    def test_track_id_type_alias(self):
        """Test TrackId type alias."""
        track_id: TrackId = 123
        assert isinstance(track_id, int)

    def test_created_at_auto_set(self):
        """Test created_at is automatically set."""
        before = datetime.now()
        track = Track()
        after = datetime.now()
        assert before <= track.created_at <= after

    def test_created_at_can_be_overridden(self):
        """Test created_at can be explicitly set."""
        specific_time = datetime(2024, 1, 1, 12, 0, 0)
        track = Track(created_at=specific_time)
        assert track.created_at == specific_time

    def test_source_default_local(self):
        """Test source defaults to LOCAL."""
        track = Track()
        assert track.source == TrackSource.LOCAL

    def test_source_set_other_values(self):
        """Test source can be set to other values."""
        track = Track(source=TrackSource.QUARK)
        assert track.source == TrackSource.QUARK

        track = Track(source=TrackSource.QQ)
        assert track.source == TrackSource.QQ

        track = Track(source=TrackSource.BAIDU)
        assert track.source == TrackSource.BAIDU

    def test_cloud_file_id_default_and_set(self):
        """Test cloud_file_id default None and can be set."""
        track = Track()
        assert track.cloud_file_id is None

        track = Track(cloud_file_id="quark_123")
        assert track.cloud_file_id == "quark_123"

    def test_file_size_and_file_mtime(self):
        """Test file_size and file_mtime fields."""
        track = Track(file_size=5242880, file_mtime=1700000000.0)
        assert track.file_size == 5242880
        assert track.file_mtime == 1700000000.0

        # Defaults
        track2 = Track()
        assert track2.file_size is None
        assert track2.file_mtime is None

    def test_track_source_enum_string_values(self):
        """Test TrackSource enum string values."""
        assert TrackSource.LOCAL.value == "Local"
        assert TrackSource.QUARK.value == "QUARK"
        assert TrackSource.BAIDU.value == "BAIDU"
        assert TrackSource.QQ.value == "QQ"
