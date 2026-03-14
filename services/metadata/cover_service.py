"""
Cover art service for extracting and fetching album covers.
"""
import logging
from pathlib import Path
from typing import Optional
import hashlib

from infrastructure.network import HttpClient

# Configure logging
logger = logging.getLogger(__name__)


class CoverService:
    """Service for extracting and fetching album covers."""

    # Cache directory
    CACHE_DIR = Path.home() / '.cache' / 'harmony_player' / 'covers'

    def __init__(self, http_client: HttpClient):
        """
        Initialize cover service.

        Args:
            http_client: HTTP client for fetching cover art
        """
        self.http_client = http_client

    def get_cover(self, track_path: str, title: str, artist: str, album: str = "") -> Optional[str]:
        """
        Get cover art for a track, prioritizing embedded art.

        Args:
            track_path: Path to the audio file
            title: Track title
            artist: Track artist
            album: Album name

        Returns:
            Path to the cover image, or None
        """
        # First try embedded cover
        cover_path = self._extract_embedded_cover(track_path)
        if cover_path:
            return cover_path

        # Fall back to cached covers
        cache_key = self._get_cache_key(artist, album or title)
        cached_cover = self._get_cached_cover(cache_key)
        if cached_cover and cached_cover.exists():
            return str(cached_cover)

        # Try online sources
        return self._fetch_online_cover(title, artist, album, cache_key)

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

            # Generate cache filename
            track_file = Path(track_path)
            cache_filename = f"{track_file.stem}_{hash(track_path)}.jpg"
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

            # Generate cache filename
            track_file = Path(track_path)
            # Determine extension from data
            if cover_data[:4] == b'\x89PNG':
                ext = '.png'
            else:
                ext = '.jpg'
            cache_filename = f"{track_file.stem}_{hash(track_path)}{ext}"
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

    def _fetch_online_cover(self, title: str, artist: str, album: str, cache_key: str) -> Optional[str]:
        """
        Fetch cover art from online sources.

        Args:
            title: Track title
            artist: Track artist
            album: Album name
            cache_key: Cache key for storing the cover

        Returns:
            Path to downloaded cover, or None
        """
        sources = [
            ("iTunes", self._fetch_from_itunes),
            ("MusicBrainz", self._fetch_from_musicbrainz),
            ("Last.fm", self._fetch_from_lastfm),
        ]

        for source_name, source_func in sources:
            try:
                cover_data = source_func(artist, album or title)
                if cover_data:
                    return self._save_cover_to_cache(cover_data, cache_key)
            except Exception as e:
                logger.warning(f"Error fetching cover from {source_name}: {e}")
                continue

        return None

    def _fetch_from_lastfm(self, artist: str, album: str) -> Optional[bytes]:
        """
        Fetch cover from Last.fm API.

        Note: Requires a valid Last.fm API key. This source is disabled
        by default. To enable, set LASTFM_API_KEY in environment or config.

        Args:
            artist: Artist name
            album: Album name

        Returns:
            Cover image data, or None
        """
        import os

        api_key = os.getenv("LASTFM_API_KEY")
        if not api_key or api_key == "YOUR_LASTFM_API_KEY":
            logger.debug("Last.fm API key not configured, skipping")
            return None

        try:
            url = "http://ws.audioscrobbler.com/2.0/"

            params = {
                'method': 'album.getinfo',
                'api_key': api_key,
                'artist': artist,
                'album': album,
                'format': 'json'
            }

            response = self.http_client.get(url, params=params, timeout=3)

            if response.status_code == 200:
                data = response.json()
                image_url = None

                # Check for error
                if 'error' in data:
                    logger.debug(f"Last.fm API error: {data.get('message')}")
                    return None

                # Try to get the largest image
                if 'album' in data and 'image' in data['album']:
                    for img in reversed(data['album']['image']):
                        if img.get('#text'):
                            image_url = img['#text']
                            break

                if image_url:
                    cover_data = self.http_client.get_content(image_url, timeout=3)
                    if cover_data:
                        return cover_data

        except Exception as e:
            logger.debug(f"Last.fm fetch error: {e}")

        return None

    def _fetch_from_musicbrainz(self, artist: str, album: str) -> Optional[bytes]:
        """
        Fetch cover from MusicBrainz Cover Art Archive.

        Args:
            artist: Artist name
            album: Album name

        Returns:
            Cover image data, or None
        """
        try:
            # First, search for the release
            search_url = "https://musicbrainz.org/ws/2/release/"
            params = {
                'query': f'artist:"{artist}" AND release:"{album}"',
                'limit': 1,
                'fmt': 'json'
            }

            response = self.http_client.get(
                search_url,
                params=params,
                headers={'User-Agent': 'HarmonyPlayer/1.0'},
                timeout=3
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('releases'):
                    release_id = data['releases'][0]['id']

                    # Get cover art from Cover Art Archive
                    cover_url = f"https://coverartarchive.org/release/{release_id}/front-500"
                    cover_data = self.http_client.get_content(cover_url, timeout=3)

                    if cover_data:
                        return cover_data

        except Exception as e:
            logger.debug(f"MusicBrainz fetch error: {e}")

        return None

    def _fetch_from_itunes(self, artist: str, album: str) -> Optional[bytes]:
        """
        Fetch cover from iTunes Search API.

        Args:
            artist: Artist name
            album: Album name

        Returns:
            Cover image data, or None
        """
        try:
            search_url = "https://itunes.apple.com/search"
            params = {
                'term': f'{artist} {album}',
                'media': 'music',
                'entity': 'album',
                'limit': 1
            }

            response = self.http_client.get(search_url, params=params, timeout=3)

            if response.status_code == 200:
                data = response.json()
                if data.get('results') and len(data['results']) > 0:
                    artwork_url = data['results'][0].get('artworkUrl100')
                    if artwork_url:
                        # Get larger version
                        artwork_url = artwork_url.replace('100x100', '600x600')
                        cover_data = self.http_client.get_content(artwork_url, timeout=3)
                        if cover_data:
                            return cover_data

        except Exception as e:
            logger.debug(f"iTunes fetch error: {e}")

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

    def save_cover_data_to_cache(self, cover_data: bytes, artist: str, title: str) -> Optional[str]:
        """
        Save cover data to cache using artist and title.

        This is a convenience method for saving already-downloaded cover data.

        Args:
            cover_data: Image data
            artist: Artist name (used for cache key)
            title: Track title (used for cache key)

        Returns:
            Path to cached cover, or None
        """
        cache_key = self._get_cache_key(artist, title)
        return self._save_cover_to_cache(cover_data, cache_key)
