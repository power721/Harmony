"""
Match scorer for calculating similarity between track metadata and search results.

Used for lyrics and cover art matching to select the best result.
"""
import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TrackInfo:
    """Track information for matching."""
    title: str
    artist: str
    album: str = ""
    duration: Optional[float] = None  # Duration in seconds


@dataclass
class SearchResult:
    """Search result with metadata."""
    title: str
    artist: str
    album: str = ""
    duration: Optional[float] = None  # Duration in seconds
    source: str = ""
    id: str = ""
    cover_url: Optional[str] = None
    lyrics: Optional[str] = None
    accesskey: Optional[str] = None
    album_mid: Optional[str] = None  # For QQ Music lazy cover fetch


class MatchScorer:
    """
    Calculate match score between track info and search result.

    Scoring factors:
    - Duration match (0-40 points) - highest weight
    - Title similarity (0-25 points)
    - Artist similarity (0-25 points)
    - Album similarity (0-10 points)

    Total max score: 100 points

    Duration tolerance: ±5 seconds for strict matching

    Match modes:
    - 'lyrics': Duration has highest weight (default for lyrics matching)
    - 'cover': Album has highest weight (default for cover matching)
    """

    # Default scoring weights (duration highest for better matching)
    TITLE_WEIGHT = 25
    ARTIST_WEIGHT = 25
    ALBUM_WEIGHT = 10
    DURATION_WEIGHT = 40

    # Weights for cover matching (album highest)
    COVER_TITLE_WEIGHT = 15
    COVER_ARTIST_WEIGHT = 25
    COVER_ALBUM_WEIGHT = 40
    COVER_DURATION_WEIGHT = 20

    # Duration tolerance in seconds (±5 seconds for stricter matching)
    DURATION_TOLERANCE = 5

    @classmethod
    def calculate_score(cls, track: TrackInfo, result: SearchResult, mode: str = 'lyrics') -> float:
        """
        Calculate overall match score between track and search result.

        Args:
            track: Original track information
            result: Search result to evaluate
            mode: Match mode - 'lyrics' (title highest) or 'cover' (album highest)

        Returns:
            Match score (0-100)
        """
        title_score = cls._title_score(track.title, result.title)
        artist_score = cls._artist_score(track.artist, result.artist)
        album_score = cls._album_score(track.album, result.album)
        duration_score = cls._duration_score(track.duration, result.duration)

        # Select weights based on mode
        if mode == 'cover':
            title_weight = cls.COVER_TITLE_WEIGHT
            artist_weight = cls.COVER_ARTIST_WEIGHT
            album_weight = cls.COVER_ALBUM_WEIGHT
            duration_weight = cls.COVER_DURATION_WEIGHT
        else:  # 'lyrics' mode (default)
            title_weight = cls.TITLE_WEIGHT
            artist_weight = cls.ARTIST_WEIGHT
            album_weight = cls.ALBUM_WEIGHT
            duration_weight = cls.DURATION_WEIGHT

        total_score = (
                title_score * title_weight / 100 +
                artist_score * artist_weight / 100 +
                album_score * album_weight / 100 +
                duration_score * duration_weight / 100
        )

        logger.debug(
            f"Match score ({mode}): {total_score:.1f} "
            f"(title={title_score:.0f}%×{title_weight}, artist={artist_score:.0f}%×{artist_weight}, "
            f"album={album_score:.0f}%×{album_weight}, duration={duration_score:.0f}%×{duration_weight})"
        )

        return total_score

    @classmethod
    def find_best_match(cls, track: TrackInfo, results: list, mode: str = 'lyrics') -> Optional[tuple]:
        """
        Find the best matching result from a list.

        Args:
            track: Original track information
            results: List of SearchResult objects
            mode: Match mode - 'lyrics' (title highest) or 'cover' (album highest)

        Returns:
            Tuple of (best_result, score) or None if no results
        """
        if not results:
            return None

        best_result = None
        best_score = 0

        for result in results:
            # Convert dict to SearchResult if needed
            if isinstance(result, dict):
                result = SearchResult(
                    title=result.get('title', ''),
                    artist=result.get('artist', ''),
                    album=result.get('album', ''),
                    duration=result.get('duration'),
                    source=result.get('source', ''),
                    id=result.get('id', ''),
                    cover_url=result.get('cover_url'),
                    lyrics=result.get('lyrics'),
                    accesskey=result.get('accesskey')
                )

            score = cls.calculate_score(track, result, mode)

            if score > best_score or (score == best_score and result.source == 'qqmusic'):
                best_score = score
                best_result = result

        if best_result:
            logger.info(f"Best match ({mode}): {best_result.title} - {best_result.artist} (score: {best_score:.1f})")

        return (best_result, best_score) if best_result else None

    @classmethod
    def _title_score(cls, track_title: str, result_title: str) -> float:
        """
        Calculate title similarity score (0-100).

        Factors:
        - Exact match: 100%
        - Case-insensitive match: 95%
        - Normalized match (ignore punctuation, spaces): 90%
        - Partial match: 50-80%
        """
        if not track_title or not result_title:
            return 0

        # Exact match
        if track_title == result_title:
            return 100

        # Case-insensitive match
        t_lower = track_title.lower()
        r_lower = result_title.lower()

        if t_lower == r_lower:
            return 95

        # Normalize: remove punctuation and extra spaces
        t_norm = cls._normalize_string(track_title)
        r_norm = cls._normalize_string(result_title)

        if t_norm == r_norm:
            return 90

        # Check if one contains the other (partial match)
        if t_norm in r_norm or r_norm in t_norm:
            # Score based on length ratio
            len_ratio = min(len(t_norm), len(r_norm)) / max(len(t_norm), len(r_norm))
            return 50 + len_ratio * 30

        # Calculate similarity using word overlap
        return cls._word_overlap_score(t_norm, r_norm)

    @classmethod
    def _artist_score(cls, track_artist: str, result_artist: str) -> float:
        """
        Calculate artist similarity score (0-100).

        Similar to title scoring but with some special handling:
        - Feat./& handling for multiple artists
        - Chinese/English artist name variations
        """
        if not track_artist or not result_artist:
            return 0

        # Exact match
        if track_artist == result_artist:
            return 100

        t_lower = track_artist.lower()
        r_lower = result_artist.lower()

        if t_lower == r_lower:
            return 95

        # Normalize
        t_norm = cls._normalize_string(track_artist)
        r_norm = cls._normalize_string(result_artist)

        if t_norm == r_norm:
            return 90

        # Handle "feat." or "ft." or "&" - check if main artist matches
        t_main = cls._extract_main_artist(t_norm)
        r_main = cls._extract_main_artist(r_norm)

        if t_main == r_main:
            return 85

        # Check partial match
        if t_main in r_main or r_main in t_main:
            return 70

        return cls._word_overlap_score(t_norm, r_norm)

    @classmethod
    def _album_score(cls, track_album: str, result_album: str) -> float:
        """
        Calculate album similarity score (0-100).
        """
        if not track_album or not result_album:
            # No album info - don't penalize
            return 50

        if track_album == result_album:
            return 100

        t_lower = track_album.lower()
        r_lower = result_album.lower()

        if t_lower == r_lower:
            return 95

        t_norm = cls._normalize_string(track_album)
        r_norm = cls._normalize_string(result_album)

        if t_norm == r_norm:
            return 90

        # Partial match
        if t_norm in r_norm or r_norm in t_norm:
            return 70

        return cls._word_overlap_score(t_norm, r_norm)

    @classmethod
    def _duration_score(cls, track_duration: Optional[float], result_duration: Optional[float]) -> float:
        """
        Calculate duration match score (0-100).

        Perfect match within tolerance: 100%
        Gradual decrease for larger differences
        """
        if track_duration is None or result_duration is None:
            # No duration info - don't penalize
            return 50

        diff = abs(track_duration - result_duration)

        if diff <= cls.DURATION_TOLERANCE:
            # Perfect match within tolerance
            return 100

        # Gradual decrease: lose 10 points per 30 seconds beyond tolerance
        excess = diff - cls.DURATION_TOLERANCE
        penalty = (excess / 30) * 10

        return max(0, 100 - penalty)

    @classmethod
    def _normalize_string(cls, s: str) -> str:
        """
        Normalize string for comparison.

        - Convert to lowercase
        - Remove punctuation
        - Normalize whitespace
        - Remove common suffixes like "(Official)", "[MV]", etc.
        """
        if not s:
            return ""

        # Convert to lowercase
        s = s.lower()

        # Remove common suffixes
        patterns_to_remove = [
            r'\s*\(official\s*(music\s*)?video\)',
            r'\s*\[official\s*(music\s*)?video\]',
            r'\s*\(mv\)',
            r'\s*\[mv\]',
            r'\s*\(lyric\s*video\)',
            r'\s*\[lyric\s*video\]',
            r'\s*\(audio\)',
            r'\s*\[audio\]',
            r'\s*-?\s*official\s*audio',
            r'\s*-?\s*lyrics',
            r'\s*\(explicit\)',
            r'\s*\[explicit\]',
            r'\s*\(radio\s*edit\)',
            r'\s*\[radio\s*edit\]',
            r'\s*\(remix\)',
            r'\s*\[remix\]',
        ]

        for pattern in patterns_to_remove:
            s = re.sub(pattern, '', s, flags=re.IGNORECASE)

        # Remove punctuation except for CJK characters
        # Keep letters, numbers, CJK characters, and spaces
        s = re.sub(r'[^\w\s\u4e00-\u9fff\u3400-\u4dbf]', '', s)

        # Normalize whitespace
        s = ' '.join(s.split())

        return s.strip()

    @classmethod
    def _extract_main_artist(cls, artist_str: str) -> str:
        """
        Extract main artist from string with multiple artists.

        Examples:
        - "Artist A feat. Artist B" -> "Artist A"
        - "Artist A & Artist B" -> "Artist A"
        - "Artist A, Artist B" -> "Artist A"
        """
        if not artist_str:
            return ""

        # Split by common separators
        separators = [
            r'\s+feat\.?\s+',
            r'\s+ft\.?\s+',
            r'\s+&\s+',
            r'\s*,\s*',
            r'\s+and\s+',
            r'\s+x\s+',
        ]

        for sep in separators:
            parts = re.split(sep, artist_str, flags=re.IGNORECASE)
            if len(parts) > 1:
                return parts[0].strip()

        return artist_str.strip()

    @classmethod
    def _word_overlap_score(cls, s1: str, s2: str) -> float:
        """
        Calculate word overlap score between two strings.

        Uses Jaccard similarity on word sets.
        """
        if not s1 or not s2:
            return 0

        words1 = set(s1.split())
        words2 = set(s2.split())

        if not words1 or not words2:
            return 0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union) * 100
