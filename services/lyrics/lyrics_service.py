"""
Lyrics service for fetching and parsing lyrics.
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

# Configure logging
logger = logging.getLogger(__name__)
from pathlib import Path
from typing import Optional, List
import requests

from utils.lrc_parser import LyricLine
from utils.match_scorer import MatchScorer, TrackInfo
from .qqmusic_lyrics import download_qqmusic_lyrics

if TYPE_CHECKING:
    from services.sources.base import LyricsSource

# Initialize OpenCC converter for Traditional to Simplified Chinese conversion
try:
    from opencc import OpenCC

    _t2s_converter = OpenCC('t2s')  # Traditional to Simplified
    _HAS_OPENCC = True
except ImportError:
    _HAS_OPENCC = False
    _t2s_converter = None
    logger.warning("OpenCC not installed. Traditional Chinese lyrics will not be converted to Simplified.")

# Shared HTTP client instance
_shared_http_client = None


def _get_http_client():
    """Get or create shared HTTP client instance."""
    global _shared_http_client
    if _shared_http_client is None:
        from infrastructure.network import HttpClient
        _shared_http_client = HttpClient()
    return _shared_http_client


class LyricsService:
    """Service for fetching lyrics from local files and online sources."""

    # User agent for web requests
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    # Enable online lyrics
    ENABLE_ONLINE = True  # Changed to True for better UX

    @classmethod
    def _get_sources(cls) -> List["LyricsSource"]:
        """Get lyrics sources."""
        from services.sources import (
            NetEaseLyricsSource,
            QQMusicLyricsSource,
            KugouLyricsSource,
            LRCLIBLyricsSource,
        )
        http_client = _get_http_client()
        return [
            LRCLIBLyricsSource(http_client),
            NetEaseLyricsSource(http_client),
            KugouLyricsSource(http_client),
            QQMusicLyricsSource(),
        ]

    @classmethod
    def _convert_to_simplified_chinese(cls, text: str) -> str:
        """
        Convert Traditional Chinese to Simplified Chinese.

        Args:
            text: Text that may contain Traditional Chinese

        Returns:
            Text with Traditional Chinese converted to Simplified
        """
        if not _HAS_OPENCC or not text:
            return text

        try:
            return _t2s_converter.convert(text)
        except Exception as e:
            logger.warning(f"Failed to convert to Simplified Chinese: {e}")
            return text

    @classmethod
    def search_songs(cls, title: str, artist: str, limit: int = 10,
                     progress_callback=None) -> List[dict]:
        """
        Search for songs online and return a list of candidates.
        Uses parallel searching for better performance.

        Args:
            title: Track title
            artist: Track artist
            limit: Maximum number of results per source (total results will be larger)
            progress_callback: Optional callback(progress_results, source_name) called
                              as each source completes

        Returns:
            List of dicts with keys: 'id', 'title', 'artist', 'album', 'source'
        """
        results = []
        sources = cls._get_sources()

        # Parallel search from multiple sources with progressive updates
        with ThreadPoolExecutor(max_workers=len(sources)) as executor:
            futures = {
                executor.submit(source.search, title, artist, limit): source.name
                for source in sources
            }

            # Wait for each source independently (no overall timeout)
            for future in as_completed(futures, timeout=15):
                source_name = futures[future]
                try:
                    search_results = future.result(timeout=6)
                    # Convert LyricsSearchResult to dict for compatibility
                    for r in search_results:
                        results.append({
                            'id': r.id,
                            'title': r.title,
                            'artist': r.artist,
                            'album': r.album,
                            'duration': r.duration,
                            'cover_url': r.cover_url,
                            'source': r.source,
                            'lyrics': r.lyrics,
                            'accesskey': r.accesskey,
                            'supports_yrc': r.supports_yrc,
                        })
                    logger.debug(f"[LyricsService] {source_name}: found {len(search_results)} results")

                    # Call progress callback if provided
                    if progress_callback and search_results:
                        progress_callback(results, source_name)

                except Exception as e:
                    # Log but don't fail - other sources may have results
                    logger.debug(f"[LyricsService] {source_name} search failed: {e}")

        # Return all results (user can see all sources)
        return results

    @classmethod
    def download_lyrics_by_id(cls, song_id: str, source: str, accesskey: str = None) -> str:
        """
        Download lyrics by song ID from a specific source.

        Args:
            song_id: Song ID
            source: Source name ('lrclib', 'netease', 'kugou', or 'qqmusic')
            accesskey: Access key for Kugou

        Returns:
            Lyrics content or empty string
        """
        # Find the appropriate source and download lyrics
        sources = cls._get_sources()
        source_map = {s.name.lower(): s for s in sources}

        lyrics_source = source_map.get(source.lower())
        if not lyrics_source:
            return ""

        # Create a result object for get_lyrics
        from services.sources.base import LyricsSearchResult
        result = LyricsSearchResult(
            id=song_id,
            title="",
            artist="",
            source=source,
            accesskey=accesskey,
        )

        lyrics = lyrics_source.get_lyrics(result)
        if lyrics:
            return cls._convert_to_simplified_chinese(lyrics)
        return ""

    @classmethod
    def get_song_cover_url(cls, song_id: str, source: str) -> Optional[str]:
        """
        Get cover URL for a song from online sources.

        Args:
            song_id: Song ID
            source: Source name ('netease', 'lrclib', or 'kugou')

        Returns:
            Cover URL or None
        """
        # Only NetEase provides cover URLs in lyrics service
        if source == 'netease':
            try:
                # Use song detail API to get cover URL
                detail_url = f"https://music.163.com/api/song/detail?ids=[{song_id}]"
                response = requests.get(
                    detail_url,
                    headers=cls.HEADERS,
                    timeout=3
                )

                if response.status_code != 200:
                    return None

                data = response.json()
                if data.get('code') != 200 or not data.get('songs'):
                    return None

                # Get cover URL from songs[0].al.picUrl
                song = data['songs'][0]
                if song.get('album') and song['album'].get('picUrl'):
                    return song['album']['picUrl']

            except Exception as e:
                logger.error(f"Error getting NetEase song cover: {e}", exc_info=True)

        return None

    @classmethod
    def get_lyrics_by_qqmusic_mid(cls, song_mid: str) -> str:
        """
        Get lyrics directly from QQ Music by song mid.

        This is used for online QQ Music tracks where we already have the song_mid.

        Args:
            song_mid: QQ Music song MID

        Returns:
            Lyrics content (QRC or LRC format) or empty string
        """
        try:
            return download_qqmusic_lyrics(song_mid)
        except Exception as e:
            logger.error(f"Error downloading QQ Music lyrics: {e}", exc_info=True)
            return ""

    @classmethod
    def download_and_save_lyrics(cls, track_path: str, title: str, artist: str) -> bool:
        """
        Download lyrics and save to local .lrc file.

        Args:
            track_path: Path to the audio file
            title: Track title
            artist: Track artist

        Returns:
            True if lyrics were downloaded and saved
        """
        lyrics = cls._get_online_lyrics(title, artist)
        if lyrics:
            return cls.save_lyrics(track_path, lyrics)
        return False

    @classmethod
    def get_lyrics(cls, track_path: str, title: str, artist: str, album: str = "", duration: float = None) -> str:
        """
        Get lyrics for a track, prioritizing local .lrc files.

        Args:
            track_path: Path to the audio file
            title: Track title
            artist: Track artist
            album: Album name (optional, for better matching)
            duration: Track duration in seconds (optional, for better matching)

        Returns:
            Lyrics content or empty string
        """
        # First try local .lrc file
        if track_path:
            lyrics = cls._get_local_lyrics(track_path)
            if lyrics:
                return lyrics

        # Fall back to online sources (only if enabled)
        if cls.ENABLE_ONLINE:
            # If title looks like a filename, try to parse artist and title from it
            search_title = title
            search_artist = artist

            from utils.helpers import is_filename_like, parse_filename_as_metadata
            if is_filename_like(title) or (not artist and ' - ' in title):
                parsed_artist, parsed_title = parse_filename_as_metadata(title)
                if parsed_title:
                    search_title = parsed_title
                    if parsed_artist:
                        search_artist = parsed_artist
                    logger.info(
                        f"[LyricsService] Parsed filename: '{title}' -> artist='{search_artist}', title='{search_title}'")

            lyrics = cls._get_online_lyrics(search_title, search_artist, album, duration)
            if lyrics:
                cls.save_lyrics(track_path, lyrics)
                return lyrics

        return ""

    @classmethod
    def _get_local_lyrics(cls, track_path: str) -> str:
        """
        Load lyrics from a local lyrics file.

        Supports multiple formats: .yrc, .qrc, .lrc

        Args:
            track_path: Path to the audio file

        Returns:
            Lyrics content or empty string
        """
        track_file = Path(track_path)

        # Try multiple encodings to support different file sources
        encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'big5', 'utf-16']

        # Try different lyrics file extensions in priority order: .yrc, .qrc, .lrc
        for ext in ['.yrc', '.qrc', '.lrc']:
            lyrics_path = track_file.with_suffix(ext)
            if lyrics_path.exists():
                for encoding in encodings:
                    try:
                        with open(lyrics_path, 'r', encoding=encoding) as f:
                            content = f.read()
                        return content
                    except (UnicodeDecodeError, UnicodeError):
                        continue
                    except Exception as e:
                        logger.error(f"Error loading local lyrics from {lyrics_path}: {e}", exc_info=True)
                        break

        return ""

    @classmethod
    def _get_online_lyrics(cls, title: str, artist: str, album: str = "", duration: float = None) -> str:
        """
        Fetch lyrics from online sources with smart matching.
        Uses parallel searching for better performance.

        Args:
            title: Track title
            artist: Track artist
            album: Album name (optional)
            duration: Track duration in seconds (optional)

        Returns:
            Lyrics content or empty string
        """
        # Search all sources and collect results
        all_results = []
        sources = cls._get_sources()

        # Parallel search from multiple sources
        with ThreadPoolExecutor(max_workers=len(sources)) as executor:
            futures = {
                executor.submit(source.search, title, artist, 5): source.name
                for source in sources
            }

            # Each source has its own timeout, slow sources don't block fast ones
            for future in as_completed(futures, timeout=15):
                source_name = futures[future]
                try:
                    search_results = future.result(timeout=6)
                    # Convert LyricsSearchResult to SearchResult for MatchScorer
                    from utils.match_scorer import SearchResult
                    for r in search_results:
                        all_results.append(SearchResult(
                            title=r.title,
                            artist=r.artist,
                            album=r.album,
                            duration=r.duration,
                            source=r.source,
                            id=r.id,
                            cover_url=r.cover_url,
                        ))
                except Exception as e:
                    logger.debug(f"[LyricsService] {source_name} search failed: {e}")

        if not all_results:
            return ""

        # Use MatchScorer to find best match (use 'lyrics' mode - title highest weight)
        track_info = TrackInfo(
            title=title,
            artist=artist,
            album=album,
            duration=duration
        )

        best_match = MatchScorer.find_best_match(track_info, all_results, mode='lyrics')

        if best_match:
            result, score = best_match
            logger.info(f"Best lyrics match: {result.title} - {result.artist} (score: {score:.1f})")

            # If score is too low, don't use
            if score < 30:
                logger.info(f"Score too low ({score:.1f}), skipping")
                return ""

            # Download lyrics by ID
            return cls.download_lyrics_by_id(
                result.id,
                result.source,
                getattr(result, 'accesskey', None)
            )

        return ""

    @classmethod
    def save_lyrics(cls, track_path: str, lyrics: str) -> bool:
        """
        Save lyrics to a local file.

        Automatically detects format and saves with appropriate extension:
        - YRC format -> .yrc
        - QRC format -> .qrc
        - LRC format -> .lrc

        Args:
            track_path: Path to the audio file
            lyrics: Lyrics content

        Returns:
            True if saved successfully
        """
        # Skip saving if track_path is empty or invalid
        if not track_path or track_path in ('.', '', '/'):
            return False

        try:
            from utils.lrc_parser import detect_format

            track_file = Path(track_path)

            # Detect format and use appropriate extension
            lyrics_format = detect_format(lyrics)
            if lyrics_format == 'yrc':
                save_path = track_file.with_suffix('.yrc')
            elif lyrics_format == 'qrc':
                save_path = track_file.with_suffix('.qrc')
            else:
                save_path = track_file.with_suffix('.lrc')

            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(lyrics)

            # Delete old lyrics files with different extensions
            for ext in ['.lrc', '.yrc', '.qrc']:
                old_path = track_file.with_suffix(ext)
                if old_path.exists() and old_path != save_path:
                    try:
                        old_path.unlink()
                    except Exception:
                        pass

            return True

        except Exception as e:
            logger.error(f"Error saving lyrics to {track_path}: {e}", exc_info=True)
            return False

    @classmethod
    def delete_lyrics(cls, track_path: str) -> bool:
        """
        Delete lyrics file for a track.

        Deletes any existing lyrics file (.lrc, .yrc, or .qrc).

        Args:
            track_path: Path to the audio file

        Returns:
            True if deleted successfully
        """
        # Skip if track_path is empty or invalid
        if not track_path or track_path in ('.', '', '/'):
            return False

        try:
            track_file = Path(track_path)
            deleted = False

            # Delete any lyrics file regardless of extension
            for ext in ['.lrc', '.yrc', '.qrc']:
                lyrics_path = track_file.with_suffix(ext)
                if lyrics_path.exists():
                    lyrics_path.unlink()
                    deleted = True

            return deleted

        except Exception as e:
            logger.error(f"Error deleting lyrics file for {track_path}: {e}", exc_info=True)
            return False

    @classmethod
    def lyrics_file_exists(cls, track_path: str) -> bool:
        """
        Check if a lyrics file exists for a track.

        Checks for any supported lyrics format (.lrc, .yrc, .qrc).

        Args:
            track_path: Path to the audio file

        Returns:
            True if lyrics file exists
        """
        track_file = Path(track_path)

        # Check for any supported lyrics format
        for ext in ['.lrc', '.yrc', '.qrc']:
            lyrics_path = track_file.with_suffix(ext)
            if lyrics_path.exists():
                return True

        return False


class LyricsProvider:
    """Base class for lyrics providers."""

    def search(self, title: str, artist: str) -> Optional[str]:
        """Search for lyrics. Override in subclasses."""
        raise NotImplementedError

    def get_lyrics(self, song_id: str) -> Optional[List[LyricLine]]:
        """Get lyrics by song ID. Override in subclasses."""
        raise NotImplementedError
