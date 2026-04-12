"""
Tests for Playlist domain model.
"""

from datetime import datetime
from domain.playlist import Playlist


class TestPlaylist:
    """Test Playlist domain model."""

    def test_default_initialization(self):
        """Test playlist with default values."""
        playlist = Playlist()
        assert playlist.id is None
        assert playlist.name == ""
        assert isinstance(playlist.created_at, datetime)

    def test_full_initialization(self, sample_playlist_data):
        """Test playlist with all fields populated."""
        playlist = Playlist(**sample_playlist_data)
        assert playlist.id == 1
        assert playlist.name == "My Playlist"
        assert isinstance(playlist.created_at, datetime)

    def test_created_at_auto_set(self):
        """Test created_at is automatically set."""
        before = datetime.now()
        playlist = Playlist()
        after = datetime.now()
        assert before <= playlist.created_at <= after

    def test_created_at_can_be_overridden(self):
        """Test created_at can be explicitly set."""
        specific_time = datetime(2024, 1, 1, 12, 0, 0)
        playlist = Playlist(created_at=specific_time)
        assert playlist.created_at == specific_time

    def test_playlist_with_name(self):
        """Test playlist with name only."""
        playlist = Playlist(name="Favorites")
        assert playlist.name == "Favorites"
        assert isinstance(playlist.created_at, datetime)

    def test_playlist_supports_folder_and_position(self):
        """Test playlist folder assignment and ordering fields."""
        playlist = Playlist(name="Road Trip", folder_id=7, position=3)

        assert playlist.folder_id == 7
        assert playlist.position == 3
