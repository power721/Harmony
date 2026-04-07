"""Artist navigation regression tests."""

from PySide6.QtCore import QCoreApplication

from domain.track import Track
from infrastructure.database import DatabaseManager
from repositories.album_repository import SqliteAlbumRepository
from repositories.artist_repository import SqliteArtistRepository
from repositories.genre_repository import SqliteGenreRepository
from repositories.playlist_repository import SqlitePlaylistRepository
from repositories.track_repository import SqliteTrackRepository
from services.library import LibraryService
from services.metadata import split_artists
from system.event_bus import EventBus


def _build_library_service(db_path: str) -> LibraryService:
    db = DatabaseManager(db_path)
    track_repo = SqliteTrackRepository(db_path, db_manager=db)
    playlist_repo = SqlitePlaylistRepository(db_path, db_manager=db)
    album_repo = SqliteAlbumRepository(db_path, db_manager=db)
    artist_repo = SqliteArtistRepository(db_path, db_manager=db)
    genre_repo = SqliteGenreRepository(db_path, db_manager=db)
    return LibraryService(
        track_repo=track_repo,
        playlist_repo=playlist_repo,
        album_repo=album_repo,
        artist_repo=artist_repo,
        genre_repo=genre_repo,
        event_bus=EventBus.instance(),
    )


def test_artist_navigation(tmp_path):
    """get_artist_by_name should resolve normalized names from cached artist rows."""
    QCoreApplication.instance() or QCoreApplication([])

    db_path = str(tmp_path / "artist-navigation.db")
    library = _build_library_service(db_path)

    tracks = [
        Track(path="/music/a-lin-1.mp3", title="Song A", artist="A-Lin", album="Album A"),
        Track(path="/music/taylor-1.mp3", title="Song B", artist="Taylor Swift", album="Album B"),
        Track(path="/music/jay-1.mp3", title="Song C", artist="周杰伦", album="Album C"),
        Track(path="/music/huang-1.mp3", title="Song D", artist="黄霄雲", album="Album D"),
        Track(
            path="/music/collab-1.mp3",
            title="Collab 1",
            artist="A-Lin, 李佳薇, 汪苏泷",
            album="Collab Album",
        ),
        Track(
            path="/music/collab-2.mp3",
            title="Collab 2",
            artist="Taylor Swift, Ed Sheeran",
            album="Collab Album 2",
        ),
    ]
    library.add_tracks_bulk(tracks)
    library.refresh_albums_artists(immediate=True)

    expected_artists = [
        "A-Lin",
        "Taylor Swift",
        "周杰伦",
        "黄霄雲",
        "李佳薇",
        "汪苏泷",
        "Ed Sheeran",
    ]

    for artist_name in expected_artists:
        artist = library.get_artist_by_name(artist_name)
        assert artist is not None, artist_name
        assert artist.name == artist_name

    multi_artist_cases = {
        "A-Lin, 李佳薇, 汪苏泷": ["A-Lin", "李佳薇", "汪苏泷"],
        "Taylor Swift, Ed Sheeran": ["Taylor Swift", "Ed Sheeran"],
        "周杰伦": ["周杰伦"],
    }
    for artist_string, expected in multi_artist_cases.items():
        parsed = split_artists(artist_string)
        assert parsed == expected
        for artist_name in parsed:
            assert library.get_artist_by_name(artist_name) is not None
