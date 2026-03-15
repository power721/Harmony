"""
Lyrics service for fetching and parsing lyrics.
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configure logging
logger = logging.getLogger(__name__)
from pathlib import Path
from typing import Optional, List
import requests
import base64
import zlib

from utils.lrc_parser import LyricLine
from utils.match_scorer import MatchScorer, TrackInfo

# Initialize OpenCC converter for Traditional to Simplified Chinese conversion
try:
    from opencc import OpenCC

    _t2s_converter = OpenCC('t2s')  # Traditional to Simplified
    _HAS_OPENCC = True
except ImportError:
    _HAS_OPENCC = False
    _t2s_converter = None
    logger.warning("OpenCC not installed. Traditional Chinese lyrics will not be converted to Simplified.")


class LyricsService:
    """Service for fetching lyrics from local files and online sources."""

    # User agent for web requests
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    # Enable online lyrics (default: False to prevent UI blocking)
    ENABLE_ONLINE = True  # Changed to True for better UX

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
    def search_songs(cls, title: str, artist: str, limit: int = 10) -> List[dict]:
        """
        Search for songs online and return a list of candidates.
        Uses parallel searching for better performance.

        Args:
            title: Track title
            artist: Track artist
            limit: Maximum number of results per source (total results will be larger)

        Returns:
            List of dicts with keys: 'id', 'title', 'artist', 'album', 'source'
        """
        results = []

        # Define search tasks for parallel execution
        search_tasks = [
            ("LRCLIB", lambda: cls._search_from_lrclib(title, artist, limit)),
            ("NetEase", lambda: cls._search_from_netease(title, artist, limit)),
            ("Kugou", lambda: cls._search_from_kugou(title, artist, limit)),
        ]

        # Parallel search from multiple sources
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(task[1]): task[0]
                for task in search_tasks
            }

            for future in as_completed(futures, timeout=10):
                source_name = futures[future]
                try:
                    source_results = future.result()
                    results.extend(source_results)
                    logger.debug(f"[LyricsService] {source_name}: found {len(source_results)} results")
                except Exception as e:
                    logger.error(f"Error searching from {source_name}: {e}", exc_info=True)

        # Return all results (user can see all sources)
        return results

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
                duration = song['duration'] / 1000  # Convert ms to seconds

            results.append({
                'id': str(song['id']),
                'title': song.get('name', ''),
                'artist': song['artists'][0]['name'] if song.get('artists') else '',
                'album': song['album']['name'] if song.get('album') else '',
                'duration': duration,  # Duration in seconds
                'cover_url': cover_url,
                'source': 'netease'
            })

        return results

    @classmethod
    def _search_from_lrclib(cls, title: str, artist: str, limit: int = 10) -> List[dict]:
        """Search songs from LRCLIB (free, open source lyrics API)."""
        results = []

        search_url = "https://lrclib.net/api/search"
        params = {
            'track_name': title,
            'artist_name': artist
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

        if not isinstance(data, list):
            return results

        for song in data[:limit]:
            # Include songs with synced lyrics or plain lyrics
            synced = song.get('syncedLyrics')
            plain = song.get('plainLyrics')
            if synced or plain:
                # Store lyrics directly in the result for later use
                lyrics = synced if synced else plain
                # Convert to Simplified Chinese
                lyrics = cls._convert_to_simplified_chinese(lyrics)
                results.append({
                    'id': str(song.get('id', '')),
                    'title': song.get('trackName', ''),
                    'artist': song.get('artistName', ''),
                    'album': song.get('albumName', ''),
                    'duration': song.get('duration'),  # Song duration in seconds
                    'source': 'lrclib',
                    'lyrics': lyrics  # Pre-fetch lyrics from search result
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
            source: Source name ('lrclib', 'netease' or 'kugou')
            accesskey: Access key for Kugou

        Returns:
            Lyrics content or empty string
        """
        if source == 'lrclib':
            return cls._download_lrclib_lyrics(song_id)
        elif source == 'netease':
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
    def get_song_cover_url(cls, song_id: str, source: str) -> Optional[str]:
        """
        Get cover URL for a song from online sources.

        Args:
            song_id: Song ID
            source: Source name ('netease', 'lrclib', or 'kugou')

        Returns:
            Cover URL or None
        """
        if source == 'netease':
            return cls._get_netease_song_cover(song_id)
        # LRCLIB and Kugou don't provide cover art
        return None

    @classmethod
    def _get_netease_song_cover(cls, song_id: str) -> Optional[str]:
        """Get cover URL from NetEase by song ID."""
        try:
            # Use song detail API to get cover URL
            detail_url = f"https://music.163.com/api/song/detail?ids=[{song_id}]"
            response = requests.get(
                detail_url,
                headers=cls.HEADERS,
                timeout=5
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

            return None

        except Exception as e:
            logger.error(f"Error getting NetEase song cover: {e}", exc_info=True)
            return None

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
    def _download_lrclib_lyrics(cls, song_id: str) -> str:
        """Download lyrics from LRCLIB by song ID.

        Note: LRCLIB doesn't have a dedicated /api/lyrics/{id} endpoint.
        We need to search and extract from results.
        """
        try:
            # LRCLIB API doesn't have a get-by-id endpoint, so we search by ID
            # Using the query parameter format
            search_url = "https://lrclib.net/api/search"
            params = {
                'q': song_id  # Search by ID as query
            }

            response = requests.get(
                search_url,
                params=params,
                headers=cls.HEADERS,
                timeout=5
            )

            if response.status_code != 200:
                return ""

            data = response.json()

            if not isinstance(data, list) or not data:
                return ""

            # Find the matching song by ID
            for song in data:
                if str(song.get('id')) == str(song_id):
                    # Prioritize synced lyrics
                    synced_lyrics = song.get('syncedLyrics')
                    if synced_lyrics:
                        return cls._convert_to_simplified_chinese(synced_lyrics)

                    # Fall back to plain lyrics
                    plain_lyrics = song.get('plainLyrics')
                    if plain_lyrics:
                        return cls._convert_to_simplified_chinese(plain_lyrics)

                    return ""

            return ""

        except Exception as e:
            logger.error(f"Error downloading LRCLIB lyrics: {e}", exc_info=True)
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
            lyrics = cls._get_online_lyrics(title, artist, album, duration)
            if lyrics:
                cls.save_lyrics(track_path, lyrics)
                return lyrics

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

        # Define search tasks for parallel execution
        search_tasks = [
            ("LRCLIB", lambda: cls._search_from_lrclib(title, artist, limit=5)),
            ("NetEase", lambda: cls._search_from_netease(title, artist, limit=5)),
            ("Kugou", lambda: cls._search_from_kugou(title, artist, limit=5)),
        ]

        # Parallel search from multiple sources
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(task[1]): task[0]
                for task in search_tasks
            }

            for future in as_completed(futures, timeout=10):
                source_name = futures[future]
                try:
                    source_results = future.result()
                    all_results.extend(source_results)
                except Exception as e:
                    logger.error(f"Error searching from {source_name}: {e}", exc_info=True)

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

            # Get lyrics from result
            if result.lyrics:
                # Already have lyrics (LRCLIB)
                return result.lyrics

            # Download lyrics by ID
            return cls.download_lyrics_by_id(
                result.id,
                result.source,
                result.accesskey
            )

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
    def _fetch_from_lrclib(cls, title: str, artist: str) -> str:
        """
        Fetch lyrics from LRCLIB (free, open source lyrics API).

        Args:
            title: Track title
            artist: Track artist

        Returns:
            Synced lyrics content or empty string
        """
        try:
            print(f'search lyric from lrclib: {artist} {title}')
            search_url = "https://lrclib.net/api/search"
            params = {
                'track_name': title,
                'artist_name': artist
            }

            response = requests.get(
                search_url,
                params=params,
                headers=cls.HEADERS,
                timeout=3
            )

            if response.status_code != 200:
                return ""

            data = response.json()

            if not isinstance(data, list) or not data:
                return ""

            # Get first result with synced lyrics
            for song in data:
                synced_lyrics = song.get('syncedLyrics')
                if synced_lyrics:
                    print('get lyrics from lrclib')
                    # Convert to Simplified Chinese
                    return cls._convert_to_simplified_chinese(synced_lyrics)

            # If no synced lyrics, try plain lyrics
            for song in data:
                plain_lyrics = song.get('plainLyrics')
                if plain_lyrics:
                    print('get plain lyrics from lrclib')
                    # Convert to Simplified Chinese
                    return cls._convert_to_simplified_chinese(plain_lyrics)

        except Exception as e:
            print(f"LRCLIB lyrics fetch error: {e}")

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
