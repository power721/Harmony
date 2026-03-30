"""
Tests for PlayHistory and Favorite domain models.
"""

import pytest
from datetime import datetime
from domain.history import PlayHistory, Favorite


class TestPlayHistory:
    """Test PlayHistory domain model."""

    def test_default_initialization(self):
        """Test default initialization."""
        history = PlayHistory()
        assert history.id is None
        assert history.track_id == 0
        assert history.play_count == 1
        assert history.played_at is not None

    def test_full_initialization(self):
        """Test full initialization with all fields."""
        now = datetime.now()
        history = PlayHistory(
            id=1,
            track_id=42,
            played_at=now,
            play_count=5
        )
        assert history.id == 1
        assert history.track_id == 42
        assert history.played_at == now
        assert history.play_count == 5

    def test_played_at_auto_set(self):
        """Test that played_at is automatically set."""
        before = datetime.now()
        history = PlayHistory(track_id=1)
        after = datetime.now()

        assert history.played_at is not None
        assert before <= history.played_at <= after

    def test_played_at_can_be_overridden(self):
        """Test that played_at can be explicitly set."""
        custom_time = datetime(2023, 1, 1, 12, 0, 0)
        history = PlayHistory(track_id=1, played_at=custom_time)
        assert history.played_at == custom_time

    def test_play_count_default(self):
        """Test that play_count defaults to 1."""
        history = PlayHistory(track_id=1)
        assert history.play_count == 1

    def test_play_count_can_be_set(self):
        """Test that play_count can be explicitly set."""
        history = PlayHistory(track_id=1, play_count=100)
        assert history.play_count == 100


class TestFavorite:
    """Test Favorite domain model."""

    def test_default_initialization(self):
        """Test default initialization."""
        favorite = Favorite()
        assert favorite.id is None
        assert favorite.track_id == 0
        assert favorite.created_at is not None

    def test_full_initialization(self):
        """Test full initialization with all fields."""
        now = datetime.now()
        favorite = Favorite(
            id=1,
            track_id=42,
            created_at=now
        )
        assert favorite.id == 1
        assert favorite.track_id == 42
        assert favorite.created_at == now

    def test_created_at_auto_set(self):
        """Test that created_at is automatically set."""
        before = datetime.now()
        favorite = Favorite(track_id=1)
        after = datetime.now()

        assert favorite.created_at is not None
        assert before <= favorite.created_at <= after

    def test_created_at_can_be_overridden(self):
        """Test that created_at can be explicitly set."""
        custom_time = datetime(2023, 1, 1, 12, 0, 0)
        favorite = Favorite(track_id=1, created_at=custom_time)
        assert favorite.created_at == custom_time


class TestPlayHistoryBoundary:
    """Boundary tests for PlayHistory."""

    def test_play_count_zero(self):
        """Test play_count can be zero."""
        history = PlayHistory(track_id=1, play_count=0)
        assert history.play_count == 0

    def test_play_count_negative(self):
        """Test play_count accepts negative values (data may be corrupted)."""
        history = PlayHistory(track_id=1, play_count=-1)
        assert history.play_count == -1

    def test_play_count_large_value(self):
        """Test play_count with large value."""
        history = PlayHistory(track_id=1, play_count=1000000)
        assert history.play_count == 1000000
