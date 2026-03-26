"""
Artist parsing service for splitting and normalizing artist names.
"""

import re
from typing import List


# Separators for splitting artist strings
# Order matters: longer patterns first to avoid partial matches
ARTIST_SEPARATORS = [
    r'\s+feat\.?\s+',      # feat., feat
    r'\s+featuring\s+',    # featuring
    r'\s+ft\.?\s+',        # ft., ft
    r'\s*[,，、]\s*',      # commas (English, Chinese, Japanese)
    r'\s*[/\\]\s*',        # slashes
    r'\s*&\s*',            # ampersand
    r'\s+and\s+',          # and (with spaces to avoid matching "Anderson")
]

# Compile pattern once
_SEPARATOR_PATTERN = '|'.join(f'({sep})' for sep in ARTIST_SEPARATORS)
_SPLIT_REGEX = re.compile(_SEPARATOR_PATTERN, re.IGNORECASE)


def split_artists(artist_string: str) -> List[str]:
    """
    Split an artist string into individual artist names.

    Handles common separators:
    - Commas: "Artist A, Artist B"
    - Chinese commas: "歌手A，歌手B"
    - Ampersand: "Artist A & Artist B"
    - Slashes: "Artist A/Artist B"
    - Featuring: "Artist A ft. Artist B", "Artist A feat. Artist B"

    Args:
        artist_string: The artist string to split

    Returns:
        List of individual artist names, stripped of whitespace
    """
    if not artist_string:
        return []

    # Split using the compiled regex
    parts = _SPLIT_REGEX.split(artist_string)

    # Filter out None values and separators, keep only artist names
    artists = []
    for part in parts:
        if part is None:
            continue
        part = part.strip()
        # Skip if it's a separator pattern
        if not part:
            continue
        # Check if this part looks like a separator
        if re.match(r'^[\s,，、/\\&]+$', part, re.IGNORECASE):
            continue
        if re.match(r'^(feat\.?|featuring|ft\.?|and)$', part, re.IGNORECASE):
            continue
        artists.append(part)

    return artists


def normalize_artist_name(artist_name: str) -> str:
    """
    Normalize artist name for case-insensitive matching.

    Args:
        artist_name: The artist name to normalize

    Returns:
        Lowercase version of the name for comparison
    """
    if not artist_name:
        return ""
    return artist_name.lower().strip()


def get_canonical_artist_name(artists: List[str]) -> str:
    """
    Get canonical display string for multiple artists.

    Args:
        artists: List of artist names

    Returns:
        Comma-separated string of artists
    """
    if not artists:
        return ""
    return ", ".join(artists)
