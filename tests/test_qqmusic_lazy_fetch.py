"""
Test QQ Music cover lazy fetch functionality.
"""
import pytest
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QApplication

from ui.strategies.track_search_strategy import TrackSearchStrategy
from ui.strategies.album_search_strategy import AlbumSearchStrategy
from ui.strategies.artist_search_strategy import ArtistSearchStrategy
from domain.track import Track
from domain.album import Album
from domain.artist import Artist


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance once."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    app.processEvents()


class TestQQMusicLazyFetch:
    """Test QQ Music cover lazy fetch in strategies."""

    def test_track_strategy_detects_qqmusic_lazy_fetch(self, qapp):
        """Test that Track strategy detects QQ Music results needing lazy fetch."""
        track = Track(id=1, path="/path/song.mp3", title="Test", artist="Artist")
        mock_repo = Mock()
        mock_bus = Mock()

        strategy = TrackSearchStrategy([track], mock_repo, mock_bus)

        # Result with album_mid but no cover_url
        result = {
            'source': 'qqmusic',
            'cover_url': None,
            'album_mid': 'album123',
            'id': 'song456'
        }

        assert strategy.needs_lazy_fetch(result) is True

    def test_track_strategy_detects_qqmusic_with_cover_url(self, qapp):
        """Test that Track strategy doesn't lazy fetch if cover_url exists."""
        track = Track(id=1, path="/path/song.mp3", title="Test", artist="Artist")
        mock_repo = Mock()
        mock_bus = Mock()

        strategy = TrackSearchStrategy([track], mock_repo, mock_bus)

        # Result with cover_url
        result = {
            'source': 'qqmusic',
            'cover_url': 'https://example.com/cover.jpg',
            'album_mid': 'album123',
            'id': 'song456'
        }

        assert strategy.needs_lazy_fetch(result) is False

    def test_track_strategy_lazy_fetch_with_album_mid(self, qapp):
        """Test lazy fetch using album_mid."""
        track = Track(id=1, path="/path/song.mp3", title="Test", artist="Artist")
        mock_repo = Mock()
        mock_bus = Mock()
        mock_cover_service = Mock()

        strategy = TrackSearchStrategy([track], mock_repo, mock_bus)

        result = {
            'source': 'qqmusic',
            'cover_url': None,
            'album_mid': 'album123',
            'id': 'song456'
        }

        # Mock provider cover helper
        with patch('ui.strategies.track_search_strategy.get_online_cover_url') as mock_get_url, \
             patch('ui.strategies.track_search_strategy.HttpClient') as mock_http:

            mock_get_url.return_value = 'https://y.gtimg.cn/music/photo_new/T002R500x500M000album123.jpg'
            mock_client = Mock()
            mock_client.get_content.return_value = b'fake_image_data'
            mock_http.return_value = mock_client

            cover_data = strategy.lazy_fetch(mock_cover_service, result)

            # Verify correct API was called with provider and album id
            mock_get_url.assert_called_once_with(
                provider_id='qqmusic',
                track_id='song456',
                album_id='album123',
                size=500,
            )
            assert cover_data == b'fake_image_data'

    def test_track_strategy_lazy_fetch_with_song_id(self, qapp):
        """Test lazy fetch using song id."""
        track = Track(id=1, path="/path/song.mp3", title="Test", artist="Artist")
        mock_repo = Mock()
        mock_bus = Mock()
        mock_cover_service = Mock()

        strategy = TrackSearchStrategy([track], mock_repo, mock_bus)

        result = {
            'source': 'qqmusic',
            'cover_url': None,
            'album_mid': None,
            'id': 'song456'
        }

        # Mock provider cover helper
        with patch('ui.strategies.track_search_strategy.get_online_cover_url') as mock_get_url, \
             patch('ui.strategies.track_search_strategy.HttpClient') as mock_http:

            mock_get_url.return_value = 'https://y.gtimg.cn/music/photo_new/T002R500x500M000song456.jpg'
            mock_client = Mock()
            mock_client.get_content.return_value = b'fake_image_data'
            mock_http.return_value = mock_client

            cover_data = strategy.lazy_fetch(mock_cover_service, result)

            # Verify correct API was called with provider and track id
            mock_get_url.assert_called_once_with(
                provider_id='qqmusic',
                track_id='song456',
                album_id=None,
                size=500,
            )
            assert cover_data == b'fake_image_data'

    def test_album_strategy_uses_correct_fields(self, qapp):
        """Test that Album strategy uses correct field names."""
        album = Album(name="Album", artist="Artist", cover_path=None, song_count=10, duration=300.0)
        mock_library = Mock()
        mock_bus = Mock()

        strategy = AlbumSearchStrategy(album, mock_library, mock_bus)

        # Result with correct fields
        result = {
            'source': 'qqmusic',
            'cover_url': None,
            'album_mid': 'album123',
            'id': 'song456'
        }

        assert strategy.needs_lazy_fetch(result) is True

    def test_artist_strategy_uses_singer_mid(self, qapp):
        """Test that Artist strategy uses singer_mid for lazy fetch."""
        artist = Artist(name="Artist", cover_path=None, song_count=20, album_count=5)
        mock_library = Mock()
        mock_bus = Mock()

        strategy = ArtistSearchStrategy(artist, mock_library, mock_bus)

        # Result with singer_mid
        result = {
            'source': 'qqmusic',
            'cover_url': None,
            'singer_mid': 'singer123'
        }

        assert strategy.needs_lazy_fetch(result) is True

    def test_artist_strategy_lazy_fetch(self, qapp):
        """Test artist lazy fetch with singer_mid."""
        artist = Artist(name="Artist", cover_path=None, song_count=20, album_count=5)
        mock_library = Mock()
        mock_bus = Mock()
        mock_cover_service = Mock()

        strategy = ArtistSearchStrategy(artist, mock_library, mock_bus)

        result = {
            'source': 'qqmusic',
            'cover_url': None,
            'singer_mid': 'singer123'
        }

        # Mock provider artist cover helper
        with patch('ui.strategies.artist_search_strategy.get_online_artist_cover_url') as mock_get_url, \
             patch('ui.strategies.artist_search_strategy.HttpClient') as mock_http:

            mock_get_url.return_value = 'https://y.gtimg.cn/music/photo_new/T001R500x500M000singer123.jpg'
            mock_client = Mock()
            mock_client.get_content.return_value = b'fake_artist_image'
            mock_http.return_value = mock_client

            cover_data = strategy.lazy_fetch(mock_cover_service, result)

            # Verify correct API was called
            mock_get_url.assert_called_once_with(
                provider_id='qqmusic',
                artist_id='singer123',
                size=500,
            )
            assert cover_data == b'fake_artist_image'
