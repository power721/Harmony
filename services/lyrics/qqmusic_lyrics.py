"""
QQ Music lyrics provider.

Hybrid implementation: Uses local QQ Music API when credentials are available,
falls back to remote API (api.ygking.top) for public access.
"""
import logging
from typing import List, Optional, TYPE_CHECKING
import requests

if TYPE_CHECKING:
    from system.config import ConfigManager

logger = logging.getLogger(__name__)


def _get_client() -> 'QQMusicClient':
    """Get QQMusicClient from Bootstrap."""
    from app.bootstrap import Bootstrap
    return Bootstrap.instance().qqmusic_client


class QQMusicClient:
    """QQ Music API client with hybrid local/remote support."""

    REMOTE_BASE_URL = "https://api.ygking.top/api"

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    def __init__(self, timeout: int = 10):
        """
        Initialize QQ Music client with hybrid support.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self._local_client = None
        self._has_credentials = False

        # Initialize local client
        self._init_local_client()

    def _init_local_client(self):
        """Initialize local client with credentials."""
        # Try to initialize local client with credentials
        try:
            from services.cloud.qqmusic.client import QQMusicClient as QQMusicClientLocal
            from app.bootstrap import Bootstrap

            config = Bootstrap.instance().config
            credential = config.get_qqmusic_credential()

            logger.debug(f"QQ Music credential check: musicid={credential.get('musicid') if credential else 'None'}, "
                        f"has_musickey={bool(credential.get('musickey')) if credential else False}")

            if credential and credential.get('musicid') and credential.get('musickey'):
                # Ensure musicid is a non-empty string
                musicid = credential.get('musicid')
                if musicid and str(musicid) != '0' and str(musicid).strip():
                    # Check if credential has refresh capability
                    has_refresh = credential.get('refresh_key') and credential.get('refresh_token')
                    if not has_refresh:
                        logger.warning("Credential missing refresh_key/refresh_token, auto-refresh unavailable. "
                                      "Please re-login via QR code to get full credential.")

                    # Create client with callback for credential updates
                    self._local_client = QQMusicClientLocal(
                        credential,
                        on_credential_updated=lambda c: config.set_qqmusic_credential(c)
                    )
                    self._has_credentials = True
                    logger.info(f"Using local QQ Music API with credentials (musicid: {musicid})")

                    # Check if credential needs refresh
                    if self._local_client.needs_refresh():
                        logger.info("Credential needs refresh, attempting...")
                        self._refresh_and_save_credential(config)
                else:
                    logger.debug(f"Invalid musicid: {musicid}")
                    self._local_client = None
                    self._has_credentials = False
            else:
                self._local_client = None
                self._has_credentials = False
                logger.debug("No QQ Music credentials, will use remote API fallback")
        except Exception as e:
            logger.warning(f"Local QQ Music client unavailable: {e}")
            self._local_client = None
            self._has_credentials = False

    def _refresh_and_save_credential(self, config: 'ConfigManager'):
        """
        Refresh credential and save to config.

        Args:
            config: ConfigManager instance for saving updated credential
        """
        if not self._local_client:
            return

        try:
            updated = self._local_client.refresh_credential()
            if updated:
                config.set_qqmusic_credential(updated)
                logger.info("Credential refreshed and saved successfully")
            else:
                logger.warning("Credential refresh failed, will retry later")
        except Exception as e:
            logger.error(f"Error refreshing credential: {e}")

    def refresh_credentials(self):
        """Refresh credentials and reinitialize local client."""
        self._init_local_client()
        return self._has_credentials

    def _should_use_local(self) -> bool:
        """Check if we should use local API (has credentials and available)."""
        # Try to initialize if not already
        if not self._has_credentials or self._local_client is None:
            self._init_local_client()
        return self._has_credentials and self._local_client is not None

    def search(self, keyword: str, limit: int = 5) -> List[dict]:
        """
        Search for songs on QQ Music.

        Hybrid approach:
        - If credentials available: Use local QQ Music API (faster)
        - Otherwise: Fall back to remote API (api.ygking.top)

        Args:
            keyword: Search keyword
            limit: Maximum number of results

        Returns:
            List of song dicts with keys: mid, name, singer, album, duration
        """
        # Try local API first (if we have credentials)
        if self._should_use_local():
            try:
                result = self._local_client.search(keyword, search_type='song',
                                                  page_num=1, page_size=limit)

                if result and 'body' in result:
                    songs = result['body'].get('item_song', [])

                    formatted = []
                    for song in songs[:limit]:
                        singer_info = song.get('singer', {})
                        if isinstance(singer_info, list) and singer_info:
                            singer_name = singer_info[0].get('name', '')
                            singer_mid = singer_info[0].get('mid', '')
                        else:
                            singer_name = singer_info.get('name', '') if isinstance(singer_info, dict) else ''
                            singer_mid = ''

                        album_info = song.get('album', {})
                        album_name = album_info.get('name', '') if isinstance(album_info, dict) else ''
                        album_mid = album_info.get('mid', '') if isinstance(album_info, dict) else ''

                        formatted.append({
                            'mid': song.get('songmid', ''),
                            'name': song.get('songname', ''),
                            'title': song.get('songname', ''),
                            'singer': singer_name,
                            'singer_mid': singer_mid,
                            'album': album_name,
                            'album_mid': album_mid,
                            'interval': song.get('interval', 0),
                        })

                    if formatted:
                        logger.debug(f"QQ Music search via local API: {len(formatted)} results")
                        return formatted

            except Exception as e:
                logger.debug(f"Local QQ Music search failed: {e}, falling back to remote")

        # Fallback to remote API
        return self._search_remote(keyword, limit)

    def _search_remote(self, keyword: str, limit: int) -> List[dict]:
        """Search using remote API (fallback)."""
        url = f"{self.REMOTE_BASE_URL}/search"

        params = {
            "keyword": keyword,
            "type": "song",
            "num": limit,
            "page": 1,
        }

        try:
            session = requests.Session()
            r = session.get(url, params=params, headers=self.HEADERS, timeout=self.timeout)
            data = r.json()
            songs = data.get("data", {}).get("list", [])

            # Normalize format to match local API
            formatted = []
            for song in songs[:limit]:
                # Handle singer - could be list, dict, or string
                singer_info = song.get('singer', '')
                if isinstance(singer_info, list) and singer_info:
                    singer_name = singer_info[0].get('name', '') if isinstance(singer_info[0], dict) else str(singer_info[0])
                    singer_mid = singer_info[0].get('mid', '') if isinstance(singer_info[0], dict) else ''
                elif isinstance(singer_info, dict):
                    singer_name = singer_info.get('name', '')
                    singer_mid = singer_info.get('mid', '')
                else:
                    singer_name = str(singer_info) if singer_info else ''
                    singer_mid = ''

                # Handle album - could be dict or string
                album_info = song.get('album', '')
                if isinstance(album_info, dict):
                    album_name = album_info.get('name', '')
                    album_mid = album_info.get('mid', '')
                else:
                    album_name = str(album_info) if album_info else ''
                    album_mid = song.get('album_mid', '')

                formatted.append({
                    'mid': song.get('mid', '') or song.get('songmid', ''),
                    'name': song.get('name', '') or song.get('songname', ''),
                    'title': song.get('name', '') or song.get('songname', ''),
                    'singer': singer_name,
                    'singer_mid': singer_mid,
                    'album': album_name,
                    'album_mid': album_mid,
                    'interval': song.get('interval', 0),
                })

            logger.debug(f"QQ Music search via remote API: {len(formatted)} results")
            return formatted
        except Exception as e:
            logger.error(f"QQ Music remote search error: {e}")
            return []

    def get_lyrics(self, mid: str) -> Optional[str]:
        """
        Get lyrics for a song by mid.

        Hybrid approach with fallback.

        Args:
            mid: QQ Music song mid

        Returns:
            Lyrics content (QRC or LRC format) or None
        """
        # Try local API first
        if self._should_use_local():
            try:
                result = self._local_client.get_lyric(mid, qrc=True, trans=False)

                if result:
                    lyric = result.get('lyric') or result.get('qrc')
                    if lyric:
                        logger.debug(f"Got lyrics via local API: {len(lyric)} chars")
                        return lyric

            except Exception as e:
                logger.debug(f"Local lyrics fetch failed: {e}, falling back to remote")

        # Fallback to remote API
        return self._get_lyrics_remote(mid)

    def _get_lyrics_remote(self, mid: str) -> Optional[str]:
        """Get lyrics using remote API."""
        url = f"{self.REMOTE_BASE_URL}/lyric"

        params = {
            "mid": mid,
            "qrc": 1
        }

        try:
            session = requests.Session()
            r = session.get(url, params=params, headers=self.HEADERS, timeout=self.timeout)
            data = r.json()
            lyric = data.get('data', {}).get('lyric')
            if lyric:
                logger.debug(f"Got lyrics via remote API: {len(lyric)} chars")
            return lyric
        except Exception as e:
            logger.error(f"QQ Music remote lyrics fetch error: {e}")
            return None

    def get_cover_url(self, mid: str = None, album_mid: str = None, size: int = 500) -> Optional[str]:
        """
        Get cover URL for a song or album.

        Uses QQ Music's direct image URL pattern when possible.

        Args:
            mid: QQ Music song MID (will try to get album_mid)
            album_mid: QQ Music album MID (preferred)
            size: Image size (150, 300, 500, 800)

        Returns:
            Cover image URL or None
        """
        if album_mid:
            # Direct QQ Music album cover URL (no API call needed)
            return f"https://y.gtimg.cn/music/photo_new/T002R{size}x{size}M000{album_mid}.jpg"

        # If only song mid provided, try to get album info
        if mid:
            if self._should_use_local():
                try:
                    result = self._local_client.get_song_detail(mid)
                    if result and 'data' in result:
                        album_mid = result['data'].get('album', {}).get('mid', '')
                        if album_mid:
                            return f"https://y.gtimg.cn/music/photo_new/T002R{size}x{size}M000{album_mid}.jpg"
                except Exception as e:
                    logger.debug(f"Failed to get album info: {e}")

            # Fallback to remote API
            try:
                url = f"{self.REMOTE_BASE_URL}/song/cover"
                session = requests.Session()
                r = session.get(url, params={"mid": mid, "size": size},
                              headers=self.HEADERS, timeout=self.timeout,
                              allow_redirects=False)

                if r.status_code == 302:
                    return r.headers.get('Location')
                elif r.status_code == 200:
                    data = r.json()
                    if data.get('code') == 0:
                        return data.get('data', {}).get('url')
            except Exception as e:
                logger.debug(f"Remote cover URL fetch failed: {e}")

        return None

    def search_artist(self, keyword: str, limit: int = 5) -> List[dict]:
        """
        Search for artists on QQ Music.

        Args:
            keyword: Search keyword
            limit: Maximum number of results

        Returns:
            List of artist dicts with keys: mid, name, singer_mid
        """
        # Try local API first
        if self._should_use_local():
            try:
                result = self._local_client.search(keyword, search_type='singer',
                                                  page_num=1, page_size=limit)

                if result and 'body' in result:
                    singers = result['body'].get('singer', {}).get('list', [])

                    formatted = []
                    for singer in singers[:limit]:
                        formatted.append({
                            'singerMID': singer.get('singer_mid', ''),
                            'singerName': singer.get('singer_name', ''),
                            'mid': singer.get('singer_mid', ''),
                            'name': singer.get('singer_name', ''),
                        })

                    if formatted:
                        logger.debug(f"Artist search via local API: {len(formatted)} results")
                        return formatted

            except Exception as e:
                logger.debug(f"Local artist search failed: {e}, falling back to remote")

        # Fallback to remote API
        url = f"{self.REMOTE_BASE_URL}/search"
        params = {
            "keyword": keyword,
            "type": "singer",
            "num": limit,
            "page": 1,
        }

        try:
            session = requests.Session()
            r = session.get(url, params=params, headers=self.HEADERS, timeout=self.timeout)
            data = r.json()
            artists = data.get("data", {}).get("list", [])
            logger.debug(f"Artist search via remote API: {len(artists)} results")
            return artists
        except Exception as e:
            logger.error(f"QQ Music remote artist search error: {e}")
            return []

    def get_artist_cover_url(self, singer_mid: str, size: int = 300) -> Optional[str]:
        """
        Get artist cover URL.

        Uses QQ Music's direct image URL pattern.

        Args:
            singer_mid: QQ Music singer MID
            size: Image size (150, 300, 500)

        Returns:
            Artist cover URL or None
        """
        # QQ Music artist photo URL pattern (direct, no API needed)
        return f"https://y.gtimg.cn/music/photo_new/T001R{size}x{size}M000{singer_mid}.jpg"


def search_from_qqmusic(title: str, artist: str, limit: int = 10) -> List[dict]:
    """
    Search songs from QQ Music.

    Args:
        title: Track title
        artist: Track artist
        limit: Maximum number of results

    Returns:
        List of dicts with keys: 'id', 'title', 'artist', 'album', 'duration', 'source',
                                 'album_mid', 'singer_mid' (for cover fetching)
    """
    client = _get_client()
    keyword = f"{title} {artist}" if artist else title

    songs = client.search(keyword, limit)
    results = []

    for song in songs:
        # Get artist name
        artist_name = song.get('singer', '') or song.get('singer_name', '')

        # Get album info
        album_name = song.get('album', '') or song.get('album_name', '')
        album_mid = song.get('album_mid', '')

        # Get singer mid
        singer_mid = song.get('singer_mid', '')

        # Duration in seconds
        duration = song.get('interval', 0)

        results.append({
            'id': song.get('mid', ''),
            'title': song.get('name', '') or song.get('title', ''),
            'artist': artist_name,
            'album': album_name,
            'duration': duration,
            'source': 'qqmusic',
            'album_mid': album_mid,
            'singer_mid': singer_mid,
            'supports_qrc': True  # QQ Music supports QRC word-by-word lyrics
        })

    return results


def get_qqmusic_cover_url(mid: str = None, album_mid: str = None, size: int = 500) -> Optional[str]:
    """
    Get cover URL from QQ Music.

    Args:
        mid: QQ Music song MID
        album_mid: QQ Music album MID
        size: Image size (150, 300, 500, 800)

    Returns:
        Cover URL or None
    """
    client = _get_client()
    return client.get_cover_url(mid=mid, album_mid=album_mid, size=size)


def get_qqmusic_artist_cover_url(singer_mid: str, size: int = 300) -> Optional[str]:
    """
    Get artist cover URL from QQ Music.

    Args:
        singer_mid: QQ Music singer MID
        size: Image size (150, 300, 500)

    Returns:
        Artist cover URL or None
    """
    client = _get_client()
    return client.get_artist_cover_url(singer_mid, size)


def search_artist_from_qqmusic(artist_name: str, limit: int = 10) -> List[dict]:
    """
    Search artists from QQ Music.

    Args:
        artist_name: Artist name to search
        limit: Maximum number of results

    Returns:
        List of dicts with keys: 'id', 'name', 'singer_mid', 'source', 'album_count'
    """
    client = _get_client()
    artists = client.search_artist(artist_name, limit)
    results = []

    for artist in artists:
        results.append({
            'id': artist.get('mid', '') or artist.get('singerMID', ''),
            'name': artist.get('name', '') or artist.get('singerName', ''),
            'singer_mid': artist.get('mid', '') or artist.get('singerMID', ''),
            'album_count': artist.get('albumNum', 0),
            'source': 'qqmusic',
        })

    return results


def download_qqmusic_lyrics(mid: str) -> str:
    """
    Download lyrics from QQ Music by song mid.

    Args:
        mid: QQ Music song mid

    Returns:
        Lyrics content (QRC or LRC format) or empty string
    """
    client = _get_client()
    lyrics = client.get_lyrics(mid)
    return lyrics if lyrics else ""


if __name__ == "__main__":
    # Test the client
    client = QQMusicClient()

    songs = client.search("稻香 周杰伦", 3)

    print("搜索结果：")
    for s in songs:
        print(f"  {s.get('name')} - {s.get('singer')}")

    if songs:
        mid = songs[0].get("mid")
        lyric = client.get_lyrics(mid)
        if lyric:
            print(f"\n歌词 ({len(lyric)} chars):")
            print(lyric[:500])
