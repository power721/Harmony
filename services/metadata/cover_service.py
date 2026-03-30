"""
Cover art service for extracting and fetching album covers.
"""
import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional, List, TYPE_CHECKING

from infrastructure.network import HttpClient
from utils.helpers import get_cache_dir
from utils.match_scorer import MatchScorer, TrackInfo, SearchResult

if TYPE_CHECKING:
    from services.sources.base import CoverSource, ArtistCoverSource

# Configure logging
logger = logging.getLogger(__name__)


class CoverService:
    """Service for extracting and fetching album covers."""

    # Cache directory
    CACHE_DIR = get_cache_dir('covers')

    def __init__(
        self,
        http_client: HttpClient,
        sources: Optional[List["CoverSource"]] = None,
    ):
        """
        Initialize cover service.

        Args:
            http_client: HTTP client for fetching cover art
            sources: Optional list of CoverSource instances for search.
                     If None, default sources will be created.
        """
        self.http_client = http_client
        self._sources = sources

    def _get_sources(self) -> List["CoverSource"]:
        """Get cover sources, creating default ones if needed."""
        if self._sources is None:
            from services.sources import (
                NetEaseCoverSource,
                QQMusicCoverSource,
                ITunesCoverSource,
                LastFmCoverSource,
            )
            self._sources = [
                NetEaseCoverSource(self.http_client),
                QQMusicCoverSource(),
                ITunesCoverSource(self.http_client),
                LastFmCoverSource(self.http_client),
            ]
        return [s for s in self._sources if s.is_available()]

    def _get_artist_sources(self) -> List["ArtistCoverSource"]:
        """Get artist cover sources."""
        from services.sources import (
            NetEaseArtistCoverSource,
            QQMusicArtistCoverSource,
            ITunesArtistCoverSource,
        )
        return [
            NetEaseArtistCoverSource(self.http_client),
            QQMusicArtistCoverSource(),
            ITunesArtistCoverSource(self.http_client),
        ]

    def get_cover(self, track_path: str, title: str, artist: str, album: str = "", duration: float = None,
                  skip_online: bool = False) -> Optional[str]:
        """
        Get cover art for a track, prioritizing cached/downloaded covers.

        Args:
            track_path: Path to the audio file
            title: Track title
            artist: Track artist
            album: Album name
            duration: Track duration in seconds (optional, for better matching)
            skip_online: If True, skip online fetching (used for cloud files before download completes)

        Returns:
            Path to the cover image, or None
        """
        # If title looks like a filename, try to parse artist and title from it
        search_title = title
        search_artist = artist
        search_album = album

        from utils.helpers import is_filename_like, parse_filename_as_metadata
        if is_filename_like(title) or (not artist and ' - ' in title):
            parsed_artist, parsed_title = parse_filename_as_metadata(title)
            if parsed_title:
                search_title = parsed_title
                if parsed_artist:
                    search_artist = parsed_artist
                logger.info(f"[CoverService] Parsed filename: '{title}' -> artist='{search_artist}', title='{search_title}'")

        # First check cached/downloaded covers (higher priority for user-downloaded covers)
        cache_key = self._get_cache_key(search_artist, search_album or search_title)
        logger.info(f"[CoverService] get_cover: cache_key={cache_key}, artist={search_artist}, album={search_album}, title={search_title}")
        cached_cover = self._get_cached_cover(cache_key)
        if cached_cover and cached_cover.exists():
            logger.info(f"[CoverService] Returning cached cover: {cached_cover}")
            return str(cached_cover)

        # Then try embedded cover
        cover_path = self._extract_embedded_cover(track_path)
        logger.info(f"[CoverService] embedded cover_path={cover_path}")
        if cover_path:
            return cover_path

        # Skip online fetching if requested (e.g., for cloud files before download completes)
        if skip_online:
            logger.info(f"[CoverService] Skipping online fetch (skip_online=True)")
            return None

        # Try online sources with smart matching
        logger.info(f"[CoverService] No cover found, trying online sources")
        return self._fetch_online_cover(search_title, search_artist, search_album, cache_key, duration)

    def _extract_embedded_cover(self, track_path: str) -> Optional[str]:
        """
        Extract embedded cover from audio file.

        Args:
            track_path: Path to the audio file

        Returns:
            Path to extracted cover, or None
        """
        # Early return if no path provided (e.g., for cloud files before download)
        if not track_path:
            return None

        try:
            from .metadata_service import MetadataService

            # Create cache directory if needed
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

            # Generate cache filename (use MD5 for deterministic hash)
            track_file = Path(track_path)
            path_hash = hashlib.md5(track_path.encode()).hexdigest()[:16]
            cache_filename = f"{track_file.stem}_{path_hash}.jpg"
            cache_path = self.CACHE_DIR / cache_filename

            # Check if already cached
            if cache_path.exists():
                return str(cache_path)

            # Extract cover using metadata service
            if MetadataService.save_cover(track_path, str(cache_path)):
                return str(cache_path)

        except Exception as e:
            logger.debug(f"Error extracting embedded cover from {track_path}: {e}")

        return None

    def save_cover_from_metadata(self, track_path: str, cover_data: bytes) -> Optional[str]:
        """
        Save cover art from already extracted metadata.

        Args:
            track_path: Path to the audio file (used for generating cache filename)
            cover_data: Cover image data from metadata

        Returns:
            Path to saved cover, or None
        """
        if not cover_data:
            return None

        try:
            # Create cache directory if needed
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

            # Generate cache filename (use MD5 for deterministic hash)
            track_file = Path(track_path)
            path_hash = hashlib.md5(track_path.encode()).hexdigest()[:16]
            # Determine extension from data
            if cover_data[:4] == b'\x89PNG':
                ext = '.png'
            else:
                ext = '.jpg'
            cache_filename = f"{track_file.stem}_{path_hash}{ext}"
            cache_path = self.CACHE_DIR / cache_filename

            # Check if already cached
            if cache_path.exists():
                return str(cache_path)

            # Save cover data
            with open(cache_path, 'wb') as f:
                f.write(cover_data)

            return str(cache_path)

        except Exception as e:
            logger.error(f"Error saving cover from metadata: {e}", exc_info=True)
            return None

    def _get_cache_key(self, artist: str, album: str) -> str:
        """Generate cache key for cover art."""
        key = f"{artist}:{album}".lower()
        return hashlib.md5(key.encode()).hexdigest()

    def _get_cached_cover(self, cache_key: str) -> Optional[Path]:
        """Get cached cover by cache key."""
        for ext in ['.jpg', '.jpeg', '.png']:
            cover_path = self.CACHE_DIR / f"{cache_key}{ext}"
            if cover_path.exists():
                return cover_path
        return None

    def fetch_online_cover(self, title: str, artist: str, album: str = "", duration: float = None) -> Optional[str]:
        """
        Fetch cover art from online sources (public method).

        This method always attempts to download cover from online sources,
        regardless of whether an embedded cover exists.

        Args:
            title: Track title
            artist: Track artist
            album: Album name
            duration: Track duration in seconds (optional, for better matching)

        Returns:
            Path to downloaded cover, or None if no suitable cover found
        """
        cache_key = self._get_cache_key(artist, album or title)
        return self._fetch_online_cover(title, artist, album, cache_key, duration)

    def get_online_cover(self, song_mid: str, album_mid: str = None,
                         artist: str = "", title: str = "") -> Optional[str]:
        """
        Get cover for online QQ Music track by song_mid or album_mid.

        This directly fetches cover from QQ Music without searching.

        Args:
            song_mid: QQ Music song MID
            album_mid: QQ Music album MID (preferred, if available)
            artist: Artist name (for cache key)
            title: Track title (for cache key)

        Returns:
            Path to cached cover, or None
        """
        if not song_mid and not album_mid:
            return None

        # Check cache first
        cache_key = self._get_cache_key(artist, title)
        cached_cover = self._get_cached_cover(cache_key)
        if cached_cover and cached_cover.exists():
            return str(cached_cover)

        try:
            from services.lyrics.qqmusic_lyrics import get_qqmusic_cover_url

            # Get cover URL
            cover_url = get_qqmusic_cover_url(mid=song_mid, album_mid=album_mid, size=500)
            if not cover_url:
                logger.debug(f"[CoverService] No cover URL for song_mid={song_mid}, album_mid={album_mid}")
                return None

            logger.debug(f"[CoverService] Got cover URL: {cover_url}")

            # Download cover
            cover_data = self.http_client.get_content(cover_url, timeout=5)
            if cover_data:
                return self._save_cover_to_cache(cover_data, cache_key)

        except Exception as e:
            logger.error(f"[CoverService] Error getting online cover: {e}")

        return None

    def _fetch_online_cover(self, title: str, artist: str, album: str, cache_key: str, duration: float = None) -> \
    Optional[str]:
        """
        Fetch cover art from online sources with smart matching.

        Args:
            title: Track title
            artist: Track artist
            album: Album name
            cache_key: Cache key for storing the cover
            duration: Track duration in seconds (optional, for better matching)

        Returns:
            Path to downloaded cover, or None
        """
        all_results: List[SearchResult] = []

        sources = self._get_sources()

        # Parallel search from multiple sources
        with ThreadPoolExecutor(max_workers=len(sources)) as executor:
            futures = {
                executor.submit(source.search, title, artist, album, duration): source.name
                for source in sources
            }

            for future in as_completed(futures, timeout=15):
                source_name = futures[future]
                try:
                    search_results = future.result()
                    # Convert CoverSearchResult to SearchResult for compatibility
                    for r in search_results:
                        all_results.append(SearchResult(
                            title=r.title,
                            artist=r.artist,
                            album=r.album,
                            duration=r.duration,
                            source=r.source,
                            id=r.id,
                            cover_url=r.cover_url,
                            album_mid=getattr(r, 'album_mid', None),
                        ))
                    logger.debug(f"{source_name} found {len(search_results)} results")
                except Exception as e:
                    logger.warning(f"Error searching cover from {source_name}: {e}")

        # Find best match from all collected results (use 'cover' mode - album highest weight)
        if all_results:
            track_info = TrackInfo(
                title=title,
                artist=artist,
                album=album,
                duration=duration
            )
            best_match = MatchScorer.find_best_match(track_info, all_results, mode='cover')

            if best_match:
                result, score = best_match
                logger.info(
                    f"Best cover match: {result.title} - {result.artist} (score: {score:.1f}, source: {result.source})")

                if score >= 50 and result.cover_url:
                    cover_data = self.http_client.get_content(result.cover_url, timeout=5)
                    if cover_data:
                        return self._save_cover_to_cache(cover_data, cache_key)

        return None

    def search_covers(self, title: str, artist: str, album: str = "", duration: float = None) -> List[dict]:
        """
        Search for covers from online sources (for manual download dialog).

        Args:
            title: Track title
            artist: Track artist
            album: Album name
            duration: Track duration in seconds

        Returns:
            List of dicts with cover info for UI display
        """
        results = []
        all_search_results: List[SearchResult] = []

        sources = self._get_sources()

        # Parallel search from multiple sources
        with ThreadPoolExecutor(max_workers=len(sources)) as executor:
            futures = {
                executor.submit(source.search, title, artist, album, duration): source.name
                for source in sources
            }

            for future in as_completed(futures, timeout=15):
                source_name = futures[future]
                try:
                    search_results = future.result()
                    # Convert CoverSearchResult to SearchResult for compatibility
                    for r in search_results:
                        all_search_results.append(SearchResult(
                            title=r.title,
                            artist=r.artist,
                            album=r.album,
                            duration=r.duration,
                            source=r.source,
                            id=r.id,
                            cover_url=r.cover_url,
                            album_mid=getattr(r, 'album_mid', None),
                        ))
                except Exception as e:
                    logger.error(f"Error searching {source_name} covers: {e}", exc_info=True)

        # Use MatchScorer to rank all results (use 'cover' mode - album highest weight)
        if all_search_results:
            track_info = TrackInfo(
                title=title,
                artist=artist,
                album=album,
                duration=duration
            )

            for result in all_search_results:
                score = MatchScorer.calculate_score(track_info, result, mode='cover')
                results.append({
                    'title': result.title,
                    'artist': result.artist,
                    'album': result.album,
                    'duration': result.duration,
                    'cover_url': result.cover_url,
                    'source': result.source,
                    'id': result.id,
                    'score': score,
                    'album_mid': result.album_mid,  # For QQ Music lazy cover fetch
                })

            # Sort by score descending
            results.sort(key=lambda x: x['score'], reverse=True)

        return results

    def download_cover_by_url(self, cover_url: str, artist: str, title: str, album: str = "") -> Optional[str]:
        """
        Download cover from URL and save to cache.

        Args:
            cover_url: URL to download cover from
            artist: Artist name (for cache key)
            title: Track title (for cache key)
            album: Album name (for cache key)

        Returns:
            Path to cached cover, or None
        """
        try:
            cover_data = self.http_client.get_content(cover_url, timeout=5)
            if cover_data:
                cache_key = self._get_cache_key(artist, album or title)
                return self._save_cover_to_cache(cover_data, cache_key)
        except Exception as e:
            logger.error(f"Error downloading cover from URL: {e}", exc_info=True)

        return None

    def _save_cover_to_cache(self, cover_data: bytes, cache_key: str) -> Optional[str]:
        """
        Save cover data to cache.

        Args:
            cover_data: Image data
            cache_key: Cache key

        Returns:
            Path to cached cover, or None
        """
        try:
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

            # Delete old cached covers with different extensions
            for old_ext in ['.jpg', '.jpeg', '.png']:
                old_path = self.CACHE_DIR / f"{cache_key}{old_ext}"
                if old_path.exists():
                    old_path.unlink()
                    logger.debug(f"Deleted old cached cover: {old_path}")

            # Try to determine format from data
            if cover_data[:4] == b'\x89PNG':
                ext = '.png'
            else:
                ext = '.jpg'

            cache_path = self.CACHE_DIR / f"{cache_key}{ext}"

            with open(cache_path, 'wb') as f:
                f.write(cover_data)

            return str(cache_path)

        except Exception as e:
            logger.error(f"Error saving cover to cache: {e}", exc_info=True)
            return None

    def clear_cache(self):
        """Clear all cached cover art."""
        try:
            if self.CACHE_DIR.exists():
                for file in self.CACHE_DIR.iterdir():
                    if file.is_file():
                        file.unlink()
        except Exception as e:
            logger.error(f"Error clearing cover cache: {e}", exc_info=True)

    def save_cover_data_to_cache(self, cover_data: bytes, artist: str, title: str, album: str = "") -> Optional[str]:
        """
        Save cover data to cache using artist and album/title.

        This is a convenience method for saving already-downloaded cover data.

        Args:
            cover_data: Image data
            artist: Artist name (used for cache key)
            title: Track title (used for cache key if no album)
            album: Album name (used for cache key if available)

        Returns:
            Path to cached cover, or None
        """
        cache_key = self._get_cache_key(artist, album or title)
        return self._save_cover_to_cache(cover_data, cache_key)

    def search_artist_covers(self, artist_name: str, limit: int = 10) -> List[dict]:
        """
        Search for artist covers from online sources in parallel.

        Args:
            artist_name: Artist name to search
            limit: Maximum number of results

        Returns:
            List of dicts with artist cover info
        """
        results = []
        sources = self._get_artist_sources()

        with ThreadPoolExecutor(max_workers=len(sources)) as executor:
            futures = {
                executor.submit(source.search, artist_name, limit): source.name
                for source in sources
            }

            for future in as_completed(futures, timeout=15):
                source_name = futures[future]
                try:
                    search_results = future.result()
                    # Convert ArtistCoverSearchResult to dict for compatibility
                    for r in search_results:
                        score = self._calculate_artist_name_score(artist_name, r.name)
                        results.append({
                            'name': r.name,
                            'id': r.id,
                            'cover_url': r.cover_url,
                            'album_count': r.album_count,
                            'source': r.source,
                            'singer_mid': r.singer_mid,
                            'score': score,
                        })
                except Exception as e:
                    logger.error(f"Error searching artist covers from {source_name}: {e}", exc_info=True)

        # Sort by score descending
        results.sort(key=lambda x: x['score'], reverse=True)

        return results

    def _calculate_artist_name_score(self, query: str, name: str) -> float:
        """Calculate similarity score between query and artist name."""
        query_lower = query.lower().strip()
        name_lower = name.lower().strip()

        if query_lower == name_lower:
            return 100.0

        if query_lower in name_lower or name_lower in query_lower:
            return 85.0

        # Word-level matching
        query_words = set(query_lower.split())
        name_words = set(name_lower.split())

        if query_words & name_words:
            common = len(query_words & name_words)
            total = max(len(query_words), len(name_words))
            return 70.0 + (common / total) * 15

        return 50.0
