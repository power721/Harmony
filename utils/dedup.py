"""
Intelligent track deduplication utility.

This module provides smart deduplication for music tracks based on version priority.
For example, when multiple versions of the same song exist:
- 黄霄雲 - 淬炼 (伴奏)
- 黄霄雲 - 淬炼 (和声伴奏)
- 黄霄雲 - 淬炼

The algorithm keeps the original version (highest priority).
"""

import re
import os
import logging
from typing import List, Tuple
from dataclasses import dataclass

from domain import PlaylistItem

logger = logging.getLogger(__name__)


# Pre-compiled regex patterns for H-17 optimization (10-50x faster deduplication)

# File extension removal
_PATTERN_FILE_EXT = re.compile(r'\.(flac|mp3|wav|m4a|ogg|aac|ape|wma)$', re.IGNORECASE)

# Website/source tag removal
_PATTERN_TAG_COM = re.compile(r'\s*\[.*?\.com.*?\]\s*$', re.IGNORECASE)
_PATTERN_TAG_NET = re.compile(r'\s*\[.*?网.*?\]\s*$', re.IGNORECASE)
_PATTERN_TAG_SITE = re.compile(r'\s*\[.*?site.*?\]\s*$', re.IGNORECASE)
_PATTERN_TAG_HTTP = re.compile(r'\s*\[https?://.*?\]\s*$', re.IGNORECASE)
_PATTERN_TAG_WWW = re.compile(r'\s*\[www\..*?\]\s*$', re.IGNORECASE)

# Version detection patterns (applied to lowercase title)
_PATTERN_LIVE_DETECT = re.compile(
    r'[（\(]?\s*live\s*(版|version|ver\.?|现场)?\s*[）\)]?|[【\[]?\s*live\s*(版|version|ver\.?|现场)?\s*[】\]]?'
)
_PATTERN_INSTRUMENTAL_DETECT = re.compile(
    r'(人声伴奏|vocal\s+accompaniment|伴奏|instrumental|karaoke|off\s*vocal)'
)
_PATTERN_HARMONY_DETECT = re.compile(r'和声伴奏|和声|harmony')
_PATTERN_SPECIAL_DETECT = re.compile(
    r'([（\(]纯享版[）\)]|[（\(]吟唱版[）\)]|[（\(]explicit\s+version[）\)]|'
    r'[（\(]singing\s+version[）\)]|[（\(]singing\s+ver\.?[）\)]|'
    r'[（\(]chorus\s+version[）\)]|[（\(]remix[）\)]|[（\(]solo\s+version[）\)]|'
    r'[（\(](?:纯享版|吟唱版|remix|solo\s+version)[^)）]*[）\)])'
)

# Base title cleanup - live markers
_PATTERN_LIVE_PARENS = re.compile(r'\s*[（\(][^)）]*live[^)）]*[）\)]\s*', re.IGNORECASE)
_PATTERN_LIVE_BRACKETS = re.compile(r'\s*[\[【][^\]】]*live[^\]】]*[\]】]\s*', re.IGNORECASE)
_PATTERN_LIVE_STANDALONE = re.compile(r'\s*live\s*', re.IGNORECASE)

# Base title cleanup - instrumental markers
_PATTERN_INSTRUMENTAL_PARENS = re.compile(
    r'\s*[（\(][^)）]*(?:人声伴奏|vocal\s+accompaniment|伴奏|instrumental|karaoke|off\s*vocal)[^)）]*[）\)]\s*',
    re.IGNORECASE
)
_PATTERN_INSTRUMENTAL_BRACKETS = re.compile(
    r'\s*[\[【][^\]】]*(?:人声伴奏|vocal\s+accompaniment|伴奏|instrumental|karaoke|off\s*vocal)[^\]】]*[\]】]\s*',
    re.IGNORECASE
)
_PATTERN_INSTRUMENTAL_STANDALONE = re.compile(
    r'\s*(?:人声伴奏|vocal\s+accompaniment|伴奏|instrumental|karaoke|off\s*vocal)\s*',
    re.IGNORECASE
)

# Base title cleanup - harmony markers
_PATTERN_HARMONY_PARENS = re.compile(r'\s*[（\(]?\s*(和声伴奏|和声|harmony)\s*[）\)]?\s*', re.IGNORECASE)
_PATTERN_HARMONY_BRACKETS = re.compile(r'\s*[\[【].*(和声伴奏|和声|harmony).*[\]】]\s*', re.IGNORECASE)

