"""
Lyrics source implementations.
"""

import base64
import logging
import zlib
from typing import Optional, List

from .base import LyricsSource, LyricsSearchResult

logger = logging.getLogger(__name__)


class NetEaseLyricsSource(LyricsSource):
    """NetEase Cloud Music lyrics source."""

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    @property
    def name(self) -> str:
        return "NetEase"

    def search(
        self,
        title: str,
        artist: str,
        limit: int = 10
    ) -> List[LyricsSearchResult]:
        """Search for lyrics from NetEase Cloud Music."""
        results = []

        search_url = "https://music.163.com/api/search/get/web"
        params = {
            's': f'{artist} {title}',
            'type': '1',
            'limit': str(limit)
        }

        response = self._http_client.get(
            search_url,
            params=params,
            headers=self.HEADERS,
            timeout=3
        )

        if response.status_code != 200:
            return results

        data = response.json()

        if data.get('code') != 200 or not data.get('result', {}).get('songs'):
            return results

        for song in data['result']['songs']:
            # Get album cover URL (300x300 size)
            cover_url = None
            if song.get('album') and song['album'].get('picUrl'):
                cover_url = song['album']['picUrl']
            elif song.get('album') and song['album'].get('pic'):
                pic_str = str(song['album']['pic'])
                cover_url = f"https://p1.music.126.net/{pic_str}/{pic_str}.jpg"

            # Get duration (convert from milliseconds to seconds)
            duration = None
            if song.get('duration'):
                duration = song['duration'] / 1000

            results.append(LyricsSearchResult(
                id=str(song['id']),
                title=song.get('name', ''),
                artist=song['artists'][0]['name'] if song.get('artists') else '',
                album=song['album']['name'] if song.get('album') else '',
                duration=duration,
                source='netease',
                cover_url=cover_url,
                supports_yrc=True  # NetEase supports YRC word-by-word lyrics
            ))

        return results

    def get_lyrics(self, result: LyricsSearchResult) -> Optional[str]:
        """Download lyrics from NetEase by song ID."""
        try:
            # Request both YRC and LRC at the same time
            api_url = f"https://music.163.com/api/song/lyric?id={result.id}&lv=1&kv=0&tv=0&yv=0"
            response = self._http_client.get(
                api_url,
                headers=self.HEADERS,
                timeout=3
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 200:
                    # Check for YRC (word-by-word lyrics) first
                    yrc_data = data.get('yrc')
                    if yrc_data and yrc_data.get('lyric'):
                        return yrc_data['lyric']

                    # Fall back to LRC if no YRC
                    lrc_data = data.get('lrc')
                    if lrc_data and lrc_data.get('lyric'):
                        return lrc_data['lyric']

            # Fallback to original API
            lyrics_url = f"https://music.163.com/api/song/lyric?id={result.id}&lv=1&kv=1&tv=-1"
            response = self._http_client.get(
                lyrics_url,
                headers=self.HEADERS,
                timeout=3
            )

            if response.status_code != 200:
                return None

            data = response.json()
            if data.get('code') != 200:
                return None

            if 'lrc' in data:
                return data['lrc'].get('lyric', '')
            elif 'lyric' in data:
                return data['lyric']

        except Exception as e:
            logger.error(f"Error downloading NetEase lyrics: {e}")

        return None

    def __init__(self, http_client):
        self._http_client = http_client


class QQMusicLyricsSource(LyricsSource):
    """QQ Music lyrics source."""

    @property
    def name(self) -> str:
        return "QQMusic"

    def search(
        self,
        title: str,
        artist: str,
        limit: int = 10
    ) -> List[LyricsSearchResult]:
        """Search for lyrics from QQ Music."""
        results = []

        try:
            from services.lyrics.qqmusic_lyrics import search_from_qqmusic
            search_results = search_from_qqmusic(title, artist, limit)

            for item in search_results:
                results.append(LyricsSearchResult(
                    id=item.get('id', ''),
                    title=item.get('title', ''),
                    artist=item.get('artist', ''),
                    album=item.get('album', ''),
                    duration=item.get('duration'),
                    source='qqmusic',
                    cover_url=item.get('cover_url'),
                ))

        except Exception as e:
            logger.error(f"Error searching from QQ Music: {e}")

        return results

    def get_lyrics(self, result: LyricsSearchResult) -> Optional[str]:
        """Download lyrics from QQ Music by song mid."""
        try:
            from services.lyrics.qqmusic_lyrics import download_qqmusic_lyrics
            return download_qqmusic_lyrics(result.id)
        except Exception as e:
            logger.error(f"Error downloading QQ Music lyrics: {e}")

        return None

    def __init__(self, http_client=None):
        pass


class KugouLyricsSource(LyricsSource):
    """Kugou lyrics source."""

    @property
    def name(self) -> str:
        return "Kugou"

    def search(
        self,
        title: str,
        artist: str,
        limit: int = 10
    ) -> List[LyricsSearchResult]:
        """Search for lyrics from Kugou."""
        results = []

        keyword = f"{title} {artist}"
        search_url = "https://lyrics.kugou.com/search"
        headers = {"User-Agent": "Mozilla/5.0"}

        params = {
            "keyword": keyword,
            "page": 1,
            "pagesize": limit
        }

        try:
            r = self._http_client.get(search_url, params=params, headers=headers, timeout=3)
            data = r.json()

            candidates = data.get("candidates", [])
            for item in candidates:
                results.append(LyricsSearchResult(
                    id=str(item['id']),
                    title=item.get('name', item.get('song', '')),
                    artist=item.get('singer', ''),
                    album='',
                    source='kugou',
                    accesskey=item.get('accesskey', '')
                ))

        except Exception as e:
            logger.debug(f"Kugou search error: {e}")

        return results

    def get_lyrics(self, result: LyricsSearchResult) -> Optional[str]:
        """Download lyrics from Kugou by song ID."""
        try:
            download_url = "https://lyrics.kugou.com/download"
            headers = {"User-Agent": "Mozilla/5.0"}

            params = {
                "id": result.id,
                "accesskey": result.accesskey,
                "fmt": "krc",
                "charset": "utf8"
            }

            r = self._http_client.get(download_url, params=params, headers=headers, timeout=5)
            data = r.json()

            content = data.get("content")
            if not content:
                return None

            # base64 decode
            krc = base64.b64decode(content)

            # Remove KRC header
            if krc[:4] == b'krc1':
                krc = krc[4:]

            # zlib decompress
            lyric = zlib.decompress(krc)
            return lyric.decode("utf-8", errors="ignore")

        except Exception as e:
            logger.error(f"Error downloading Kugou lyrics: {e}")

        return None

    def __init__(self, http_client):
        self._http_client = http_client


class LRCLIBLyricsSource(LyricsSource):
    """LRCLIB (free, open source lyrics API) source."""

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    @property
    def name(self) -> str:
        return "LRCLIB"

    def search(
        self,
        title: str,
        artist: str,
        limit: int = 10
    ) -> List[LyricsSearchResult]:
        """Search for lyrics from LRCLIB."""
        results = []

        search_url = "https://lrclib.net/api/search"
        params = {
            'track_name': title,
            'artist_name': artist
        }

        try:
            response = self._http_client.get(
                search_url,
                params=params,
                headers=self.HEADERS,
                timeout=3
            )

            if response.status_code != 200:
                return results

            data = response.json()

            if not isinstance(data, list):
                return results

            for song in data[:limit]:
                # Include songs with synced lyrics or plain lyrics
                synced = song.get('syncedLyrics')
                plain = song.get('plainLyrics')
                if synced or plain:
                    # Store lyrics directly in the result for later use
                    lyrics = synced if synced else plain
                    results.append(LyricsSearchResult(
                        id=str(song.get('id', '')),
                        title=song.get('trackName', ''),
                        artist=song.get('artistName', ''),
                        album=song.get('albumName', ''),
                        duration=song.get('duration'),
                        source='lrclib',
                        lyrics=lyrics  # Pre-fetch lyrics from search result
                    ))

        except Exception as e:
            logger.debug(f"LRCLIB search error: {e}")

        return results

    def get_lyrics(self, result: LyricsSearchResult) -> Optional[str]:
        """Get lyrics from LRCLIB (may already be in result)."""
        # Lyrics may already be pre-fetched in the search result
        if result.lyrics:
            return result.lyrics

        # Otherwise, search again to get lyrics
        try:
            search_url = "https://lrclib.net/api/search"
            params = {
                'q': result.id  # Search by ID as query
            }

            response = self._http_client.get(
                search_url,
                params=params,
                headers=self.HEADERS,
                timeout=3
            )

            if response.status_code != 200:
                return None

            data = response.json()

            if not isinstance(data, list) or not data:
                return None

            # Find the matching song by ID
            for song in data:
                if str(song.get('id')) == str(result.id):
                    # Prioritize synced lyrics
                    synced_lyrics = song.get('syncedLyrics')
                    if synced_lyrics:
                        return synced_lyrics

                    # Fall back to plain lyrics
                    plain_lyrics = song.get('plainLyrics')
                    if plain_lyrics:
                        return plain_lyrics

        except Exception as e:
            logger.error(f"Error downloading LRCLIB lyrics: {e}")

        return None

    def __init__(self, http_client):
        self._http_client = http_client
