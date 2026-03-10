"""
Lyrics service for fetching and parsing lyrics.
"""
import re
import logging

from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(levelname)s] %(name)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
from pathlib import Path
from typing import Optional, List, Tuple
import requests
import base64
import zlib
import xml.etree.ElementTree as ET

from utils.lrc_parser import LyricLine


class LyricsService:
    """Service for fetching lyrics from local files and online sources."""

    # User agent for web requests
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    # Enable online lyrics (default: False to prevent UI blocking)
    ENABLE_ONLINE = True  # Changed to True for better UX

    @classmethod
    def search_songs(cls, title: str, artist: str, limit: int = 10) -> List[dict]:
        """
        Search for songs online and return a list of candidates.

        Args:
            title: Track title
            artist: Track artist
            limit: Maximum number of results

        Returns:
            List of dicts with keys: 'id', 'title', 'artist', 'album', 'source'
        """
        results = []

        # Try NetEase Cloud Music first
        try:
            netease_results = cls._search_from_netease(title, artist, limit)
            results.extend(netease_results)
        except Exception as e:
            logger.error(f"Error searching from NetEase: {e}", exc_info=True)

        # Try Kugou if not enough results
        if len(results) < limit:
            try:
                kugou_results = cls._search_from_kugou(title, artist, limit - len(results))
                results.extend(kugou_results)
            except Exception as e:
                logger.error(f"Error searching from Kugou: {e}", exc_info=True)

        return results[:limit]

    @classmethod
    def _search_from_netease(cls, title: str, artist: str, limit: int = 10) -> List[dict]:
        """Search songs from NetEase Cloud Music."""
        results = []

        search_url = "https://music.163.com/api/search/get/web"
        params = {
            's': f'{artist} {title}',
            'type': '1',
            'limit': str(limit)
        }

        response = requests.get(
            search_url,
            params=params,
            headers=cls.HEADERS,
            timeout=5
        )

        if response.status_code != 200:
            return results

        data = response.json()

        if data.get('code') != 200 or not data.get('result', {}).get('songs'):
            return results

        for song in data['result']['songs']:
            results.append({
                'id': str(song['id']),
                'title': song.get('name', ''),
                'artist': song['artists'][0]['name'] if song.get('artists') else '',
                'album': song['album']['name'] if song.get('album') else '',
                'source': 'netease'
            })

        return results

    @classmethod
    def _search_from_kugou(cls, title: str, artist: str, limit: int = 10) -> List[dict]:
        """Search songs from Kugou."""
        results = []

        keyword = f"{title} {artist}"
        search_url = "https://lyrics.kugou.com/search"
        headers = {"User-Agent": "Mozilla/5.0"}

        params = {
            "keyword": keyword,
            "page": 1,
            "pagesize": limit
        }

        r = requests.get(search_url, params=params, headers=headers, timeout=5)
        data = r.json()

        candidates = data.get("candidates", [])
        for item in candidates:
            results.append({
                'id': str(item['id']),
                'title': item.get('name', item.get('song', '')),
                'artist': item.get('singer', ''),
                'album': '',
                'source': 'kugou',
                'accesskey': item.get('accesskey', '')
            })

        return results

    @classmethod
    def download_lyrics_by_id(cls, song_id: str, source: str, accesskey: str = None) -> str:
        """
        Download lyrics by song ID from a specific source.

        Args:
            song_id: Song ID
            source: Source name ('netease' or 'kugou')
            accesskey: Access key for Kugou

        Returns:
            Lyrics content or empty string
        """
        if source == 'netease':
            return cls._download_netease_lyrics(song_id)
        elif source == 'kugou':
            return cls._download_kugou_lyrics(song_id, accesskey)
        return ""

    @classmethod
    def _download_netease_lyrics(cls, song_id: str) -> str:
        """Download lyrics from NetEase by song ID."""
        try:
            lyrics_url = f"https://music.163.com/api/song/lyric?id={song_id}&lv=1&kv=1&tv=-1"
            response = requests.get(
                lyrics_url,
                headers=cls.HEADERS,
                timeout=5
            )

            if response.status_code != 200:
                return ""

            data = response.json()
            if data.get('code') != 200:
                return ""

            lrc_content = ""
            if 'lrc' in data:
                lrc_content = data['lrc'].get('lyric', '')
            elif 'lyric' in data:
                lrc_content = data['lyric']

            return lrc_content

        except Exception as e:
            logger.error(f"Error downloading NetEase lyrics: {e}", exc_info=True)
            return ""

    @classmethod
    def _download_kugou_lyrics(cls, song_id: str, accesskey: str) -> str:
        """Download lyrics from Kugou by song ID."""
        try:
            download_url = "https://lyrics.kugou.com/download"
            headers = {"User-Agent": "Mozilla/5.0"}

            params = {
                "id": song_id,
                "accesskey": accesskey,
                "fmt": "krc",
                "charset": "utf8"
            }

            r = requests.get(download_url, params=params, headers=headers, timeout=10)
            data = r.json()

            content = data.get("content")
            if not content:
                return ""

            # base64 decode
            krc = base64.b64decode(content)

            # Remove KRC header
            if krc[:4] == b'krc1':
                krc = krc[4:]

            # zlib decompress
            lyric = zlib.decompress(krc)
            return lyric.decode("utf-8", errors="ignore")

        except Exception as e:
            logger.error(f"Error downloading Kugou lyrics: {e}", exc_info=True)
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
    def get_lyrics(cls, track_path: str, title: str, artist: str) -> str:
        """
        Get lyrics for a track, prioritizing local .lrc files.

        Args:
            track_path: Path to the audio file
            title: Track title
            artist: Track artist

        Returns:
            List of (time, text) tuples for synchronized lyrics, or None
        """
        import time
        start_time = time.time()

        logger.debug(f"[LyricsService] get_lyrics called: path={track_path}, title={title}, artist={artist}")

        # First try local .lrc file
        if track_path:
            local_start = time.time()
            lyrics = cls._get_local_lyrics(track_path)
            logger.debug(f"[LyricsService] _get_local_lyrics took: {time.time() - local_start:.3f}s")
            if lyrics:
                logger.debug(f"[LyricsService] Found local lyrics, total time: {time.time() - start_time:.3f}s")
                return lyrics

        # Fall back to online sources (only if enabled)
        if cls.ENABLE_ONLINE:
            logger.debug(f"[LyricsService] No local lyrics, trying online sources...")
            online_start = time.time()
            lyrics = cls._get_online_lyrics(title, artist)
            logger.debug(f"[LyricsService] _get_online_lyrics took: {time.time() - online_start:.3f}s")
            if lyrics:
                cls.save_lyrics(track_path, lyrics)
            logger.debug(f"[LyricsService] get_lyrics total time: {time.time() - start_time:.3f}s")
            return lyrics

        logger.debug(f"[LyricsService] get_lyrics total time: {time.time() - start_time:.3f}s (no online)")
        return ""

    @classmethod
    def _get_local_lyrics(cls, track_path: str) -> str:
        """
        Load lyrics from a local .lrc file.

        Args:
            track_path: Path to the audio file

        Returns:
            List of (time, text) tuples, or None
        """
        track_file = Path(track_path)
        lrc_path = track_file.with_suffix('.lrc')

        if lrc_path.exists():
            # Try multiple encodings to support different file sources
            encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'big5', 'utf-16']

            for encoding in encodings:
                try:
                    with open(lrc_path, 'r', encoding=encoding) as f:
                        content = f.read()
                    return content
                except (UnicodeDecodeError, UnicodeError):
                    continue
                except Exception as e:
                    logger.error(f"Error loading local lyrics from {lrc_path}: {e}", exc_info=True)
                    break

        return ""

    @classmethod
    def _get_online_lyrics(cls, title: str, artist: str) -> str:
        """
        Fetch lyrics from online sources.

        Args:
            title: Track title
            artist: Track artist

        Returns:
            List of (time, text) tuples, or None if not found
        """
        import time
        start_time = time.time()

        logger.debug(f"[LyricsService] _get_online_lyrics called: title={title}, artist={artist}")

        # Try multiple online sources
        sources = [
            cls._fetch_from_netease,
            cls._fetch_from_kugou_music,
        ]

        for source in sources:
            try:
                source_start = time.time()
                logger.debug(f"[LyricsService] Trying source: {source.__name__}")
                lyrics = source(title, artist)
                logger.debug(f"[LyricsService] {source.__name__} took: {time.time() - source_start:.3f}s")
                if lyrics:
                    logger.debug(f"[LyricsService] Found lyrics from {source.__name__}, total time: {time.time() - start_time:.3f}s")
                    return lyrics
            except Exception as e:
                logger.error(f"Error fetching lyrics from {source.__name__}: {e}", exc_info=True)
                continue

        logger.debug(f"[LyricsService] _get_online_lyrics total time: {time.time() - start_time:.3f}s (not found)")
        return ""

    @classmethod
    def _fetch_from_netease(cls, title: str, artist: str) -> str:
        """
        Fetch lyrics from NetEase Cloud Music.

        This searches for the song and tries to get lyrics.
        """
        try:
            # Search for the song
            search_url = "https://music.163.com/api/search/get/web"
            params = {
                's': f'{artist} {title}',
                'type': '1',
                'limit': '5'
            }
            print(f'search lyric from 163: {artist} {title}')

            response = requests.get(
                search_url,
                params=params,
                headers=cls.HEADERS,
                timeout=3  # Reduced to 3 seconds
            )

            if response.status_code != 200:
                return ""

            data = response.json()

            if data.get('code') != 200 or not data.get('result', {}).get('songs'):
                return ""

            song_id = data['result']['songs'][0]['id']
            for item in data['result']['songs']:
                if item['artists'][0]['name'] == artist:
                    song_id = item['id']
                    break

            lyrics_url = f"https://music.163.com/api/song/lyric?id={song_id}&lv=1&kv=1&tv=-1"
            lyrics_response = requests.get(
                lyrics_url,
                headers=cls.HEADERS,
                timeout=3  # Reduced to 3 seconds
            )

            if lyrics_response.status_code != 200:
                return ""

            lyrics_data = lyrics_response.json()

            if lyrics_data.get('code') != 200:
                return ""

            # Extract LRC content
            lrc_content = ""
            if 'lrc' in lyrics_data:
                lrc_content = lyrics_data['lrc'].get('lyric')
            elif 'lyric' in lyrics_data:
                lrc_content = lyrics_data['lyric']

            if lrc_content:
                print('get lyrics from 163')
                return lrc_content

        except Exception as e:
            print(f"NetEase lyrics fetch error: {e}")

        return ""

    @classmethod
    def _fetch_from_kugou_music(cls, title: str, artist: str) -> str:
        try:
            keyword = f"{title} {artist}"
            print(f'search lyric from kugou: {keyword}')

            search_url = "https://lyrics.kugou.com/search"
            download_url = "https://lyrics.kugou.com/download"

            headers = {
                "User-Agent": "Mozilla/5.0"
            }

            # 1 搜索歌词
            params = {
                "keyword": keyword,
                "page": 1,
                "pagesize": 10
            }

            r = requests.get(search_url, params=params, headers=headers, timeout=10)
            data = r.json()

            candidates = data.get("candidates", [])
            if not candidates:
                return ""

            # 2 选第一条
            item = candidates[0]

            lyric_id = item["id"]
            accesskey = item["accesskey"]

            # 3 下载歌词
            params = {
                "id": lyric_id,
                "accesskey": accesskey,
                "fmt": "krc",
                "charset": "utf8"
            }

            r = requests.get(download_url, params=params, headers=headers, timeout=10)
            data = r.json()

            content = data.get("content")
            if not content:
                return ""

            # 4 base64解码
            krc = base64.b64decode(content)

            # 5 去掉 KRC 头
            if krc[:4] == b'krc1':
                krc = krc[4:]

            # 6 zlib 解压
            lyric = zlib.decompress(krc)

            print('get lyrics from kugou')
            return lyric.decode("utf-8", errors="ignore")

        except Exception:
            return ""

    @classmethod
    def search_lyrics(cls, query: str) -> List[str]:
        """
        Search for lyrics online (returns plain text, not synchronized).

        Args:
            query: Search query

        Returns:
            List of potential matches
        """
        # This would return search results for the user to choose from
        # Implementation depends on the lyrics provider API
        return []

    @classmethod
    def save_lyrics(cls, track_path: str, lyrics: str) -> bool:
        """
        Save lyrics to a local .lrc file.

        Args:
            track_path: Path to the audio file
            lyrics: List of (time, text) tuples

        Returns:
            True if saved successfully
        """
        # Skip saving if track_path is empty or invalid
        if not track_path or track_path in ('.', '', '/'):
            logger.debug(f"Skipping lyrics save for invalid track path: {track_path}")
            return False

        try:
            track_file = Path(track_path)
            lrc_path = track_file.with_suffix('.lrc')

            with open(lrc_path, 'w', encoding='utf-8') as f:
                f.write(lyrics)

            return True

        except Exception as e:
            logger.error(f"Error saving lyrics to {track_path}: {e}", exc_info=True)
            return False

    @classmethod
    def delete_lyrics(cls, track_path: str) -> bool:
        """
        Delete lyrics file for a track.

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
            lrc_path = track_file.with_suffix('.lrc')

            if lrc_path.exists():
                lrc_path.unlink()
                return True

            return False

        except Exception as e:
            logger.error(f"Error deleting lyrics file for {track_path}: {e}", exc_info=True)
            return False

    @classmethod
    def lyrics_file_exists(cls, track_path: str) -> bool:
        """
        Check if a lyrics file exists for a track.

        Args:
            track_path: Path to the audio file

        Returns:
            True if lyrics file exists
        """
        track_file = Path(track_path)
        lrc_path = track_file.with_suffix('.lrc')

        if lrc_path.exists():
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