# Base title cleanup - special version markers
_PATTERN_SPECIAL_PARENS = re.compile(
    r'\s*[（\(][^)）]*(?:纯享版|吟唱版|explicit\s+version|singing\s+version|'
    r'singing\s+ver\.?|chorus\s+version|remix|solo\s+version)[^)）]*[）\)]\s*',
    re.IGNORECASE
)
_PATTERN_SPECIAL_BRACKETS = re.compile(
    r'\s*[\[【][^\]【]*(?:纯享版|吟唱版|explicit\s+version|singing\s+version|'
    r'singing\s+ver\.?|chorus\s+version|remix|solo\s+version)[^\]】]*[\]】]\s*',
    re.IGNORECASE
)

# Base title cleanup - other version qualifiers
_PATTERN_VERSION_PARENS = re.compile(
    r'\s*[（\(][^)）]*(?:official\s+version|version|正式版|官方正式版|监制)[^)）]*[）\)]\s*',
    re.IGNORECASE
)


@dataclass
class VersionInfo:
    """Version information extracted from track title."""
    is_live: bool = False
    has_instrumental: bool = False
    has_harmony: bool = False
    has_special_version: bool = False  # e.g., 吟唱版, remix, etc.
    base_title: str = ""
    raw_title: str = ""

    @property
    def priority_score(self) -> int:
        """
        Calculate priority score for version selection.

        Higher score = higher priority to keep.
        Priority order (highest to lowest):
        1. Original version (no markers) - score 100
        2. Live version (has live, no instrumental) - score 80
        3. Special versions (singing ver, remix, etc.) - score 70
        4. Instrumental version (has instrumental, no live) - score 60
        5. Live instrumental (has both) - score 40
        6. Harmony instrumental - score 20

        Returns:
            Priority score (higher is better)
        """
        if not (self.is_live or self.has_instrumental or self.has_harmony or self.has_special_version):
            # Original version - highest priority
            return 100

        if self.is_live and not self.has_instrumental and not self.has_harmony and not self.has_special_version:
            # Live version only
            return 80

        if self.is_live and self.has_special_version and not self.has_instrumental and not self.has_harmony:
            # Live + special version (e.g., "Live remix")
            return 65

        if self.has_special_version and not self.is_live and not self.has_instrumental and not self.has_harmony:
            # Special version only (singing version, remix, etc.)
            return 70

        if self.has_special_version and self.has_instrumental and not self.is_live and not self.has_harmony:
            # Special instrumental version
            return 55

        if self.has_instrumental and not self.is_live and not self.has_harmony:
            # Instrumental only
            return 60

        if self.is_live and self.has_instrumental and not self.has_harmony:
            # Live instrumental
            return 40

        if self.has_harmony:
            # Harmony instrumental (lowest priority)
            return 20

        # Fallback for other combinations
        return 50


