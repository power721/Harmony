"""
Tests for Online Music domain models.
"""

import pytest
from domain.online_music import (
    OnlineSinger,
    AlbumInfo,
    OnlineTrack,
    OnlineArtist,
    OnlineAlbum,
    OnlinePlaylist,
    SearchResult,
    SearchType,
)


class TestOnlineSinger:
    """Test OnlineSinger domain model."""

    def test_default_initialization(self):
        """Test singer with default values."""
        singer = OnlineSinger()
        assert singer.mid == ""
        assert singer.name == ""

    def test_full_initialization(self):
        """Test singer with all fields populated."""
        singer = OnlineSinger(mid="singer_mid_123", name="Test Singer")
        assert singer.mid == "singer_mid_123"
        assert singer.name == "Test Singer"


class TestAlbumInfo:
    """Test AlbumInfo domain model."""

    def test_default_initialization(self):
        """Test album info with default values."""
        album = AlbumInfo()
        assert album.mid == ""
        assert album.name == ""

    def test_full_initialization(self):
        """Test album info with all fields populated."""
        album = AlbumInfo(mid="album_mid_456", name="Test Album")
        assert album.mid == "album_mid_456"
        assert album.name == "Test Album"


class TestOnlineTrack:
    """Test OnlineTrack domain model."""

    def test_default_initialization(self):
        """Test track with default values."""
        track = OnlineTrack()
        assert track.mid == ""
        assert track.id is None
        assert track.title == ""
        assert track.singer == []
        assert track.album is None
        assert track.duration == 0
        assert track.pay_play == 0

    def test_full_initialization(self):
        """Test track with all fields populated."""
        singers = [OnlineSinger(mid="s1", name="Artist 1"), OnlineSinger(mid="s2", name="Artist 2")]
        album = AlbumInfo(mid="album_1", name="Test Album")
        track = OnlineTrack(
            mid="track_mid_123",
            id=12345,
            title="Test Song",
            singer=singers,
            album=album,
            duration=180,
            pay_play=0,
        )
        assert track.mid == "track_mid_123"
        assert track.id == 12345
        assert track.title == "Test Song"
        assert len(track.singer) == 2
        assert track.album.name == "Test Album"
        assert track.duration == 180
        assert track.pay_play == 0

    def test_singer_name_empty(self):
        """Test singer_name with no singers."""
        track = OnlineTrack()
        assert track.singer_name == ""

    def test_singer_name_single(self):
        """Test singer_name with single singer."""
        track = OnlineTrack(singer=[OnlineSinger(name="Artist 1")])
        assert track.singer_name == "Artist 1"

    def test_singer_name_multiple(self):
        """Test singer_name with multiple singers."""
        track = OnlineTrack(singer=[
            OnlineSinger(name="Artist 1"),
            OnlineSinger(name="Artist 2"),
        ])
        assert track.singer_name == "Artist 1, Artist 2"

    def test_singer_name_skips_empty(self):
        """Test singer_name skips empty names."""
        track = OnlineTrack(singer=[
            OnlineSinger(name="Artist 1"),
            OnlineSinger(name=""),
            OnlineSinger(name="Artist 2"),
        ])
        assert track.singer_name == "Artist 1, Artist 2"

    def test_album_name_with_album(self):
        """Test album_name when album is set."""
        track = OnlineTrack(album=AlbumInfo(name="Test Album"))
        assert track.album_name == "Test Album"

    def test_album_name_without_album(self):
        """Test album_name when album is None."""
        track = OnlineTrack()
        assert track.album_name == ""

    def test_display_title_with_title(self):
        """Test display_title returns title when available."""
        track = OnlineTrack(title="My Song")
        assert track.display_title == "My Song"

    def test_display_title_without_title(self):
        """Test display_title returns Unknown when empty."""
        track = OnlineTrack()
        assert track.display_title == "Unknown"

    def test_is_vip_free(self):
        """Test is_vip for free track."""
        track = OnlineTrack(pay_play=0)
        assert track.is_vip is False

    def test_is_vip_paid(self):
        """Test is_vip for VIP track."""
        track = OnlineTrack(pay_play=1)
        assert track.is_vip is True


