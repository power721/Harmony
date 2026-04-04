"""
Tests for intelligent track deduplication utility.
"""

import pytest
from domain import PlaylistItem
from domain.track import TrackSource
from utils.dedup import (
    extract_version_info,
    get_track_key,
    deduplicate_playlist_items,
    deduplicate_playlist_items_strict,
    get_version_summary,
    VersionInfo,
)


class TestVersionInfo:
    """Test VersionInfo class and priority scoring."""

    def test_original_version_priority(self):
        """Test original version has highest priority."""
        info = extract_version_info("Song")
        assert info.priority_score == 100
        assert not info.is_live
        assert not info.has_instrumental
        assert not info.has_harmony

    def test_live_version_priority(self):
        """Test live version has second highest priority."""
        info = extract_version_info("Song Live")
        assert info.priority_score == 80
        assert info.is_live
        assert not info.has_instrumental

    def test_instrumental_version_priority(self):
        """Test instrumental version has lower priority."""
        info = extract_version_info("Song Instrumental")
        assert info.priority_score == 60
        assert info.has_instrumental
        assert not info.is_live

    def test_live_instrumental_priority(self):
        """Test live instrumental has even lower priority."""
        info = extract_version_info("Song Live Instrumental")
        assert info.priority_score == 40
        assert info.is_live
        assert info.has_instrumental

    def test_harmony_instrumental_priority(self):
        """Test harmony instrumental has lowest priority."""
        info = extract_version_info("Song Harmony Instrumental")
        assert info.priority_score == 20
        assert info.has_harmony

    def test_extract_base_title(self):
        """Test extracting base title without markers."""
        info = extract_version_info("Song Harmony Instrumental")
        assert info.base_title == "Song"

    def test_various_marker_formats(self):
        """Test various marker format variations."""
        # Parentheses format
        info = extract_version_info("song (伴奏)")
        assert info.has_instrumental

        # Bracket format
        info = extract_version_info("song [伴奏]")
        assert info.has_instrumental

        # Mixed case
        info = extract_version_info("song (Live)")
        assert info.is_live

        # No spaces
        info = extract_version_info("song(live)")
        assert info.is_live


class TestGetTrackKey:
    """Test track key generation for grouping."""

    def test_key_with_artist_and_title(self):
        """Test key generation with standard format."""
        item = PlaylistItem(
            title="Song Title",
            artist="Artist Name",
        )
        key = get_track_key(item)
        assert key == "Artist Name - Song Title"

    def test_key_normalizes_base_title(self):
        """Test key normalization removes version markers."""
        item = PlaylistItem(
            title="Song Title (伴奏)",
            artist="Artist Name",
        )
        key = get_track_key(item)
        # Should use base title, not full title
        assert "Song Title" in key
        assert "伴奏" not in key

    def test_key_handles_missing_artist(self):
        """Test key handles missing artist."""
        item = PlaylistItem(
            title="Song Title",
            artist="",
        )
        key = get_track_key(item)
        assert "Unknown Artist" in key

    def test_key_groups_similar_versions(self):
        """Test that different versions get same key."""
        items = [
            PlaylistItem(title="Song", artist="Artist"),
            PlaylistItem(title="Song (伴奏)", artist="Artist"),
            PlaylistItem(title="Song (和声伴奏)", artist="Artist"),
        ]

        keys = [get_track_key(item) for item in items]
        # All should have the same key
        assert len(set(keys)) == 1