def extract_version_info(title: str) -> VersionInfo:
    """
    Extract version information from track title.

    Args:
        title: Track title (may include version markers, website tags, file extensions)

    Returns:
        VersionInfo object with extracted information
    """
    # First, clean the title by removing common noise
    cleaned_title = title

    # Remove file extensions
    cleaned_title = _PATTERN_FILE_EXT.sub('', cleaned_title)

    # Remove website/source tags (e.g., [putaojie.com], [site.com], etc.)
    # Be careful not to remove version markers like [伴奏]
    cleaned_title = _PATTERN_TAG_COM.sub('', cleaned_title)
    cleaned_title = _PATTERN_TAG_NET.sub('', cleaned_title)
    cleaned_title = _PATTERN_TAG_SITE.sub('', cleaned_title)
    # Only remove trailing brackets if they contain URLs or site names
    cleaned_title = _PATTERN_TAG_HTTP.sub('', cleaned_title)
    cleaned_title = _PATTERN_TAG_WWW.sub('', cleaned_title)

    # Now detect version markers from the cleaned title
    title_lower = cleaned_title.lower()

    # Detect version markers (supports both Chinese and English formats)
    # Support both half-width () and full-width （） parentheses
    # Match: live, live版, live version, live ver., live ver 等
    is_live = bool(_PATTERN_LIVE_DETECT.search(title_lower))

    # Detect instrumental markers (expanded to include more variations)
    # IMPORTANT: Order matters - longer phrases first!
    has_instrumental = bool(_PATTERN_INSTRUMENTAL_DETECT.search(title_lower))

    has_harmony = bool(_PATTERN_HARMONY_DETECT.search(title_lower))

    # Detect special versions that should have lower priority
    # Match: 纯享版, 吟唱版, Singing Version/Ver, Chorus Version, Remix, Solo Version, etc.
    # IMPORTANT: Order matters - longer patterns first!
    # Support both half-width () and full-width （） parentheses
    has_special_version = bool(_PATTERN_SPECIAL_DETECT.search(title_lower))

    # Extract base title by removing common version markers
    base_title = cleaned_title

    # Remove live markers (with or without parentheses/brackets, both half and full width)
    # Match: live, live版, live version, live ver., live现场, [Live], [Live Version] 等
    # Use same pattern style as instrumental markers for consistency
    base_title = _PATTERN_LIVE_PARENS.sub(' ', base_title)
    base_title = _PATTERN_LIVE_BRACKETS.sub(' ', base_title)
    # Also handle standalone live (without parentheses)
    base_title = _PATTERN_LIVE_STANDALONE.sub(' ', base_title)

    # Remove instrumental markers (expanded)
    # Handle both parenthetical and non-parenthetical formats
    # Support both half-width () and full-width （） parentheses
    base_title = _PATTERN_INSTRUMENTAL_PARENS.sub(' ', base_title)
    base_title = _PATTERN_INSTRUMENTAL_BRACKETS.sub(' ', base_title)
    # Then, remove standalone markers (for formats like "Song Instrumental")
    base_title = _PATTERN_INSTRUMENTAL_STANDALONE.sub(' ', base_title)

    # Remove harmony markers (support both half and full width parentheses)
    base_title = _PATTERN_HARMONY_PARENS.sub(' ', base_title)
    base_title = _PATTERN_HARMONY_BRACKETS.sub(' ', base_title)

    # Remove special version markers (e.g., 吟唱版, 纯享版, Singing Ver, Remix, etc.)
    # Handle both parenthetical and non-parenthetical formats
    base_title = _PATTERN_SPECIAL_PARENS.sub(' ', base_title)
    base_title = _PATTERN_SPECIAL_BRACKETS.sub(' ', base_title)

    # Remove other version qualifiers for better grouping
    # (e.g., "Official Version", "Version", "正式版", "官方正式版" etc.)
    base_title = _PATTERN_VERSION_PARENS.sub(' ', base_title)

    base_title = ' '.join(base_title.split())  # Normalize whitespace

    return VersionInfo(
        is_live=is_live,
        has_instrumental=has_instrumental,
        has_harmony=has_harmony,
        has_special_version=has_special_version,
        base_title=base_title,
        raw_title=title
    )


def get_track_key(item: PlaylistItem) -> str:
    """
    Get grouping key for track deduplication.

    Groups tracks by artist and base title (without version markers).

    Args:
        item: PlaylistItem to analyze

    Returns:
        Grouping key string (e.g., "黄霄雲 - 淬炼")
    """
    artist = item.artist or "Unknown Artist"
    title = item.title or os.path.basename(item.local_path or "")

    # Extract base title without version markers
    version_info = extract_version_info(title)
    base_title = version_info.base_title or title

    return f"{artist} - {base_title}".strip()


def _extract_item_version_info(item: PlaylistItem) -> VersionInfo:
    """
    Extract version info from both title and local filename.

    Some tracks have cleaned metadata titles (e.g., no "(伴奏)") while the
    actual filename still contains version markers. In that case, combine both
    sources to avoid picking a lower-quality version.
    """
    title = item.title or ""
    title_info = extract_version_info(title) if title else VersionInfo()

    filename = os.path.basename(item.local_path or "")
    filename_info = extract_version_info(filename) if filename else VersionInfo()

    base_title = title_info.base_title or title or filename_info.base_title or filename

    return VersionInfo(
        is_live=title_info.is_live or filename_info.is_live,
        has_instrumental=title_info.has_instrumental or filename_info.has_instrumental,
        has_harmony=title_info.has_harmony or filename_info.has_harmony,
        has_special_version=title_info.has_special_version or filename_info.has_special_version,
        base_title=base_title,
        raw_title=title or filename,
    )


