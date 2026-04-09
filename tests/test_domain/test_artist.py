"""
Tests for Artist domain model.
"""

from domain.artist import Artist


class TestArtist:
    """Test Artist domain model."""

    def test_default_initialization(self):
        """Test default initialization."""
        artist = Artist(name="Test Artist")
        assert artist.name == "Test Artist"
        assert artist.cover_path is None
        assert artist.song_count == 0
        assert artist.album_count == 0

    def test_full_initialization(self):
        """Test full initialization with all fields."""
        artist = Artist(
            name="Full Artist",
            cover_path="/path/to/artist.jpg",
            song_count=50,
            album_count=5
        )
        assert artist.name == "Full Artist"
        assert artist.cover_path == "/path/to/artist.jpg"
        assert artist.song_count == 50
        assert artist.album_count == 5

    def test_display_name_with_name(self):
        """Test display_name property with name."""
        artist = Artist(name="My Artist")
        assert artist.display_name == "My Artist"

    def test_display_name_without_name(self):
        """Test display_name property without name."""
        artist = Artist(name="")
        assert artist.display_name == "Unknown Artist"

    def test_id_property(self):
        """Test id property generates unique ID."""
        artist1 = Artist(name="Artist One")
        artist2 = Artist(name="Artist Two")
        artist3 = Artist(name="")

        assert artist1.id == "artist one"
        assert artist2.id == "artist two"
        assert artist3.id == "unknown"

    def test_hash_and_equality(self):
        """Test hash and equality based on ID."""
        artist1 = Artist(name="Artist")
        artist2 = Artist(name="Artist")
        artist3 = Artist(name="Different")

        # Same ID means equal
        assert artist1 == artist2
        assert hash(artist1) == hash(artist2)

        # Different ID means not equal
        assert artist1 != artist3
        assert hash(artist1) != hash(artist3)

    def test_hashable_in_set(self):
        """Test that Artist can be used in a set."""
        artist1 = Artist(name="Artist1")
        artist2 = Artist(name="Artist2")
        artist3 = Artist(name="Artist1")  # Same as artist1

        artist_set = {artist1, artist2, artist3}
        assert len(artist_set) == 2  # artist1 and artist2 only

    def test_case_insensitive_id(self):
        """Test that ID is case-insensitive."""
        artist1 = Artist(name="Artist")
        artist2 = Artist(name="ARTIST")

        assert artist1.id == artist2.id
        assert artist1 == artist2

    def test_equality_with_non_artist(self):
        """Test equality with non-Artist object."""
        artist = Artist(name="Artist")
        assert artist != "Artist"
        assert artist != 123
        assert artist is not None

    def test_id_property_is_stable_across_accesses(self):
        """Test repeated access returns the same computed ID."""
        artist = Artist(name="Artist")

        first = artist.id
        second = artist.id

        assert first == "artist"
        assert second == "artist"
