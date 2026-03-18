"""
Cover art service for extracting and fetching album covers.
"""
import hashlib
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional, List

from infrastructure.network import HttpClient
from utils.match_scorer import MatchScorer, TrackInfo, SearchResult

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
        # First check cached/downloaded covers (higher priority for user-downloaded covers)
        cache_key = self._get_cache_key(artist, album or title)
        logger.info(f"[CoverService] get_cover: cache_key={cache_key}, artist={artist}, album={album}, title={title}")
        cached_cover = self._get_cached_cover(cache_key)
        logger.info(f"[CoverService] cached_cover={cached_cover}")
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
        return self._fetch_online_cover(title, artist, album, cache_key, duration)

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

        # Define search tasks
        search_tasks = [
            ("NetEase", lambda: self._search_covers_from_netease(title, artist, album, duration)),
            # ("QQMusic", lambda: self._search_covers_from_qqmusic(title, artist, album, duration)),
            ("iTunes", lambda: self._search_covers_from_itunes(title, artist, album)),
            # ("Spotify", lambda: self._search_covers_from_spotify(title, artist, album)),
        ]

        # Parallel search from multiple sources
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(task[1]): task[0]
                for task in search_tasks
            }

            for future in as_completed(futures):
                source_name = futures[future]
                try:
                    results = future.result()
                    all_results.extend(results)
                    logger.debug(f"{source_name} found {len(results)} results")
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

        # Fallback to other sources (without smart matching) - parallel
        fallback_sources = [
            ("MusicBrainz", lambda: self._fetch_from_musicbrainz(artist, album or title)),
            ("Last.fm", lambda: self._fetch_from_lastfm(artist, album or title)),
        ]

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                executor.submit(src[1]): src[0]
                for src in fallback_sources
            }

            for future in as_completed(futures):
                source_name = futures[future]
                try:
                    cover_data = future.result()
                    if cover_data:
                        return self._save_cover_to_cache(cover_data, cache_key)
                except Exception as e:
                    logger.warning(f"Error fetching cover from {source_name}: {e}")

        return None

    def _search_covers_from_netease(self, title: str, artist: str, album: str, duration: float = None) -> List[
        SearchResult]:
        """
        Search for covers from NetEase Cloud Music.

        Args:
            title: Track title
            artist: Track artist
            album: Album name
            duration: Track duration in seconds

        Returns:
            List of SearchResult objects with cover URLs
        """
        results = []

        try:
            search_url = "https://music.163.com/api/search/get/web"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://music.163.com/'
            }

            # First try album search
            params = {
                's': f'{artist} {album or title}',
                'type': 10,  # album search
                'limit': 5
            }

            response = self.http_client.get(
                search_url,
                params=params,
                headers=headers,
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()

                if data.get('code') == 200 and data.get('result', {}).get('albums'):
                    for album_info in data['result']['albums']:
                        pic_url = album_info.get('picUrl') or album_info.get('blurPicUrl')
                        if pic_url:
                            # Get high quality version
                            if '?' not in pic_url:
                                pic_url += '?param=500y500'

                            results.append(SearchResult(
                                title=album_info.get('name', ''),
                                artist=album_info.get('artist', {}).get('name', ''),
                                album=album_info.get('name', ''),
                                duration=None,
                                source='netease',
                                id=str(album_info.get('id', '')),
                                cover_url=pic_url
                            ))

            # Also try song search for more accurate matching
            params = {
                's': f'{artist} {title}',
                'type': 1,  # song search
                'limit': 5
            }

            response = self.http_client.get(
                search_url,
                params=params,
                headers=headers,
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()

                if data.get('code') == 200 and data.get('result', {}).get('songs'):
                    for song in data['result']['songs']:
                        album_info = song.get('album', {})
                        pic_url = album_info.get('picUrl') or album_info.get('blurPicUrl')

                        if pic_url:
                            if '?' not in pic_url:
                                pic_url += '?param=500y500'

                            song_duration = None
                            if song.get('duration'):
                                song_duration = song['duration'] / 1000

                            results.append(SearchResult(
                                title=song.get('name', ''),
                                artist=song['artists'][0]['name'] if song.get('artists') else '',
                                album=album_info.get('name', ''),
                                duration=song_duration,
                                source='netease',
                                id=str(song.get('id', '')),
                                cover_url=pic_url
                            ))

        except Exception as e:
            logger.debug(f"NetEase cover search error: {e}")

        return results

    def _search_covers_from_qqmusic(self, title: str, artist: str, album: str, duration: float = None) -> List[
        SearchResult]:
        """
        Search for covers from QQ Music.

        Args:
            title: Track title
            artist: Track artist
            album: Album name
            duration: Track duration in seconds

        Returns:
            List of SearchResult objects (cover_url fetched lazily on click)
        """
        results = []

        try:
            from services.lyrics.qqmusic_lyrics import QQMusicClient

            client = QQMusicClient()

            # Search for songs
            keyword = f"{artist} {title}" if artist else title
            songs = client.search(keyword, limit=5)

            for song in songs:
                # Parse artist from singer list
                artist_name = ""
                if isinstance(song.get('singer'), list) and song['singer']:
                    artist_name = song['singer'][0].get('name', '')

                # Parse album from album dict
                album_name = ""
                album_mid = ""
                album_data = song.get('album')
                logger.debug(f"QQ Music song album data: {album_data}")
                if isinstance(album_data, dict):
                    album_name = album_data.get('name', '')
                    album_mid = album_data.get('mid', '')
                    logger.debug(f"QQ Music album_mid: {album_mid}")

                # Store album_mid for lazy cover fetch, don't get cover_url now
                results.append(SearchResult(
                    title=song.get('name', ''),
                    artist=artist_name,
                    album=album_name,
                    duration=song.get('interval'),  # Already in seconds
                    source='qqmusic',
                    id=song.get('mid', ''),
                    cover_url=None,  # Lazy fetch on click
                    album_mid=album_mid
                ))

        except Exception as e:
            logger.debug(f"QQ Music cover search error: {e}")

        return results

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

        # Define search tasks
        search_tasks = [
            ("NetEase", lambda: self._search_covers_from_netease(title, artist, album, duration)),
            ("QQMusic", lambda: self._search_covers_from_qqmusic(title, artist, album, duration)),
            ("iTunes", lambda: self._search_covers_from_itunes(title, artist, album)),
            # ("Spotify", lambda: self._search_covers_from_spotify(title, artist, album)),
            ("Last.fm", lambda: self._search_covers_from_lastfm(artist, album or title)),
        ]

        # Parallel search from multiple sources
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(task[1]): task[0]
                for task in search_tasks
            }

            for future in as_completed(futures, timeout=15):
                source_name = futures[future]
                try:
                    search_results = future.result()
                    all_search_results.extend(search_results)
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

    def _fetch_from_netease(self, artist: str, album: str) -> Optional[bytes]:
        """
        Fetch cover from NetEase Cloud Music API.

        Args:
            artist: Artist name
            album: Album name

        Returns:
            Cover image data, or None
        """
        try:
            # Search for album/song
            search_url = "https://music.163.com/api/search/get/web"
            params = {
                's': f'{artist} {album}',
                'type': 10,  # 10 = album search
                'limit': 1
            }
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://music.163.com/'
            }

            response = self.http_client.get(
                search_url,
                params=params,
                headers=headers,
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()

                # Check for album results
                if data.get('code') == 200 and data.get('result', {}).get('albums'):
                    album_info = data['result']['albums'][0]
                    pic_url = album_info.get('picUrl') or album_info.get('blurPicUrl')

                    if pic_url:
                        # Get high quality version
                        if '?' not in pic_url:
                            pic_url += '?param=500y500'
                        cover_data = self.http_client.get_content(pic_url, timeout=5)
                        if cover_data:
                            return cover_data

                # Fallback: try song search if album search failed
                params['type'] = 1  # 1 = song search
                response = self.http_client.get(
                    search_url,
                    params=params,
                    headers=headers,
                    timeout=5
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get('code') == 200 and data.get('result', {}).get('songs'):
                        song_info = data['result']['songs'][0]
                        # Try to get album cover from song
                        album_info = song_info.get('album', {})
                        pic_url = album_info.get('picUrl') or album_info.get('blurPicUrl')

                        if pic_url:
                            if '?' not in pic_url:
                                pic_url += '?param=500y500'
                            cover_data = self.http_client.get_content(pic_url, timeout=5)
                            if cover_data:
                                return cover_data

        except Exception as e:
            logger.debug(f"NetEase fetch error: {e}")

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
            api_key = "9b0cdcf446cc96dea3e747787ad23575"

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

    def _search_covers_from_musicbrainz(self, artist: str, album: str) -> List[SearchResult]:
        """
        Search for covers from MusicBrainz Cover Art Archive.

        Args:
            artist: Artist name
            album: Album name

        Returns:
            List of SearchResult objects with cover URLs
        """
        results = []

        try:
            search_url = "https://musicbrainz.org/ws/2/release/"
            params = {
                'query': f'artist:"{artist}" AND release:"{album}"',
                'limit': 5,
                'fmt': 'json'
            }

            response = self.http_client.get(
                search_url,
                params=params,
                headers={'User-Agent': 'HarmonyPlayer/1.0'},
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('releases'):
                    for release in data['releases']:
                        release_id = release.get('id')
                        if release_id:
                            # Construct cover art URL
                            cover_url = f"https://coverartarchive.org/release/{release_id}/front-500"

                            results.append(SearchResult(
                                title=release.get('title', ''),
                                artist=', '.join([a.get('name', '') for a in release.get('artist-credit', []) if isinstance(a, dict) and 'name' in a]) or artist,
                                album=release.get('title', ''),
                                duration=None,
                                source='musicbrainz',
                                id=release_id,
                                cover_url=cover_url
                            ))

        except Exception as e:
            logger.debug(f"MusicBrainz search error: {e}")

        return results

    def _search_covers_from_lastfm(self, artist: str, album: str) -> List[SearchResult]:
        """
        Search for covers from Last.fm API.

        Args:
            artist: Artist name
            album: Album name

        Returns:
            List of SearchResult objects with cover URLs
        """
        results = []

        import os
        api_key = os.getenv("LASTFM_API_KEY")
        if not api_key or api_key == "YOUR_LASTFM_API_KEY":
            api_key = "52e8e86c171ed9affffa34580666927a"
            api_key = "94381a2146e972044b745b93575ddeac"
            api_key = "9b0cdcf446cc96dea3e747787ad23575"

        try:
            url = "http://ws.audioscrobbler.com/2.0/"
            params = {
                'method': 'album.getinfo',
                'api_key': api_key,
                'artist': artist,
                'album': album,
                'format': 'json'
            }

            response = self.http_client.get(url, params=params, timeout=5)

            if response.status_code == 200:
                data = response.json()

                if 'error' in data:
                    logger.debug(f"Last.fm API error: {data.get('message')}")
                    return results

                if 'album' in data:
                    album_info = data['album']
                    image_url = None

                    # Get the largest image
                    if 'image' in album_info:
                        for img in reversed(album_info['image']):
                            if img.get('#text'):
                                image_url = img['#text']
                                break

                    if image_url:
                        results.append(SearchResult(
                            title=album_info.get('name', ''),
                            artist=album_info.get('artist', ''),
                            album=album_info.get('name', ''),
                            duration=None,
                            source='lastfm',
                            id=album_info.get('mbid', ''),
                            cover_url=image_url
                        ))

        except Exception as e:
            logger.debug(f"Last.fm search error: {e}")

        return results

    def _search_covers_from_itunes(self, title: str, artist: str, album: str) -> List[SearchResult]:
        """
        Search for covers from iTunes Search API.

        Args:
            title: Track title
            artist: Track artist
            album: Album name

        Returns:
            List of SearchResult objects with cover URLs
        """
        results = []

        try:
            search_url = "https://itunes.apple.com/search"

            # Search for albums
            params = {
                'term': f'{artist} {album or title}',
                'media': 'music',
                'entity': 'album',
                'limit': 5
            }

            response = self.http_client.get(search_url, params=params, timeout=3)

            if response.status_code == 200:
                data = response.json()
                if data.get('results'):
                    for item in data['results']:
                        artwork_url = item.get('artworkUrl100')
                        if artwork_url:
                            # Get larger version
                            artwork_url = artwork_url.replace('100x100', '600x600')

                            results.append(SearchResult(
                                title=item.get('collectionName', ''),
                                artist=item.get('artistName', ''),
                                album=item.get('collectionName', ''),
                                duration=None,
                                source='itunes',
                                id=str(item.get('collectionId', '')),
                                cover_url=artwork_url
                            ))

            # If album has value, also search with album only (without artist)
            if album:
                params_album_only = {
                    'term': album,
                    'media': 'music',
                    'entity': 'album',
                    'limit': 5
                }

                response = self.http_client.get(search_url, params=params_album_only, timeout=3)

                if response.status_code == 200:
                    data = response.json()
                    if data.get('results'):
                        for item in data['results']:
                            artwork_url = item.get('artworkUrl100')
                            if artwork_url:
                                artwork_url = artwork_url.replace('100x100', '600x600')

                                results.append(SearchResult(
                                    title=item.get('collectionName', ''),
                                    artist=item.get('artistName', ''),
                                    album=item.get('collectionName', ''),
                                    duration=None,
                                    source='itunes',
                                    id=str(item.get('collectionId', '')),
                                    cover_url=artwork_url
                                ))

        except Exception as e:
            logger.debug(f"iTunes search error: {e}")

        return results

    def _search_covers_from_spotify(self, title: str, artist: str, album: str) -> List[SearchResult]:
        """
        Search for album covers from Spotify Web API.

        Args:
            title: Track title
            artist: Track artist
            album: Album name

        Returns:
            List of SearchResult objects with cover URLs
        """
        results = []

        token = self._get_spotify_token()
        if not token:
            logger.debug("Failed to get Spotify token for album search")
            return results

        try:
            url = "https://api.spotify.com/v1/search"
            headers = {
                "Authorization": f"Bearer {token}"
            }

            # Build search query
            search_album = album or title
            params = {
                "q": f"album:{search_album} artist:{artist}",
                "type": "album",
                "limit": 5
            }

            response = self.http_client.get(url, headers=headers, params=params, timeout=5)

            if response.status_code == 200:
                data = response.json()
                albums = data.get("albums", {}).get("items", [])

                for album_info in albums:
                    images = album_info.get("images", [])
                    if images:
                        # Get the largest image (first in list)
                        cover_url = images[0].get("url")

                        if cover_url:
                            results.append(SearchResult(
                                title=album_info.get("name", ""),
                                artist=album_info.get("artists", [{}])[0].get("name", ""),
                                album=album_info.get("name", ""),
                                duration=None,
                                source='spotify',
                                id=album_info.get("id", ""),
                                cover_url=cover_url
                            ))

            # If album has value, also search with album only (without artist)
            if album:
                params_album_only = {
                    "q": f"album:{album}",
                    "type": "album",
                    "limit": 5
                }

                response = self.http_client.get(url, headers=headers, params=params_album_only, timeout=5)

                if response.status_code == 200:
                    data = response.json()
                    albums = data.get("albums", {}).get("items", [])

                    for album_info in albums:
                        images = album_info.get("images", [])
                        if images:
                            cover_url = images[0].get("url")

                            if cover_url:
                                results.append(SearchResult(
                                    title=album_info.get("name", ""),
                                    artist=album_info.get("artists", [{}])[0].get("name", ""),
                                    album=album_info.get("name", ""),
                                    duration=None,
                                    source='spotify',
                                    id=album_info.get("id", ""),
                                    cover_url=cover_url
                                ))

        except Exception as e:
            logger.debug(f"Spotify album search error: {e}")

        return results

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
            print(f'Cache path: {cache_path}')

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
        Search for artist covers from NetEase Cloud Music, iTunes, and QQ Music in parallel.

        Args:
            artist_name: Artist name to search
            limit: Maximum number of results

        Returns:
            List of dicts with artist cover info
        """
        results = []

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(self._search_artist_covers_from_netease, artist_name, limit): 'netease',
                executor.submit(self._search_artist_covers_from_itunes, artist_name, limit): 'itunes',
                executor.submit(self._search_artist_covers_from_qqmusic, artist_name, limit): 'qqmusic'
            }

            for future in as_completed(futures):
                try:
                    source_results = future.result()
                    results.extend(source_results)
                except Exception as e:
                    source = futures[future]
                    logger.error(f"Error searching artist covers from {source}: {e}", exc_info=True)

        # Sort by score descending
        results.sort(key=lambda x: x['score'], reverse=True)

        return results

    def _search_artist_covers_from_netease(self, artist_name: str, limit: int) -> List[dict]:
        """Search artist covers from NetEase Cloud Music."""
        results = []

        search_url = "https://music.163.com/api/search/get/web"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://music.163.com/'
        }

        params = {
            's': artist_name,
            'type': 100,  # Artist search
            'limit': limit,
            'offset': 0
        }

        response = self.http_client.get(
            search_url,
            params=params,
            headers=headers,
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()

            if data.get('code') == 200 and data.get('result', {}).get('artists'):
                for artist_info in data['result']['artists']:
                    pic_url = artist_info.get('picUrl') or artist_info.get('img1v1Url')
                    if pic_url:
                        # Get high quality version
                        if '?' not in pic_url:
                            pic_url += '?param=512y512'

                        # Calculate match score based on name similarity
                        name = artist_info.get('name', '')
                        score = self._calculate_artist_name_score(artist_name, name)

                        results.append({
                            'name': name,
                            'id': artist_info.get('id'),
                            'cover_url': pic_url,
                            'album_count': artist_info.get('albumSize', 0),
                            'score': score,
                            'source': 'netease'
                        })

        return results

    def _search_artist_covers_from_itunes(self, artist_name: str, limit: int) -> List[dict]:
        """Search artist covers from iTunes."""
        results = []

        search_url = "https://itunes.apple.com/search"
        params = {
            'term': artist_name,
            'media': 'music',
            'entity': 'album',
            'limit': limit
        }

        response = self.http_client.get(search_url, params=params, timeout=5)

        if response.status_code == 200:
            data = response.json()
            if data.get('results'):
                seen_artists = set()
                for item in data['results']:
                    name = item.get('artistName', '')
                    # Skip duplicate artists
                    if name.lower() in seen_artists:
                        continue
                    seen_artists.add(name.lower())

                    artwork_url = item.get('artworkUrl100')
                    if artwork_url:
                        artwork_url = artwork_url.replace('100x100', '600x600')

                        # Calculate match score
                        score = self._calculate_artist_name_score(artist_name, name)

                        results.append({
                            'name': name,
                            'id': item.get('artistId'),
                            'cover_url': artwork_url,
                            'album_count': None,
                            'score': score,
                            'source': 'itunes'
                        })

        return results

    def parse(self, url: str):
        """
        解析QQ音乐封面URL
        """
        pattern = r"(T\d{3})R\d+x\d+M000([A-Za-z0-9]+)"
        m = re.search(pattern, url)

        if not m:
            return "", ""

        img_type = m.group(1)
        mid = m.group(2)

        return img_type, mid

    def convert(self, url: str, size: int = 500) -> str:
        """
        转换为指定尺寸
        """
        img_type, mid = self.parse(url)

        return f"https://y.gtimg.cn/music/photo_new/{img_type}R{size}x{size}M000{mid}.jpg"

    def _search_artist_covers_from_qqmusic(self, artist_name: str, limit: int) -> List[dict]:
        """Search artist covers from QQ Music (lazy loading)."""
        results = []

        try:
            from services.lyrics.qqmusic_lyrics import QQMusicClient

            client = QQMusicClient()
            artists = client.search_artist(artist_name, limit)

            for artist in artists:
                name = artist.get('singerName', '')
                singer_mid = artist.get('singerMID', '')
                cover_url = artist.get('singerPic', '')
                album_count = artist.get('albumNum', 0)

                if name and singer_mid:
                    # Calculate match score
                    score = self._calculate_artist_name_score(artist_name, name)

                    cover_url = self.convert(cover_url)
                    results.append({
                        'name': name,
                        'id': singer_mid,
                        'singer_mid': singer_mid,
                        'cover_url': cover_url,
                        'album_count': album_count,
                        'score': score,
                        'source': 'qqmusic'
                    })

        except Exception as e:
            logger.debug(f"QQ Music artist cover search error: {e}")

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

    # Spotify API credentials
    SPOTIFY_CLIENT_ID = "83e307eab4cc4e9bab3382b5bc13cc67"
    SPOTIFY_CLIENT_SECRET = "cbb426252fa44f5bb26334b3aa651fa8"
    _spotify_token = None
    _spotify_token_expires = 0

    def _get_spotify_token(self) -> Optional[str]:
        """
        Get Spotify API access token using client credentials flow.

        Returns:
            Access token, or None if failed
        """
        import base64
        import time

        # Check if we have a valid cached token
        if self._spotify_token and time.time() < self._spotify_token_expires:
            return self._spotify_token

        try:
            auth = base64.b64encode(
                f"{self.SPOTIFY_CLIENT_ID}:{self.SPOTIFY_CLIENT_SECRET}".encode()
            ).decode()

            headers = {
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/x-www-form-urlencoded"
            }

            data = {
                "grant_type": "client_credentials"
            }

            response = self.http_client.post(
                "https://accounts.spotify.com/api/token",
                headers=headers,
                data=data,
                timeout=5
            )

            if response.status_code == 200:
                token_data = response.json()
                self._spotify_token = token_data["access_token"]
                # Set expiry with 60 seconds buffer
                self._spotify_token_expires = time.time() + token_data.get("expires_in", 3600) - 60
                return self._spotify_token

        except Exception as e:
            logger.debug(f"Error getting Spotify token: {e}")

        return None

    def _search_artist_covers_from_spotify(self, artist_name: str, limit: int = 5) -> List[dict]:
        """
        Search for artist covers from Spotify Web API.

        Args:
            artist_name: Artist name to search
            limit: Maximum number of results

        Returns:
            List of dicts with artist cover info
        """
        results = []

        token = self._get_spotify_token()
        if not token:
            logger.debug("Failed to get Spotify token")
            return results

        try:
            url = "https://api.spotify.com/v1/search"
            headers = {
                "Authorization": f"Bearer {token}"
            }
            params = {
                "q": artist_name,
                "type": "artist",
                "limit": limit
            }

            response = self.http_client.get(url, headers=headers, params=params, timeout=5)

            if response.status_code == 200:
                data = response.json()
                if data.get("artists", {}).get("items"):
                    for artist_info in data["artists"]["items"]:
                        name = artist_info.get("name", "")
                        images = artist_info.get("images", [])

                        if images:
                            # Get the largest image (first in list is usually largest)
                            cover_url = images[0].get("url")

                            if cover_url:
                                # Calculate match score
                                score = self._calculate_artist_name_score(artist_name, name)

                                results.append({
                                    'name': name,
                                    'id': artist_info.get("id"),
                                    'cover_url': cover_url,
                                    'album_count': artist_info.get("popularity", 0),
                                    'score': score,
                                    'source': 'spotify'
                                })

        except Exception as e:
            logger.debug(f"Spotify artist search error: {e}")

        return results