class TestDeduplicatePlaylistItems:
    """Test main deduplication function."""

    def test_keeps_original_over_versions(self):
        """Test keeps original when versions exist."""
        items = [
            PlaylistItem(title="Song Instrumental", artist="Artist"),
            PlaylistItem(title="Song Harmony Instrumental", artist="Artist"),
            PlaylistItem(title="Song", artist="Artist"),
        ]

        result = deduplicate_playlist_items(items)
        assert len(result) == 1
        assert result[0].title == "Song"

    def test_keeps_live_when_no_original(self):
        """Test keeps live version when no original exists."""
        items = [
            PlaylistItem(title="Song Live Instrumental", artist="Artist"),
            PlaylistItem(title="Song Live Harmony Instrumental", artist="Artist"),
            PlaylistItem(title="Song Live", artist="Artist"),
        ]

        result = deduplicate_playlist_items(items)
        assert len(result) == 1
        assert result[0].title == "Song Live"

    def test_complex_example_from_user(self):
        """Test the complex example from user requirements."""
        items = [
            PlaylistItem(title="Song Live", artist="Artist"),
            PlaylistItem(title="Song Live Instrumental", artist="Artist"),
            PlaylistItem(title="Song Instrumental", artist="Artist"),
            PlaylistItem(title="Song", artist="Artist"),
        ]

        result = deduplicate_playlist_items(items)
        assert len(result) == 1
        # Should keep the original version
        assert result[0].title == "Song"

    def test_preserves_order(self):
        """Test that original order is preserved."""
        items = [
            PlaylistItem(title="Song A", artist="Artist 1"),
            PlaylistItem(title="Song B Instrumental", artist="Artist 2"),
            PlaylistItem(title="Song B", artist="Artist 2"),
            PlaylistItem(title="Song C", artist="Artist 3"),
        ]

        result = deduplicate_playlist_items(items)
        assert len(result) == 3
        assert result[0].title == "Song A"
        assert result[1].title == "Song B"
        assert result[2].title == "Song C"

    def test_no_duplicates_returns_same(self):
        """Test that items without duplicates are returned as-is."""
        items = [
            PlaylistItem(title="Song A", artist="Artist 1"),
            PlaylistItem(title="Song B", artist="Artist 2"),
            PlaylistItem(title="Song C", artist="Artist 3"),
        ]

        result = deduplicate_playlist_items(items)
        assert len(result) == 3
        assert result == items

    def test_empty_list(self):
        """Test handling empty list."""
        result = deduplicate_playlist_items([])
        assert result == []

    def test_different_artists_not_deduplicated(self):
        """Test that different artists with same song title are not deduplicated."""
        items = [
            PlaylistItem(title="Song", artist="Artist A"),
            PlaylistItem(title="Song Instrumental", artist="Artist B"),
        ]

        result = deduplicate_playlist_items(items)
        # Different artists, so no deduplication
        assert len(result) == 2

    def test_handles_cloud_and_local(self):
        """Test handling both cloud and local items."""
        items = [
            PlaylistItem(
                source=TrackSource.LOCAL,
                title="Song",
                artist="Artist",
                local_path="/local/song.flac",
            ),
            PlaylistItem(
                source=TrackSource.QUARK,
                title="Song Instrumental",
                artist="Artist",
                cloud_file_id="cloud123",
            ),
        ]

        result = deduplicate_playlist_items(items)
        assert len(result) == 1
        assert result[0].title == "Song"

    def test_uses_local_filename_markers_when_titles_are_same(self):
        """Should use local filename markers when metadata titles are identical."""
        items = [
            PlaylistItem(
                source=TrackSource.LOCAL,
                title="11次心跳",
                artist="火箭少女101",
                local_path="/music/火箭少女101 - 11次心跳 (伴奏)[putaojie.com].flac",
            ),
            PlaylistItem(
                source=TrackSource.LOCAL,
                title="11次心跳",
                artist="火箭少女101",
                local_path="/music/火箭少女101 - 11次心跳[putaojie.com].flac",
            ),
        ]

        result = deduplicate_playlist_items(items)
        assert len(result) == 1
        assert result[0].local_path.endswith("火箭少女101 - 11次心跳[putaojie.com].flac")