def deduplicate_playlist_items(items: List[PlaylistItem]) -> List[PlaylistItem]:
    """
    Intelligently deduplicate playlist items based on version priority.

    Keeps the highest priority version when duplicates are detected.
    Preserves the original order of kept items.

    Priority order (highest to lowest):
    1. Original version (no version markers)
    2. Live version (has live, no instrumental)
    3. Instrumental version (has instrumental, no live)
    4. Live instrumental (has both live and instrumental)
    5. Harmony instrumental (has harmony)

    Args:
        items: List of PlaylistItem to deduplicate

    Returns:
        Deduplicated list with highest priority versions

    Examples:
        >>> items = [
        ...     PlaylistItem(title="淬炼 (伴奏)", artist="黄霄雲"),
        ...     PlaylistItem(title="淬炼 (和声伴奏)", artist="黄霄雲"),
        ...     PlaylistItem(title="淬炼", artist="黄霄雲"),
        ... ]
        >>> result = deduplicate_playlist_items(items)
        >>> len(result)
        1
        >>> result[0].title
        '淬炼'
    """
    if not items:
        return []

    # Group items by track key
    groups: dict[str, List[PlaylistItem]] = {}
    for item in items:
        key = get_track_key(item)
        if key not in groups:
            groups[key] = []
        groups[key].append(item)

    # For each group, keep only the highest priority version
    result: List[PlaylistItem] = []
    removed_count = 0

    for key, group_items in groups.items():
        if len(group_items) == 1:
            # No duplicates, keep as is
            result.append(group_items[0])
        else:
            # Multiple versions, select highest priority
            scored_items: List[Tuple[int, PlaylistItem]] = []
            for item in group_items:
                version_info = _extract_item_version_info(item)
                score = version_info.priority_score
                scored_items.append((score, item))

            # Sort by score (descending) and keep the highest
            scored_items.sort(key=lambda x: x[0], reverse=True)
            best_item = scored_items[0][1]
            result.append(best_item)

            # Log what was removed
            removed_versions = [item.title or item.local_path for _, item in scored_items[1:]]
            logger.debug(f"[Dedup] Kept: {best_item.title} ({key}), Removed: {removed_versions}")
            removed_count += len(scored_items) - 1

    logger.info(f"[Dedup] Removed {removed_count} duplicate(s), kept {len(result)} item(s)")
    return result


def deduplicate_playlist_items_strict(items: List[PlaylistItem]) -> List[PlaylistItem]:
    """
    Strict deduplication - removes ALL versions that have version markers.

    Only keeps truly original versions. Use this when you want to remove
    ALL live/instrumental versions and keep only originals.

    Args:
        items: List of PlaylistItem to deduplicate

    Returns:
        Deduplicated list with only original versions
    """
    if not items:
        return []

    result: List[PlaylistItem] = []

    for item in items:
        version_info = _extract_item_version_info(item)
        # Only keep if no version markers
        if version_info.priority_score == 100:
            result.append(item)
        else:
            logger.debug(f"[Dedup-Strict] Removed: {item.title} ({get_track_key(item)})")

    logger.info(f"[Dedup-Strict] Removed {len(items) - len(result)} item(s), kept {len(result)} original(s)")
    return result


def get_version_summary(items: List[PlaylistItem]) -> dict:
    """
    Get a summary of version types in the playlist.

    Args:
        items: List of PlaylistItem to analyze

    Returns:
        Dictionary with version statistics
    """
    stats = {
        "total": len(items),
        "original": 0,
        "live": 0,
        "instrumental": 0,
        "live_instrumental": 0,
        "harmony": 0,
        "groups": 0,
    }

    group_keys = set()

    for item in items:
        key = get_track_key(item)
        group_keys.add(key)

        version_info = _extract_item_version_info(item)
        score = version_info.priority_score

        if score == 100:
            stats["original"] += 1
        elif score == 80:
            stats["live"] += 1
        elif score == 60:
            stats["instrumental"] += 1
        elif score == 40:
            stats["live_instrumental"] += 1
        elif score == 20:
            stats["harmony"] += 1

    stats["groups"] = len(group_keys)
    return stats