class TestOnlineArtist:
    """Test OnlineArtist domain model."""

    def test_default_initialization(self):
        """Test artist with default values."""
        artist = OnlineArtist()
        assert artist.mid == ""
        assert artist.name == ""
        assert artist.avatar_url is None
        assert artist.song_count == 0
        assert artist.album_count == 0

    def test_full_initialization(self):
        """Test artist with all fields populated."""
        artist = OnlineArtist(
            mid="artist_mid_123",
            name="Test Artist",
            avatar_url="https://example.com/avatar.jpg",
            song_count=50,
            album_count=5,
        )
        assert artist.mid == "artist_mid_123"
        assert artist.name == "Test Artist"
        assert artist.avatar_url == "https://example.com/avatar.jpg"
        assert artist.song_count == 50
        assert artist.album_count == 5


class TestOnlineAlbum:
    """Test OnlineAlbum domain model."""

    def test_default_initialization(self):
        """Test album with default values."""
        album = OnlineAlbum()
        assert album.mid == ""
        assert album.name == ""
        assert album.singer_mid == ""
        assert album.singer_name == ""
        assert album.cover_url is None
        assert album.song_count == 0
        assert album.publish_date is None
        assert album.description is None
        assert album.company is None
        assert album.genre is None
        assert album.language is None
        assert album.album_type is None

    def test_full_initialization(self):
        """Test album with all fields populated."""
        album = OnlineAlbum(
            mid="album_mid_123",
            name="Test Album",
            singer_mid="singer_mid_456",
            singer_name="Test Singer",
            cover_url="https://example.com/cover.jpg",
            song_count=10,
            publish_date="2024-01-01",
            description="Test description",
            company="Test Company",
            genre="Pop",
            language="Chinese",
            album_type="Studio",
        )
        assert album.mid == "album_mid_123"
        assert album.name == "Test Album"
        assert album.singer_mid == "singer_mid_456"
        assert album.singer_name == "Test Singer"
        assert album.cover_url == "https://example.com/cover.jpg"
        assert album.song_count == 10
        assert album.publish_date == "2024-01-01"
        assert album.description == "Test description"
        assert album.company == "Test Company"
        assert album.genre == "Pop"
        assert album.language == "Chinese"
        assert album.album_type == "Studio"


class TestOnlinePlaylist:
    """Test OnlinePlaylist domain model."""

    def test_default_initialization(self):
        """Test playlist with default values."""
        playlist = OnlinePlaylist()
        assert playlist.id == ""
        assert playlist.mid == ""
        assert playlist.title == ""
        assert playlist.creator == ""
        assert playlist.cover_url is None
        assert playlist.song_count == 0
        assert playlist.play_count == 0

    def test_full_initialization(self):
        """Test playlist with all fields populated."""
        playlist = OnlinePlaylist(
            id="playlist_id_123",
            mid="playlist_mid_456",
            title="Test Playlist",
            creator="Test Creator",
            cover_url="https://example.com/cover.jpg",
            song_count=20,
            play_count=1000,
        )
        assert playlist.id == "playlist_id_123"
        assert playlist.mid == "playlist_mid_456"
        assert playlist.title == "Test Playlist"
        assert playlist.creator == "Test Creator"
        assert playlist.cover_url == "https://example.com/cover.jpg"
        assert playlist.song_count == 20
        assert playlist.play_count == 1000


class TestSearchResult:
    """Test SearchResult domain model."""

    def test_default_initialization(self):
        """Test search result with default values."""
        result = SearchResult()
        assert result.keyword == ""
        assert result.search_type == "song"
        assert result.page == 1
        assert result.page_size == 20
        assert result.total == 0
        assert result.tracks == []
        assert result.artists == []
        assert result.albums == []
        assert result.playlists == []

    def test_full_initialization(self):
        """Test search result with all fields populated."""
        tracks = [OnlineTrack(mid="t1", title="Song 1")]
        artists = [OnlineArtist(mid="a1", name="Artist 1")]
        albums = [OnlineAlbum(mid="al1", name="Album 1")]
        playlists = [OnlinePlaylist(id="p1", title="Playlist 1")]

        result = SearchResult(
            keyword="test",
            search_type="song",
            page=1,
            page_size=20,
            total=100,
            tracks=tracks,
            artists=artists,
            albums=albums,
            playlists=playlists,
        )
        assert result.keyword == "test"
        assert result.search_type == "song"
        assert result.page == 1
        assert result.page_size == 20
        assert result.total == 100
        assert len(result.tracks) == 1
        assert len(result.artists) == 1
        assert len(result.albums) == 1
        assert len(result.playlists) == 1


class TestSearchType:
    """Test SearchType constants."""

    def test_search_type_values(self):
        """Test that search type constants have expected values."""
        assert SearchType.SONG == "song"
        assert SearchType.SINGER == "singer"
        assert SearchType.ALBUM == "album"
        assert SearchType.PLAYLIST == "playlist"
