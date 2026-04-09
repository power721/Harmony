"""
Tests for Playback domain models.
"""

from datetime import datetime
from domain.playback import PlayMode, PlaybackState, PlayQueueItem


class TestPlayMode:
    """Test PlayMode enumeration."""

    def test_play_mode_values(self):
        """Test all play mode values exist."""
        assert PlayMode.SEQUENTIAL.value == 0
        assert PlayMode.LOOP.value == 1
        assert PlayMode.PLAYLIST_LOOP.value == 2
        assert PlayMode.RANDOM.value == 3
        assert PlayMode.RANDOM_LOOP.value == 4
        assert PlayMode.RANDOM_TRACK_LOOP.value == 5

    def test_play_mode_from_value(self):
        """Test creating PlayMode from integer value."""
        assert PlayMode(0) == PlayMode.SEQUENTIAL
        assert PlayMode(1) == PlayMode.LOOP


class TestPlaybackState:
    """Test PlaybackState enumeration."""

    def test_playback_state_values(self):
        """Test all playback state values exist."""
        assert PlaybackState.STOPPED.value == 0
        assert PlaybackState.PLAYING.value == 1
        assert PlaybackState.PAUSED.value == 2

    def test_playback_state_from_value(self):
        """Test creating PlaybackState from integer value."""
        assert PlaybackState(0) == PlaybackState.STOPPED
        assert PlaybackState(1) == PlaybackState.PLAYING


class TestPlayQueueItem:
    """Test PlayQueueItem domain model."""

    def test_default_initialization(self):
        """Test queue item with default values."""
        item = PlayQueueItem()
        assert item.id is None
        assert item.position == 0
        assert item.source == "Local"
        assert item.track_id is None
        assert item.cloud_file_id is None
        assert item.cloud_account_id is None
        assert item.local_path == ""
        assert item.title == ""
        assert item.artist == ""
        assert item.album == ""
        assert item.duration == 0.0
        assert isinstance(item.created_at, datetime)

    def test_local_track_initialization(self):
        """Test queue item for local track."""
        item = PlayQueueItem(
            position=1,
            source="Local",
            track_id=123,
            local_path="/music/song.mp3",
            title="Test Song",
            artist="Test Artist",
            duration=180.0,
        )
        assert item.position == 1
        assert item.source == "Local"
        assert item.track_id == 123
        assert item.local_path == "/music/song.mp3"
        assert item.title == "Test Song"

    def test_cloud_file_initialization(self):
        """Test queue item for cloud file (Quark)."""
        item = PlayQueueItem(
            position=1,
            source="QUARK",
            cloud_file_id="quark_123",
            cloud_account_id=1,
            local_path="/cache/song.mp3",
            title="Cloud Song",
            duration=240.0,
        )
        assert item.source == "QUARK"
        assert item.cloud_file_id == "quark_123"
        assert item.cloud_account_id == 1

    def test_online_track_initialization(self):
        """Test queue item for online track."""
        item = PlayQueueItem(
            position=1,
            source="ONLINE",
            cloud_file_id="song_mid_123",
            online_provider_id="qqmusic",
            local_path="/cache/online/song.mp3",
            title="Online Song",
            artist="Online Artist",
            duration=200.0,
        )
        assert item.source == "ONLINE"
        assert item.cloud_file_id == "song_mid_123"

    def test_baidu_cloud_initialization(self):
        """Test queue item for Baidu cloud file."""
        item = PlayQueueItem(
            position=1,
            source="BAIDU",
            cloud_file_id="baidu_456",
            cloud_account_id=2,
            title="Baidu Song",
        )
        assert item.source == "BAIDU"
        assert item.cloud_file_id == "baidu_456"

    def test_created_at_auto_set(self):
        """Test created_at is automatically set."""
        before = datetime.now()
        item = PlayQueueItem()
        after = datetime.now()
        assert before <= item.created_at <= after

    def test_created_at_can_be_overridden(self):
        """Test created_at can be explicitly set."""
        specific_time = datetime(2024, 1, 1, 12, 0, 0)
        item = PlayQueueItem(created_at=specific_time)
        assert item.created_at == specific_time

    def test_download_failed_default_false(self):
        """Test download_failed defaults to False."""
        item = PlayQueueItem()
        assert item.download_failed is False

    def test_download_failed_set_true(self):
        """Test download_failed can be set to True."""
        item = PlayQueueItem(download_failed=True)
        assert item.download_failed is True


class TestPlayModeAdditional:
    """Additional PlayMode tests."""

    def test_play_mode_iteration(self):
        """Test iterating over all PlayMode values."""
        modes = list(PlayMode)
        assert len(modes) == 6
        assert PlayMode.SEQUENTIAL in modes
        assert PlayMode.LOOP in modes
        assert PlayMode.PLAYLIST_LOOP in modes
        assert PlayMode.RANDOM in modes
        assert PlayMode.RANDOM_LOOP in modes
        assert PlayMode.RANDOM_TRACK_LOOP in modes


class TestPlaybackStateAdditional:
    """Additional PlaybackState tests."""

    def test_playback_state_iteration(self):
        """Test iterating over all PlaybackState values."""
        states = list(PlaybackState)
        assert len(states) == 3
        assert PlaybackState.STOPPED in states
        assert PlaybackState.PLAYING in states
        assert PlaybackState.PAUSED in states
