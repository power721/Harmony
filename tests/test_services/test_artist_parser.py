"""Tests for artist_parser module."""

import pytest
from services.metadata.artist_parser import (
    split_artists,
    normalize_artist_name,
    get_canonical_artist_name,
    _try_split_by_known,
    split_artists_aware,
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


class TestTrySplitByKnown:
    """Tests for _try_split_by_known function."""

    def test_no_space_returns_original(self):
        """Test single word returns as-is."""
        assert _try_split_by_known("周杰伦", {"周杰伦"}) == ["周杰伦"]

    def test_space_separated_both_known(self):
        """Test splitting when both parts are known artists."""
        assert _try_split_by_known("周杰伦 费玉清", {"周杰伦", "费玉清"}) == ["周杰伦", "费玉清"]

    def test_space_separated_one_known(self):
        """Test splitting when only one part is a known artist and rest are single words."""
        # "周杰伦" is known, "未知名" is a single word -> accepted split
        assert _try_split_by_known("周杰伦 未知名", {"周杰伦"}) == ["周杰伦", "未知名"]

    def test_space_separated_none_known(self):
        """Test no split when neither part is known."""
        assert _try_split_by_known("未知甲 未知乙", {"周杰伦", "费玉清"}) == ["未知甲 未知乙"]

    def test_no_known_artists_set_empty(self):
        """Test with empty known artists set."""
        assert _try_split_by_known("A B", set()) == ["A B"]

    def test_three_space_separated_all_known(self):
        """Test splitting three space-separated known artists."""
        assert _try_split_by_known(
            "周杰伦 费玉清 陈奕迅",
            {"周杰伦", "费玉清", "陈奕迅"}
        ) == ["周杰伦", "费玉清", "陈奕迅"]

    def test_partial_match_with_single_word_remaining_splits(self):
        """Test that a known match with single-word remaining causes a split."""
        # "周杰伦" is known, "Unknown" is single word -> accepted split
        assert _try_split_by_known("周杰伦 Unknown", {"周杰伦"}) == ["周杰伦", "Unknown"]

    def test_empty_string(self):
        """Test empty string."""
        assert _try_split_by_known("", {"周杰伦"}) == [""]

    def test_greedy_vs_shorter_match(self):
        """Test that shorter known match is preferred over longer."""
        # "周杰伦 费玉清" - if full string "周杰伦 费玉清" is known AND "周杰伦" is known,
        # shorter match should be preferred (greedy starts from j=i+1, shortest first)
        assert _try_split_by_known(
            "周杰伦 费玉清",
            {"周杰伦", "费玉清", "周杰伦 费玉清"}
        ) == ["周杰伦", "费玉清"]

    def test_case_insensitive_matching(self):
        """Test that known artist matching is case-insensitive (normalized)."""
        assert _try_split_by_known("taylor swift", {"taylor swift"}) == ["taylor swift"]

    def test_result_with_single_element_returns_original(self):
        """Test that single-element result returns original string."""
        # "A B" where "A B" is known as a single entity
        assert _try_split_by_known("A B", {"a b"}) == ["A B"]


class TestSplitArtistsAware:
    """Tests for split_artists_aware function."""

    def test_no_known_artists(self):
        """Test behaves like split_artists when no known_artists provided."""
        result = split_artists_aware("Artist A, Artist B")
        assert result == ["Artist A", "Artist B"]

    def test_none_known_artists(self):
        """Test behaves like split_artists when known_artists is None."""
        result = split_artists_aware("Artist A, Artist B", known_artists=None)
        assert result == ["Artist A", "Artist B"]

    def test_empty_known_artists(self):
        """Test with empty known artists set."""
        result = split_artists_aware("Artist A, Artist B", known_artists=set())
        assert result == ["Artist A", "Artist B"]

    def test_space_splitting_with_known(self):
        """Test space-separated artists are split when known."""
        known = {"周杰伦", "费玉清"}
        result = split_artists_aware("周杰伦 费玉清", known_artists=known)
        assert result == ["周杰伦", "费玉清"]

    def test_comma_and_space_splitting(self):
        """Test both comma and space splitting work together."""
        known = {"周杰伦", "费玉清", "陈奕迅"}
        result = split_artists_aware("周杰伦, 费玉清 陈奕迅", known_artists=known)
        assert result == ["周杰伦", "费玉清", "陈奕迅"]

    def test_no_space_in_parts_no_additional_split(self):
        """Test that artists without spaces are not further split."""
        known = {"artist a"}
        result = split_artists_aware("Artist B, Artist C", known_artists=known)
        assert result == ["Artist B", "Artist C"]

    def test_unknown_space_separated_not_split(self):
        """Test that unknown space-separated names are not split."""
        known = {"周杰伦"}
        result = split_artists_aware("Unknown Artist Name", known_artists=known)
        assert result == ["Unknown Artist Name"]

    def test_complex_mixed_separators(self):
        """Test complex string with multiple separator types and known artists."""
        known = {"周杰伦", "费玉清"}
        result = split_artists_aware("周杰伦&费玉清 ft. Other Artist", known_artists=known)
        assert "周杰伦" in result
        assert "费玉清" in result
        assert "Other Artist" in result

    def test_empty_string(self):
        """Test empty string returns empty list."""
        assert split_artists_aware("") == []

    def test_feat_separator_with_known(self):
        """Test feat separator splits correctly with known artists."""
        known = {"main artist", "featured artist"}
        result = split_artists_aware("Main Artist feat. Featured Artist", known_artists=known)
        assert result == ["Main Artist", "Featured Artist"]
