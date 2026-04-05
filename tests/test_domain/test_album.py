"""
Tests for Album domain model.
"""

from domain.album import Album


class TestAlbum:
    """Test Album domain model."""

    def test_default_initialization(self):
        """Test default initialization."""
        album = Album(name="Test Album", artist="Test Artist")
        assert album.name == "Test Album"
        assert album.artist == "Test Artist"
        assert album.cover_path is None
        assert album.song_count == 0
        assert album.duration == 0.0
        assert album.year is None

    def test_full_initialization(self):
        """Test full initialization with all fields."""
        album = Album(
            name="Full Album",
            artist="Full Artist",
            cover_path="/path/to/cover.jpg",
            song_count=12,
            duration=3600.0,
            year=2023
        )
        assert album.name == "Full Album"
        assert album.artist == "Full Artist"
        assert album.cover_path == "/path/to/cover.jpg"
        assert album.song_count == 12
        assert album.duration == 3600.0
        assert album.year == 2023

    def test_display_name_with_name(self):
        """Test display_name property with name."""
        album = Album(name="My Album", artist="Artist")
        assert album.display_name == "My Album"

    def test_display_name_without_name(self):
        """Test display_name property without name."""
        album = Album(name="", artist="Artist")
        assert album.display_name == "Unknown Album"

    def test_display_artist_with_artist(self):
        """Test display_artist property with artist."""
        album = Album(name="Album", artist="My Artist")
        assert album.display_artist == "My Artist"

    def test_display_artist_without_artist(self):
        """Test display_artist property without artist."""
        album = Album(name="Album", artist="")
        assert album.display_artist == "Unknown Artist"

    def test_id_property(self):
        """Test id property generates unique ID."""
        album1 = Album(name="Album", artist="Artist")
        album2 = Album(name="Album", artist="Different Artist")
        album3 = Album(name="Different", artist="Artist")

        assert album1.id == "artist:album"
        assert album2.id == "different artist:album"
        assert album3.id == "artist:different"

    def test_hash_and_equality(self):
        """Test hash and equality based on ID."""
        album1 = Album(name="Album", artist="Artist")
        album2 = Album(name="Album", artist="Artist")
        album3 = Album(name="Different", artist="Artist")

        # Same ID means equal
        assert album1 == album2
        assert hash(album1) == hash(album2)

        # Different ID means not equal
        assert album1 != album3
        assert hash(album1) != hash(album3)

    def test_hashable_in_set(self):
        """Test that Album can be used in a set."""
        album1 = Album(name="Album1", artist="Artist")
        album2 = Album(name="Album2", artist="Artist")
        album3 = Album(name="Album1", artist="Artist")  # Same as album1

        album_set = {album1, album2, album3}
        assert len(album_set) == 2  # album1 and album2 only

    def test_case_insensitive_id(self):
        """Test that ID is case-insensitive."""
        album1 = Album(name="Album", artist="Artist")
        album2 = Album(name="ALBUM", artist="ARTIST")

        assert album1.id == album2.id
        assert album1 == album2
