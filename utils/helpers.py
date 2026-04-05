"""
Helper utility functions for the music player.
"""
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple, Optional

from system import t

# Pre-compiled regex patterns for filename metadata parsing
_RE_ARTIST_TITLE = re.compile(r'^(.+?)\s*-\s*(.+)$')
_RE_BRACKETS = re.compile(r'\[[^\]]+\]')
_RE_PARENTHESES = re.compile(r'\([^)]*\)')


def get_cache_dir(subdir: str = '') -> Path:
    """
    Get the cache directory for the application.

    Uses platformdirs when running as a frozen executable (AppImage/PyInstaller)
    for proper cross-platform cache directory resolution.
    Falls back to ~/.cache/Harmony for development mode.

    Args:
        subdir: Optional subdirectory name (e.g., 'covers', 'online_images')

    Returns:
        Path to the cache directory
    """
    if getattr(sys, 'frozen', False):
        try:
            import platformdirs
            cache_dir = Path(platformdirs.user_cache_dir('Harmony', 'HarmonyPlayer'))
        except ImportError:
            cache_dir = Path.home() / '.cache' / 'Harmony'
    else:
        cache_dir = Path.home() / '.cache' / 'Harmony'

    if subdir:
        cache_dir = cache_dir / subdir

    return cache_dir


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
    # Re-export from file_helpers for backward compatibility
    from utils.file_helpers import sanitize_filename as _sanitize
    return _sanitize(filename)


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


def parse_filename_as_metadata(filename: str) -> Tuple[str, str]:
    """
    Parse a filename to extract artist and title.

    Common formats:
    - "Artist - Title.flac"
    - "Artist - Title (伴奏).flac"
    - "Artist - Title[网站].flac"

    Args:
        filename: The filename (with or without extension)

    Returns:
        Tuple of (artist, title) - may be empty strings if parsing fails
    """
    # Remove extension if present
    name = Path(filename).stem

    # Pattern: "Artist - Title" with optional suffix like "(伴奏)" or "[网站]"
    # Common separator: " - " or "-"
    match = _RE_ARTIST_TITLE.match(name)

    if match:
        artist = match.group(1).strip()
        title = match.group(2).strip()

        # Clean common suffixes from title
        # Remove content in brackets like [putaojie.com], [www.xxx.com]
        title = _RE_BRACKETS.sub('', title).strip()
        # Remove content in parentheses like (伴奏), (Inst.)
        title = _RE_PARENTHESES.sub('', title).strip()

        return artist, title

    return "", name  # Return filename as title if no pattern match


def is_filename_like(title: str) -> bool:
    """
    Check if a title looks like a filename rather than proper metadata.

    Args:
        title: The title to check

    Returns:
        True if it looks like a filename
    """
    if not title:
        return False

    # Common file extensions
    extensions = ['.mp3', '.flac', '.m4a', '.wav', '.ogg', '.wma', '.ape', '.aac', '.opus']
    title_lower = title.lower()
    if any(title_lower.endswith(ext) for ext in extensions):
        return True

    # Check for common filename patterns like [网站], (伴奏) at the end
    return bool('[' in title and ']' in title)


def format_relative_time(dt: datetime) -> str:
    """
    Format datetime as relative time string.

    Args:
        dt: The datetime to format (assumed to be in UTC if timezone-naive)

    Returns:
        Relative time string like "刚刚", "5分钟前", "2小时前", "昨天", "3天前", "2024-03-30"
    """
    if not dt:
        return ""

    # If datetime is timezone-naive, assume it's UTC and add 8 hours for Beijing time
    if dt.tzinfo is None:
        # UTC to Beijing (UTC+8)
        dt_local = dt + timedelta(hours=8)
    else:
        # If it has timezone, convert to local
        from datetime import timezone
        local_offset = timedelta(hours=8)  # Beijing timezone
        dt_local = dt.astimezone(timezone(local_offset))

    # Use current time in same timezone
    now = datetime.utcnow() + timedelta(hours=8)
    delta = now - dt_local

    # Make sure delta is not negative (future time)
    if delta.total_seconds() < 0:
        return "刚刚"

    # Less than 1 minute
    if delta < timedelta(minutes=1):
        return "刚刚"

    # Less than 1 hour
    if delta < timedelta(hours=1):
        minutes = int(delta.total_seconds() / 60)
        return f"{minutes}分钟前"

    # Less than 24 hours
    if delta < timedelta(hours=24):
        hours = int(delta.total_seconds() / 3600)
        return f"{hours}小时前"

    # Yesterday (within 48 hours)
    if delta < timedelta(hours=48):
        return "昨天"

    # Within 7 days
    if delta < timedelta(days=7):
        days = int(delta.total_seconds() / 86400)
        return f"{days}天前"

    # Older: show date
    return dt_local.strftime("%Y-%m-%d")
