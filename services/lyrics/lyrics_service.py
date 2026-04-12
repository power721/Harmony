"""
Lyrics service for fetching and parsing lyrics.
"""
import logging
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, as_completed, wait
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from charset_normalizer import from_bytes
from harmony_plugin_api.lyrics import PluginLyricsResult
from system.plugins.online_lyrics_helpers import download_online_lyrics
from services._singleflight import SingleFlight
from utils.lrc_parser import LyricLine
from utils.match_scorer import MatchScorer, TrackInfo

# Configure logging
logger = logging.getLogger(__name__)

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
_online_provider_lyrics_singleflight: SingleFlight[str] = SingleFlight()
_online_track_lyrics_singleflight: SingleFlight[str] = SingleFlight()


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
    def _get_builtin_sources(cls) -> List["LyricsSource"]:
        """Get built-in host lyrics sources."""
        return []

    @classmethod
    def _get_sources(cls) -> List["LyricsSource"]:
        """Get host and plugin-provided lyrics sources."""
        from app.bootstrap import Bootstrap

        plugin_sources = Bootstrap.instance().plugin_manager.registry.lyrics_sources()
        return cls._get_builtin_sources() + plugin_sources

    @staticmethod
    def _get_source_name(source) -> str:
        return getattr(source, "name", getattr(source, "display_name", source.__class__.__name__))

    @staticmethod
    def _result_to_dict(result) -> dict:
        return {
            "id": getattr(result, "id", getattr(result, "song_id", "")),
            "title": getattr(result, "title", ""),
            "artist": getattr(result, "artist", ""),
            "album": getattr(result, "album", ""),
            "duration": getattr(result, "duration", None),
            "cover_url": getattr(result, "cover_url", None),
            "source": getattr(result, "source", ""),
            "lyrics": getattr(result, "lyrics", None),
            "accesskey": getattr(result, "accesskey", None),
            "supports_yrc": getattr(result, "supports_yrc", False),
        }

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
        if not sources:
            return results

        # Parallel search from multiple sources with progressive updates.
        executor = ThreadPoolExecutor(max_workers=len(sources))
        pending = set()
        futures = {}
        try:
            futures = {
                executor.submit(source.search, title, artist, limit): cls._get_source_name(source)
                for source in sources
            }
            pending = set(futures)
            deadline = time.monotonic() + 15

            while pending:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break

                completed, pending = wait(
                    pending,
                    timeout=remaining,
                    return_when=FIRST_COMPLETED,
                )
                if not completed:
                    break

                for future in completed:
                    source_name = futures[future]
                    try:
                        search_results = future.result(timeout=0)
                        results.extend(cls._result_to_dict(r) for r in search_results)
                        logger.debug(f"[LyricsService] {source_name}: found {len(search_results)} results")

                        if progress_callback and search_results:
                            progress_callback(results, source_name)

                    except Exception as e:
                        logger.debug(f"[LyricsService] {source_name} search failed: {e}")
        finally:
            if pending:
                pending_sources = ", ".join(
                    sorted(futures.get(future, "unknown") for future in pending)
                )
                logger.warning(
                    "[LyricsService] Search timed out for sources: %s",
                    pending_sources,
                )
                for future in pending:
                    future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)

        # Return all results (user can see all sources)
        return results

    @classmethod
    def download_lyrics_by_id(cls, song_id: str, source: str, accesskey: str = None) -> str:
        """
        Download lyrics by song ID from a specific source.

        Args:
            song_id: Song ID
            source: Source name ('lrclib', 'netease', 'kugou', or provider id)
            accesskey: Access key for Kugou

        Returns:
            Lyrics content or empty string
        """
        # Find the appropriate source and download lyrics
        sources = cls._get_sources()
        source_map = {cls._get_source_name(s).lower(): s for s in sources}

        lyrics_source = source_map.get(source.lower())
        if not lyrics_source:
            return ""

        if hasattr(lyrics_source, "display_name"):
            result = PluginLyricsResult(
                id=song_id,
                title="",
                artist="",
                source=source,
            )
        else:
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
                response = _get_http_client().get(
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
    def get_lyrics_by_song_id(cls, song_id: str, provider_id: str) -> str:
        """
        Get lyrics directly from an online provider by provider-side song id.

        This is used for online tracks where provider id and song id are known.

        Args:
            song_id: Provider-side song id
            provider_id: Provider id (e.g. 'netease', 'kugou', plugin id)

        Returns:
            Lyrics content (QRC or LRC format) or empty string
        """
        try:
            normalized_provider = (provider_id or "").strip().lower()
            if not normalized_provider:
                return ""
            return _online_provider_lyrics_singleflight.do(
                ("online_provider_lyrics", normalized_provider, song_id),
                lambda: download_online_lyrics(song_id=song_id, provider_id=normalized_provider),
            )
        except Exception as e:
            logger.error(f"Error downloading online lyrics: {e}", exc_info=True)
            return ""

    @classmethod
    def get_online_track_lyrics(
        cls,
        song_mid: str,
        track_path: str = "",
        provider_id: str | None = None,
    ) -> str:
        """
        Load or download lyrics for an online track once per song/path.

        This wraps the local-file check, online fetch, and local save in a shared
        single-flight call so multiple windows do not repeat the same work.
        """
        return _online_track_lyrics_singleflight.do(
            ("online_track_lyrics", provider_id or "", song_mid, track_path or ""),
            lambda: cls._load_or_download_online_track_lyrics(song_mid, track_path, provider_id=provider_id),
        )

    @classmethod
    def _load_or_download_online_track_lyrics(
        cls,
        song_mid: str,
        track_path: str = "",
        provider_id: str | None = None,
    ) -> str:
        """Internal helper for online lyrics retrieval."""
        if track_path and track_path not in (".", "", "/"):
            local_lyrics = cls._get_local_lyrics(track_path)
            if local_lyrics:
                return local_lyrics

        lyrics = cls.get_lyrics_by_song_id(song_mid, provider_id=provider_id)
        if lyrics and track_path and track_path not in (".", "", "/"):
            cls.save_lyrics(track_path, lyrics)
        return lyrics

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

        # Try different lyrics file extensions in priority order: .yrc, .qrc, .lrc
        for ext in ['.yrc', '.qrc', '.lrc']:
            lyrics_path = track_file.with_suffix(ext)
            if lyrics_path.exists():
                try:
                    raw_content = cls._read_local_lyrics_bytes(lyrics_path)
                except Exception as e:
                    logger.error(f"Error loading local lyrics from {lyrics_path}: {e}", exc_info=True)
                    continue

                decoded = cls._decode_local_lyrics(raw_content)
                if decoded:
                    return decoded

        return ""

    @staticmethod
    def _read_local_lyrics_bytes(lyrics_path: Path) -> bytes:
        """Read a local lyrics file once in binary mode."""
        with open(lyrics_path, 'rb') as f:
            return f.read()

    @staticmethod
    def _decode_local_lyrics(raw_content: bytes) -> str:
        """Decode local lyrics content with UTF-8 first and charset detection fallback."""
        if not raw_content:
            return ""

        try:
            return raw_content.decode('utf-8')
        except UnicodeDecodeError:
            pass

        detected = from_bytes(raw_content).best()
        if detected is not None:
            return str(detected)

        for encoding in ['utf-16', 'gb18030', 'gbk', 'gb2312', 'big5']:
            try:
                return raw_content.decode(encoding)
            except (UnicodeDecodeError, UnicodeError):
                continue

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
                    all_results.extend(SearchResult(
                            title=r.title,
                            artist=r.artist,
                            album=r.album,
                            duration=r.duration,
                            source=r.source,
                            id=getattr(r, "id", getattr(r, "song_id", "")),
                            cover_url=r.cover_url,
                        ) for r in search_results)
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
