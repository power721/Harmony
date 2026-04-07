"""
Lyrics source implementations.
"""

import logging
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
