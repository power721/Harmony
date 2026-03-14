"""
Helper utility functions for the music player.
"""
from typing import List, Tuple, Optional

from system import t


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to MM:SS or HH:MM:SS format.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string
    """
    if seconds is None or seconds < 0:
        return "0:00"

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_time(seconds: float) -> str:
    """
    Format time in seconds for display.

    Args:
        seconds: Time in seconds

    Returns:
        Formatted time string
    """
    return format_duration(seconds)


def find_lyric_line(lyrics: List[Tuple[float, str]], current_time: float) -> Optional[int]:
    """
    Find the current lyric line index based on time.

    Args:
        lyrics: List of (time, text) tuples
        current_time: Current playback time in seconds

    Returns:
        Index of current lyric line, or None if no match
    """
    if not lyrics:
        return None

    for i, (time, _) in enumerate(lyrics):
        if time > current_time:
            return i - 1 if i > 0 else 0

    return len(lyrics) - 1


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing invalid characters.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    # Remove invalid characters for filenames
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '')
    return filename.strip()


def truncate_text(text: str, max_length: int, suffix: str = '...') -> str:
    """
    Truncate text to maximum length with suffix.

    Args:
        text: Original text
        max_length: Maximum length
        suffix: Suffix to add when truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def format_count_message(key: str, count: int) -> str:
    """
    Format a message with count and plural form.

    Args:
        key: Translation key
        count: Count for pluralization

    Returns:
        Formatted message string
    """

    template = t(key)
    plural_suffix = 's' if count > 1 else ''

    return template.format(count=count, s=plural_suffix)
