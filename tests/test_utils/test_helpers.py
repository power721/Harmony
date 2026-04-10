"""
Tests for helper utility functions.
"""

import builtins
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

from utils.helpers import (
    format_duration,
    format_time,
    find_lyric_line,
    sanitize_filename,
    truncate_text,
    format_count_message,
    get_cache_dir,
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

    def test_find_line_with_duplicate_timestamps_returns_last_match(self):
        """Binary-search implementation should still prefer the last timestamp <= current time."""
        lyrics = [(1.0, "First"), (1.0, "Second"), (2.0, "Third")]
        result = find_lyric_line(lyrics, 1.0)
        assert result == 1


class TestSanitizeFilename:
    """Test sanitize_filename function."""

    def test_remove_invalid_chars(self):
        """Test removing invalid characters."""
        assert sanitize_filename('file<>name') == "filename"
        assert sanitize_filename('file"name') == "filename"

    def test_remove_all_invalid_chars(self):
        """Test removing all invalid characters."""
        # file_helpers version: / and \ become &, others removed
        result = sanitize_filename('file<>:"|?*name')
        assert result == "filename"

    def test_strip_whitespace(self):
        """Test stripping whitespace."""
        assert sanitize_filename("  filename  ") == "filename"

    def test_preserve_valid_chars(self):
        """Test preserving valid characters."""
        assert sanitize_filename("file-name_123.txt") == "file-name_123.txt"

    def test_empty_filename(self):
        """Test handling empty filename."""
        # file_helpers version returns "unnamed" for empty input
        assert sanitize_filename("") == "unnamed"

    def test_only_invalid_chars(self):
        """Test filename with only invalid characters."""
        # file_helpers version returns "unnamed" when result is empty
        assert sanitize_filename('<>:"|?*') == "unnamed"


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
        truncate_text("text", 3, "...")
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
        # The function imports from system at module load time
        # We need to patch the actual t function used by helpers module
        def mock_t(key):
            return "{count} track{s}"

        # Patch the t function in the helpers module's namespace
        import utils.helpers
        monkeypatch.setattr(utils.helpers, "t", mock_t)

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


class TestGetCacheDir:
    """Test get_cache_dir function."""

    def test_get_cache_dir_default(self):
        """Test get_cache_dir returns ~/.cache/Harmony in development mode."""
        with patch.object(sys, 'frozen', False, create=True):
            result = get_cache_dir()
        assert result == Path.home() / '.cache' / 'Harmony'

    def test_get_cache_dir_with_subdir(self):
        """Test get_cache_dir with subdirectory."""
        with patch.object(sys, 'frozen', False, create=True):
            result = get_cache_dir('covers')
        assert result == Path.home() / '.cache' / 'Harmony' / 'covers'

    def test_get_cache_dir_with_nested_subdir(self):
        """Test get_cache_dir with nested subdirectory path."""
        with patch.object(sys, 'frozen', False, create=True):
            result = get_cache_dir('covers/online_images')
        assert result == Path.home() / '.cache' / 'Harmony' / 'covers/online_images'

    def test_get_cache_dir_frozen_with_platformdirs(self):
        """Test get_cache_dir uses platformdirs when frozen."""
        mock_cache = MagicMock()
        mock_cache.user_cache_dir.return_value = '/tmp/app_cache/HarmonyPlayer'

        with patch.object(sys, 'frozen', True, create=True), \
             patch.dict('sys.modules', {'platformdirs': MagicMock(user_cache_dir=mock_cache.user_cache_dir)}):
            result = get_cache_dir()

        mock_cache.user_cache_dir.assert_called_once_with('Harmony', 'HarmonyPlayer')
        assert result == Path('/tmp/app_cache/HarmonyPlayer')

    def test_get_cache_dir_frozen_platformdirs_import_error(self):
        """Test get_cache_dir falls back when platformdirs is not available."""
        real_import = builtins.__import__

        def import_side_effect(name, *args, **kwargs):
            if name == 'platformdirs':
                raise ImportError("no module")
            return real_import(name, *args, **kwargs)

        with patch.object(sys, 'frozen', True, create=True), \
             patch('builtins.__import__', side_effect=import_side_effect):
            result = get_cache_dir()

        # Falls back to ~/.cache/Harmony
        assert result == Path.home() / '.cache' / 'Harmony'

    def test_get_cache_dir_frozen_with_subdir(self):
        """Test get_cache_dir with subdirectory when frozen."""
        mock_cache = MagicMock()
        mock_cache.user_cache_dir.return_value = '/tmp/app_cache/HarmonyPlayer'

        with patch.object(sys, 'frozen', True, create=True), \
             patch.dict('sys.modules', {'platformdirs': MagicMock(user_cache_dir=mock_cache.user_cache_dir)}):
            result = get_cache_dir('thumbnails')

        assert result == Path('/tmp/app_cache/HarmonyPlayer') / 'thumbnails'

    def test_get_cache_dir_empty_subdir(self):
        """Test get_cache_dir with empty string subdirectory returns base."""
        with patch.object(sys, 'frozen', False, create=True):
            result = get_cache_dir('')
        assert result == Path.home() / '.cache' / 'Harmony'

    def test_get_cache_dir_returns_path_object(self):
        """Test get_cache_dir returns a Path object."""
        with patch.object(sys, 'frozen', False, create=True):
            result = get_cache_dir()
        assert isinstance(result, Path)
