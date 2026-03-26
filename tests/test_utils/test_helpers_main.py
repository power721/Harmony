"""
Tests for helpers utility functions.
"""

import pytest
from unittest.mock import patch, MagicMock

from utils.helpers import (
    format_duration,
    format_time,
    find_lyric_line,
    truncate_text,
    format_count_message,
    parse_filename_as_metadata,
    is_filename_like,
)


class TestFormatDuration:
    """Test format_duration function."""

    def test_format_duration_zero(self):
        """Test formatting zero seconds."""
        assert format_duration(0) == "0:00"

    def test_format_duration_seconds_only(self):
        """Test formatting less than a minute."""
        assert format_duration(45) == "0:45"

    def test_format_duration_minutes_only(self):
        """Test formatting minutes and seconds."""
        assert format_duration(125) == "2:05"

    def test_format_duration_with_hours(self):
        """Test formatting with hours."""
        assert format_duration(3661) == "1:01:01"

    def test_format_duration_rounds_down(self):
        """Test that seconds are rounded down."""
        assert format_duration(125.9) == "2:05"

    def test_format_duration_negative(self):
        """Test formatting negative duration."""
        assert format_duration(-10) == "0:00"

    def test_format_duration_none(self):
        """Test formatting None."""
        assert format_duration(None) == "0:00"


class TestFormatTime:
    """Test format_time function."""

    def test_format_time_delegates_to_format_duration(self):
        """Test that format_time delegates to format_duration."""
        assert format_time(125) == format_duration(125)
        assert format_time(3661) == format_duration(3661)


class TestFindLyricLine:
    """Test find_lyric_line function."""

    def test_find_lyric_line_empty_lyrics(self):
        """Test with empty lyrics list."""
        assert find_lyric_line([], 10.0) is None

    def test_find_lyric_line_before_first(self):
        """Test time before first lyric line."""
        lyrics = [(10.0, "Line 1"), (20.0, "Line 2")]
        assert find_lyric_line(lyrics, 5.0) == 0

    def test_find_lyric_line_at_first(self):
        """Test time at first lyric line."""
        lyrics = [(10.0, "Line 1"), (20.0, "Line 2")]
        assert find_lyric_line(lyrics, 10.0) == 0

    def test_find_lyric_line_between(self):
        """Test time between two lines."""
        lyrics = [(10.0, "Line 1"), (20.0, "Line 2")]
        assert find_lyric_line(lyrics, 15.0) == 0

    def test_find_lyric_line_at_second(self):
        """Test time at second lyric line."""
        lyrics = [(10.0, "Line 1"), (20.0, "Line 2")]
        assert find_lyric_line(lyrics, 20.0) == 1

    def test_find_lyric_line_after_last(self):
        """Test time after last lyric line."""
        lyrics = [(10.0, "Line 1"), (20.0, "Line 2")]
        assert find_lyric_line(lyrics, 30.0) == 1

    def test_find_lyric_line_single(self):
        """Test with single lyric line."""
        lyrics = [(10.0, "Only Line")]
        assert find_lyric_line(lyrics, 5.0) == 0
        assert find_lyric_line(lyrics, 15.0) == 0


class TestTruncateText:
    """Test truncate_text function."""

    def test_truncate_no_need(self):
        """Test text shorter than max length."""
        assert truncate_text("Hello", 10) == "Hello"

    def test_truncate_exact_length(self):
        """Test text exactly at max length."""
        assert truncate_text("Hello", 5) == "Hello"

    def test_truncate_needed(self):
        """Test text longer than max length."""
        assert truncate_text("Hello World", 8) == "Hello..."

    def test_truncate_custom_suffix(self):
        """Test with custom suffix."""
        assert truncate_text("Hello World", 8, suffix="…") == "Hello W…"

    def test_truncate_empty_string(self):
        """Test with empty string."""
        assert truncate_text("", 10) == ""


class TestFormatCountMessage:
    """Test format_count_message function."""

    @patch("utils.helpers.t")
    def test_format_count_message_singular(self, mock_t):
        """Test message with count of 1."""
        mock_t.return_value = "{count} item{s}"
        result = format_count_message("items", 1)
        assert result == "1 item"

    @patch("utils.helpers.t")
    def test_format_count_message_plural(self, mock_t):
        """Test message with count greater than 1."""
        mock_t.return_value = "{count} item{s}"
        result = format_count_message("items", 5)
        assert result == "5 items"

    @patch("utils.helpers.t")
    def test_format_count_message_zero(self, mock_t):
        """Test message with count of 0."""
        mock_t.return_value = "{count} item{s}"
        result = format_count_message("items", 0)
        assert result == "0 item"


class TestParseFilenameAsMetadata:
    """Test parse_filename_as_metadata function."""

    def test_parse_standard_format(self):
        """Test parsing 'Artist - Title' format."""
        artist, title = parse_filename_as_metadata("Artist - Song Title.flac")
        assert artist == "Artist"
        assert title == "Song Title"

    def test_parse_with_multiple_spaces(self):
        """Test parsing with extra spaces around separator."""
        artist, title = parse_filename_as_metadata("Artist  -  Song Title.mp3")
        assert artist == "Artist"
        assert title == "Song Title"

    def test_parse_removes_brackets(self):
        """Test that content in brackets is removed from title."""
        artist, title = parse_filename_as_metadata("Artist - Song [website.com].flac")
        assert artist == "Artist"
        assert title == "Song"

    def test_parse_removes_parentheses(self):
        """Test that content in parentheses is removed from title."""
        artist, title = parse_filename_as_metadata("Artist - Song (伴奏).flac")
        assert artist == "Artist"
        assert title == "Song"

    def test_parse_no_separator(self):
        """Test filename without separator returns filename as title."""
        artist, title = parse_filename_as_metadata("SongTitle.flac")
        assert artist == ""
        assert title == "SongTitle"

    def test_parse_without_extension(self):
        """Test parsing filename without extension."""
        artist, title = parse_filename_as_metadata("Artist - Song Title")
        assert artist == "Artist"
        assert title == "Song Title"

    def test_parse_complex_filename(self):
        """Test parsing complex filename."""
        artist, title = parse_filename_as_metadata("Artist Name - Song Title (Inst.) [music.com].flac")
        assert artist == "Artist Name"
        assert title == "Song Title"


class TestIsFilenameLike:
    """Test is_filename_like function."""

    def test_is_filename_like_with_extension(self):
        """Test title that looks like filename with extension."""
        assert is_filename_like("song.mp3") is True
        assert is_filename_like("track.flac") is True
        assert is_filename_like("music.m4a") is True

    def test_is_filename_like_normal_title(self):
        """Test normal title without filename characteristics."""
        assert is_filename_like("My Favorite Song") is False
        assert is_filename_like("Love Story") is False

    def test_is_filename_like_with_brackets(self):
        """Test title with website brackets."""
        assert is_filename_like("Song [website.com]") is True
        assert is_filename_like("Track [www.music.com]") is True

    def test_is_filename_like_empty(self):
        """Test empty string."""
        assert is_filename_like("") is False

    def test_is_filename_like_none(self):
        """Test None value."""
        assert is_filename_like(None) is False

    def test_is_filename_like_case_insensitive(self):
        """Test extension matching is case insensitive."""
        assert is_filename_like("song.MP3") is True
        assert is_filename_like("track.FLAC") is True
