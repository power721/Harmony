"""
Artist parsing service for splitting and normalizing artist names.
"""

import re
from typing import List, Optional, Set


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

# Pre-compiled regex patterns for filtering
_RE_SEPARATOR_PATTERN = re.compile(r'^[\s,，、/\\&]+$', re.IGNORECASE)
_RE_FEAT_PATTERN = re.compile(r'^(feat\.?|featuring|ft\.?|and)$', re.IGNORECASE)


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
        if _RE_SEPARATOR_PATTERN.match(part):
            continue
        if _RE_FEAT_PATTERN.match(part):
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


def _try_split_by_known(artist_name: str, known_artists: Set[str]) -> List[str]:
    """
    Try to split an artist name by spaces using known artists as reference.

    Uses greedy matching that prefers shorter known matches over longer ones
    when a split is possible. For example, "周杰伦 费玉清" splits into
    ["周杰伦", "费玉清"] if "周杰伦" is known, even if the full string is
    also in the known set.

    Accepts the split if at least one part matched a known artist and all
    unmatched parts are single words (no spaces).

    Args:
        artist_name: The artist name that may contain multiple space-separated artists
        known_artists: Set of normalized (lowercase) artist names

    Returns:
        List of artist names, split if conditions met, otherwise original
    """
    if ' ' not in artist_name:
        return [artist_name]

    parts = artist_name.split(' ')
    result = []
    i = 0
    matched_count = 0

    while i < len(parts):
        matched = False
        # Try from shortest to longest: prefer shorter matches to allow
        # more splits (handles "周杰伦 费玉清" where full string is known)
        for j in range(i + 1, len(parts) + 1):
            candidate = ' '.join(parts[i:j])
            if normalize_artist_name(candidate) in known_artists:
                result.append(candidate)
                i = j
                matched = True
                matched_count += 1
                break
        if not matched:
            # No match found — collect remaining words as individual candidates
            for k in range(i, len(parts)):
                result.append(parts[k])
            break

    if len(result) <= 1:
        return [artist_name]

    # Accept split if all parts are single words (no spaces)
    all_single_word = all(' ' not in part for part in result)
    if matched_count > 0 and all_single_word:
        return result

    # Accept split if all parts matched known artists
    if matched_count == len(result):
        return result

    return [artist_name]


def split_artists_aware(artist_string: str, known_artists: Optional[Set[str]] = None) -> List[str]:
    """
    Split an artist string into individual artist names, with awareness of known artists.

    First splits by standard separators (commas, slashes, feat., etc.),
    then tries to further split space-containing parts by matching against
    known artist names.

    Args:
        artist_string: The artist string to split
        known_artists: Optional set of normalized (lowercase) known artist names.
                      When provided, space-separated names are split if all parts
                      match known artists. When None, behaves identically to split_artists().

    Returns:
        List of individual artist names
    """
    artists = split_artists(artist_string)

    if not known_artists:
        return artists

    result = []
    for artist in artists:
        if ' ' in artist:
            result.extend(_try_split_by_known(artist, known_artists))
        else:
            result.append(artist)

    return result