class TestDeduplicatePlaylistItemsStrict:
    """Test strict deduplication (remove ALL versions)."""

    def test_removes_all_versions(self):
        """Test that all versioned items are removed."""
        items = [
            PlaylistItem(title="Song", artist="Artist"),
            PlaylistItem(title="Song Instrumental", artist="Artist"),
            PlaylistItem(title="Song Live Instrumental", artist="Artist"),
        ]

        result = deduplicate_playlist_items_strict(items)
        assert len(result) == 1
        assert result[0].title == "Song"

    def test_removes_all_when_no_original(self):
        """Test that all items are removed when no original exists."""
        items = [
            PlaylistItem(title="Song Live", artist="Artist"),
            PlaylistItem(title="Song Instrumental", artist="Artist"),
        ]

        result = deduplicate_playlist_items_strict(items)
        # Both have markers, so all removed
        assert len(result) == 0


class TestDeduplicateKeepsFirst:
    """Test that deduplication keeps the first item when priorities are equal."""

    def test_keeps_first_when_same_priority(self):
        """Test keeps first item when multiple items have same priority."""
        items = [
            PlaylistItem(title="Song (伴奏)", artist="Artist"),
            PlaylistItem(title="Song (Karaoke)", artist="Artist"),
        ]
        # Both have instrumental marker, same priority (60)
        result = deduplicate_playlist_items(items)
        assert len(result) == 1
        # Should keep the first one
        assert result[0].title == "Song (伴奏)"

    def test_keeps_first_live_version(self):
        """Test keeps first live version when multiple live versions exist."""
        items = [
            PlaylistItem(title="Song (Live)", artist="Artist"),
            PlaylistItem(title="Song [Live Version]", artist="Artist"),
        ]
        # Both are live versions, same priority (80)
        result = deduplicate_playlist_items(items)
        assert len(result) == 1
        # Should keep the first one
        assert result[0].title == "Song (Live)"

    def test_user_example_ruge(self):
        """Test the user's specific example: live vs live instrumental."""
        items = [
            PlaylistItem(title="龚琳娜&黄霄雲 - 如歌", artist="龚琳娜&黄霄雲"),
            PlaylistItem(title="龚琳娜&黄霄雲 - 如歌", artist="龚琳娜&黄霄雲"),
        ]
        result = deduplicate_playlist_items(items)
        assert len(result) == 1
        # Live version (80) > Live instrumental (40), should keep first
        assert "live伴奏" not in result[0].title.lower()

    def test_user_example_ta(self):
        """Test another user example: 她 (live) vs 她 (live伴奏)."""
        items = [
            PlaylistItem(title="黄霄雲 - 她 (live)[putaojie.com].flac", artist="黄霄雲"),
            PlaylistItem(title="黄霄雲 - 她 (live伴奏)[putaojie.com].flac", artist="黄霄雲"),
        ]
        result = deduplicate_playlist_items(items)
        assert len(result) == 1
        # Live version (80) > Live instrumental (40), should keep first
        assert result[0].title == "黄霄雲 - 她 (live)[putaojie.com].flac"


class TestGetVersionSummary:
    """Test version statistics function."""

    def test_counts_versions_correctly(self):
        """Test counting different version types."""
        items = [
            PlaylistItem(title="Song 1", artist="Artist"),
            PlaylistItem(title="Song 1 Instrumental", artist="Artist"),
            PlaylistItem(title="Song 2 Live", artist="Artist"),
            PlaylistItem(title="Song 2 Live Instrumental", artist="Artist"),
        ]

        summary = get_version_summary(items)
        assert summary["total"] == 4
        assert summary["original"] == 1
        assert summary["live"] == 1
        assert summary["instrumental"] == 1
        assert summary["live_instrumental"] == 1
        assert summary["groups"] == 2

    def test_empty_summary(self):
        """Test summary of empty list."""
        summary = get_version_summary([])
        assert summary["total"] == 0
        assert summary["groups"] == 0
        assert summary["original"] == 0
