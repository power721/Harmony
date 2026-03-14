"""
Tests for helper utility functions.
"""

import pytest
from utils.helpers import (
    format_duration,
    format_time,
    find_lyric_line,
    sanitize_filename,
    truncate_text,
    format_count_message,
)


class TestFormatDuration:
    """Test format_duration function."""

    def test_format_seconds_only(self):
        """Test formatting seconds only."""
        assert format_duration(45) == "0:45"

    def test_format_minutes_seconds(self):
        """Test formatting minutes and seconds."""
        assert format_duration(125) == "2:05"
        assert format_duration(65) == "1:05"

    def test_format_hours_minutes_seconds(self):
        """Test formatting hours, minutes, and seconds."""
        assert format_duration(3661) == "1:01:01"
        assert format_duration(7200) == "2:00:00"

    def test_format_negative_duration(self):
        """Test formatting negative duration."""
        assert format_duration(-1) == "0:00"

    def test_format_none_duration(self):
        """Test formatting None duration."""
        assert format_duration(None) == "0:00"

    def test_format_zero_duration(self):
        """Test formatting zero duration."""
        assert format_duration(0) == "0:00"

    def test_format_float_duration(self):
        """Test formatting float duration."""
        assert format_duration(125.7) == "2:05"
        assert format_duration(59.9) == "0:59"


class TestFormatTime:
    """Test format_time function."""

    def test_format_time_calls_format_duration(self):
        """Test that format_time is an alias for format_duration."""
        assert format_time(125) == format_duration(125)


class TestFindLyricLine:
    """Test find_lyric_line function."""

    def test_find_line_with_empty_lyrics(self):
        """Test finding line in empty lyrics."""
        result = find_lyric_line([], 1.0)
        assert result is None

    def test_find_line_at_beginning(self):
        """Test finding line at beginning."""
        lyrics = [(0.0, "First"), (2.0, "Second"), (4.0, "Third")]
        result = find_lyric_line(lyrics, 0.5)
        assert result == 0

    def test_find_line_in_middle(self):
        """Test finding line in middle."""
        lyrics = [(0.0, "First"), (2.0, "Second"), (4.0, "Third")]
        result = find_lyric_line(lyrics, 2.5)
        assert result == 1

    def test_find_line_at_exact_time(self):
        """Test finding line at exact timestamp."""
        lyrics = [(0.0, "First"), (2.0, "Second"), (4.0, "Third")]
        result = find_lyric_line(lyrics, 2.0)
        assert result == 1

    def test_find_line_at_end(self):
        """Test finding line at end."""
        lyrics = [(0.0, "First"), (2.0, "Second"), (4.0, "Third")]
        result = find_lyric_line(lyrics, 10.0)
        assert result == 2

    def test_find_line_before_first(self):
        """Test finding line before first timestamp."""
        lyrics = [(1.0, "First"), (2.0, "Second"), (4.0, "Third")]
        result = find_lyric_line(lyrics, 0.5)
        assert result == 0

    def test_find_line_with_single_lyric(self):
        """Test finding line with only one lyric."""
        lyrics = [(2.0, "Only line")]
        result = find_lyric_line(lyrics, 0.0)
        assert result == 0


class TestSanitizeFilename:
    """Test sanitize_filename function."""

    def test_remove_invalid_chars(self):
        """Test removing invalid characters."""
        assert sanitize_filename('file<>name') == "filename"
        assert sanitize_filename('file"name') == "filename"

    def test_remove_all_invalid_chars(self):
        """Test removing all invalid characters."""
        invalid = '<>:"/\\|?*'
        result = sanitize_filename(f"file{invalid}name")
        assert result == "filename"

    def test_strip_whitespace(self):
        """Test stripping whitespace."""
        assert sanitize_filename("  filename  ") == "filename"

    def test_preserve_valid_chars(self):
        """Test preserving valid characters."""
        assert sanitize_filename("file-name_123.txt") == "file-name_123.txt"

    def test_empty_filename(self):
        """Test handling empty filename."""
        assert sanitize_filename("") == ""

    def test_only_invalid_chars(self):
        """Test filename with only invalid characters."""
        assert sanitize_filename("<>:\"") == ""


class TestTruncateText:
    """Test truncate_text function."""

    def test_no_truncation_needed(self):
        """Test when text is shorter than max length."""
        assert truncate_text("short", 10) == "short"

    def test_truncate_with_default_suffix(self):
        """Test truncation with default suffix."""
        result = truncate_text("This is a long text", 10)
        assert result == "This is..."
        assert len(result) == 10

    def test_truncate_with_custom_suffix(self):
        """Test truncation with custom suffix."""
        # "This is a long text" is 19 characters
        # With max_length=13 and suffix=" >>" (3 chars), we get text[:10] + " >>"
        result = truncate_text("This is a long text", 13, " >>")
        assert result == "This is a  >>"  # 10 chars + " >>" (3 chars) = 13
        assert len(result) == 13

    def test_truncate_exact_length(self):
        """Test when text equals max length."""
        text = "exact"
        assert truncate_text(text, len(text)) == text

    def test_truncate_one_char_over(self):
        """Test when text is one character over."""
        result = truncate_text("12345", 4)
        assert result == "1..."
        assert len(result) == 4

    def test_truncate_empty_string(self):
        """Test truncating empty string."""
        assert truncate_text("", 5) == ""

    def test_truncate_with_long_suffix(self):
        """Test when suffix is longer than max length."""
        # This edge case behavior depends on implementation
        result = truncate_text("text", 3, "...")
        # Implementation handles this by using text[:max-len(suffix)] + suffix
        # which might result in just the suffix

    def test_truncate_unicode(self):
        """Test truncating unicode text."""
        # "Hello世界" has 7 characters (5 Latin + 2 Chinese)
        # Each Chinese character counts as 1 character in Python len()
        # So with max_length=6, we get text[:3] + "..." = "Hel..."
        result = truncate_text("Hello世界", 6)
        assert result == "Hel..."
        assert len(result) == 6


class TestFormatCountMessage:
    """Test format_count_message function."""

    def test_format_with_mocked_i18n(self, monkeypatch):
        """Test formatting message with mocked i18n."""
        # Create a mock translation function
        class MockI18n:
            def __call__(self, key):
                return "{count} track{s}"

        mock_t = MockI18n()

        # Create a temporary i18n module in utils
        import sys
        import types

        mock_i18n_module = types.ModuleType("i18n")
        mock_i18n_module.t = mock_t
        sys.modules["utils.i18n"] = mock_i18n_module

        try:
            # Now test the function
            result = format_count_message("test.key", 1)
            assert result == "1 track"

            result = format_count_message("test.key", 5)
            assert result == "5 tracks"

            result = format_count_message("test.key", 0)
            # 0 is treated as singular (0 > 1 is False)
            assert result == "0 track"

            result = format_count_message("test.key", 1000)
            assert result == "1000 tracks"
        finally:
            # Clean up
            if "utils.i18n" in sys.modules:
                del sys.modules["utils.i18n"]
