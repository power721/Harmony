"""
QQ Music lyrics provider.

Provides lyrics from QQ Music via third-party API.
Supports QRC format (word-by-word lyrics).
"""
import logging
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)


class QQMusicClient:
    """QQ Music API client for lyrics search and download."""

    BASE_URL = "https://api.ygking.top/api"

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    def __init__(self, timeout: int = 10):
        self.session = requests.Session()
        self.timeout = timeout

    def search(self, keyword: str, limit: int = 5) -> List[dict]:
        """
        Search for songs on QQ Music.

        Args:
            keyword: Search keyword
            limit: Maximum number of results

        Returns:
            List of song dicts with keys: mid, name, singer, album, duration
        """
        url = f"{self.BASE_URL}/search"

        params = {
            "keyword": keyword,
            "type": "song",
            "num": limit,
            "page": 1,
        }

        try:
            r = self.session.get(url, params=params, headers=self.HEADERS, timeout=self.timeout)
            data = r.json()
            songs = data.get("data", {}).get("list", [])
            return songs
        except Exception as e:
            logger.error(f"QQ Music search error: {e}")
            return []

    def get_lyrics(self, mid: str) -> Optional[str]:
        """
        Get lyrics for a song by mid.

        Args:
            mid: QQ Music song mid

        Returns:
            Lyrics content (QRC or LRC format) or None
        """
        url = f"{self.BASE_URL}/lyric"

        params = {
            "mid": mid,
            "qrc": 1  # Request QRC format (word-by-word lyrics)
        }

        try:
            r = self.session.get(url, params=params, headers=self.HEADERS, timeout=self.timeout)
            data = r.json()
            lyric = data.get('data', {}).get('lyric')
            return lyric
        except Exception as e:
            logger.error(f"QQ Music lyrics fetch error: {e}")
            return None

    def get_cover_url(self, mid: str = None, album_mid: str = None, size: int = 500) -> Optional[str]:
        """
        Get cover URL for a song or album.

        Args:
            mid: QQ Music song MID (will auto-get album info)
            album_mid: QQ Music album MID (directly get cover)
            size: Image size (150, 300, 500, 800)

        Returns:
            Cover image URL or None
        """
        url = f"{self.BASE_URL}/song/cover"

        params = {"size": size}
        if mid:
            params["mid"] = mid
        elif album_mid:
            params["album_mid"] = album_mid
        else:
            return None

        try:
            r = self.session.get(
                url,
                params=params,
                headers=self.HEADERS,
                timeout=self.timeout
            )
            if r.status_code == 200:
                data = r.json()
                if data.get('code') == 0:
                    return data.get('data', {}).get('url')
        except Exception as e:
            logger.error(f"QQ Music cover fetch error: {e}")
            return None

    def get_artist_cover_url(self, singer_mid: str, size: int = 300) -> Optional[str]:
        """
        Get artist cover URL.

        Args:
            singer_mid: QQ Music singer MID
            size: Image size (150, 300, 500)

        Returns:
            Artist cover URL or None
        """
        # QQ Music artist photo URL pattern
        # https://y.gtimg.cn/music/photo_new/T001R{size}x{size}M000{singer_mid}.jpg
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
    client = QQMusicClient()
    keyword = f"{title} {artist}" if artist else title

    songs = client.search(keyword, limit)
    results = []

    for song in songs:
        # Parse artist from singer list
        artist_name = ""
        singer_mid = ""
        if isinstance(song.get('singer'), list) and song['singer']:
            artist_name = song['singer'][0].get('name', '')
            singer_mid = song['singer'][0].get('mid', '')
        elif song.get('singer'):
            artist_name = str(song['singer'])

        # Parse album from album dict
        album_name = ""
        album_mid = ""
        if isinstance(song.get('album'), dict):
            album_name = song['album'].get('name', '')
            album_mid = song['album'].get('mid', '')
        elif song.get('album'):
            album_name = str(song['album'])

        # Duration in seconds
        duration = song.get('interval')

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
    client = QQMusicClient()
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
    client = QQMusicClient()
    return client.get_artist_cover_url(singer_mid, size)


def download_qqmusic_lyrics(mid: str) -> str:
    """
    Download lyrics from QQ Music by song mid.

    Args:
        mid: QQ Music song mid

    Returns:
        Lyrics content (QRC or LRC format) or empty string
    """
    client = QQMusicClient()
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
        mid = songs[0]["mid"]
        lyric = client.get_lyrics(mid)
        if lyric:
            print(f"\n歌词 ({len(lyric)} chars):")
            print(lyric)