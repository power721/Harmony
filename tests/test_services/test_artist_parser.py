"""Tests for artist_parser module."""

import pytest
from services.metadata.artist_parser import (
    split_artists,
    normalize_artist_name,
    get_canonical_artist_name,
)


class TestSplitArtists:
    """Tests for split_artists function."""

    def test_empty_string(self):
        """Test empty string returns empty list."""
        assert split_artists("") == []

    def test_none_value(self):
        """Test None returns empty list."""
        assert split_artists(None) == []

    def test_single_artist(self):
        """Test single artist returns list with one item."""
        assert split_artists("Taylor Swift") == ["Taylor Swift"]

    def test_comma_separator(self):
        """Test comma separator."""
        assert split_artists("Artist A, Artist B") == ["Artist A", "Artist B"]

    def test_chinese_comma_separator(self):
        """Test Chinese comma separator."""
        assert split_artists("歌手A，歌手B") == ["歌手A", "歌手B"]

    def test_japanese_comma_separator(self):
        """Test Japanese comma separator."""
        assert split_artists("歌手A、歌手B") == ["歌手A", "歌手B"]

    def test_ampersand_separator(self):
        """Test ampersand separator."""
        assert split_artists("Artist A & Artist B") == ["Artist A", "Artist B"]

    def test_slash_separator(self):
        """Test slash separator."""
        assert split_artists("Artist A/Artist B") == ["Artist A", "Artist B"]

    def test_backslash_separator(self):
        """Test backslash separator."""
        assert split_artists("Artist A\\Artist B") == ["Artist A", "Artist B"]

    def test_ft_separator(self):
        """Test ft. separator."""
        assert split_artists("Artist A ft. Artist B") == ["Artist A", "Artist B"]

    def test_ft_without_period(self):
        """Test ft separator without period."""
        assert split_artists("Artist A ft Artist B") == ["Artist A", "Artist B"]

    def test_feat_separator(self):
        """Test feat. separator."""
        assert split_artists("Artist A feat. Artist B") == ["Artist A", "Artist B"]

    def test_featuring_separator(self):
        """Test featuring separator."""
        assert split_artists("Artist A featuring Artist B") == ["Artist A", "Artist B"]

    def test_multiple_artists(self):
        """Test multiple artists with different separators."""
        result = split_artists("Artist A, Artist B & Artist C")
        assert result == ["Artist A", "Artist B", "Artist C"]

    def test_complex_case(self):
        """Test complex artist string."""
        result = split_artists("林俊杰&阿杜&金莎&By2")
        assert len(result) == 4
        assert "林俊杰" in result
        assert "阿杜" in result
        assert "金莎" in result
        assert "By2" in result

    def test_whitespace_handling(self):
        """Test whitespace is stripped."""
        assert split_artists("  Artist A  ,  Artist B  ") == ["Artist A", "Artist B"]

    def test_case_insensitive_ft(self):
        """Test ft. is case-insensitive."""
        assert split_artists("Artist A FT. Artist B") == ["Artist A", "Artist B"]
        assert split_artists("Artist A Ft Artist B") == ["Artist A", "Artist B"]


class TestNormalizeArtistName:
    """Tests for normalize_artist_name function."""

    def test_empty_string(self):
        """Test empty string returns empty."""
        assert normalize_artist_name("") == ""

    def test_none_value(self):
        """Test None returns empty."""
        assert normalize_artist_name(None) == ""

    def test_lowercase_conversion(self):
        """Test name is converted to lowercase."""
        assert normalize_artist_name("Taylor Swift") == "taylor swift"

    def test_case_insensitive_matching(self):
        """Test different cases normalize to same value."""
        assert normalize_artist_name("Taylor Swift") == normalize_artist_name("TAYLOR SWIFT")
        assert normalize_artist_name("Taylor Swift") == normalize_artist_name("taylor swift")

    def test_whitespace_stripped(self):
        """Test whitespace is stripped."""
        assert normalize_artist_name("  Taylor Swift  ") == "taylor swift"


class TestGetCanonicalArtistName:
    """Tests for get_canonical_artist_name function."""

    def test_empty_list(self):
        """Test empty list returns empty string."""
        assert get_canonical_artist_name([]) == ""

    def test_none_value(self):
        """Test None returns empty string."""
        assert get_canonical_artist_name(None) == ""

    def test_single_artist(self):
        """Test single artist returns the name."""
        assert get_canonical_artist_name(["Taylor Swift"]) == "Taylor Swift"

    def test_multiple_artists(self):
        """Test multiple artists are joined with comma."""
        assert get_canonical_artist_name(["Artist A", "Artist B"]) == "Artist A, Artist B"

    def test_three_artists(self):
        """Test three artists are properly joined."""
        result = get_canonical_artist_name(["A", "B", "C"])
        assert result == "A, B, C"
