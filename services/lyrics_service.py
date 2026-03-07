"""
Lyrics service for fetching and parsing lyrics.
"""
from pathlib import Path
from typing import Optional, List, Tuple
import requests

from utils import parse_lrc
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
        # First try local .lrc file
        lyrics = cls._get_local_lyrics(track_path)
        if lyrics:
            return lyrics

        # Fall back to online sources (only if enabled)
        if cls.ENABLE_ONLINE:
            return cls._get_online_lyrics(title, artist)

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
                    print(f"Error loading local lyrics: {e}")
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
        # Try multiple online sources
        sources = [
            cls._fetch_from_netease,
            cls._fetch_from_qq_music,
        ]

        for source in sources:
            try:
                lyrics = source(title, artist)
                if lyrics:
                    return lyrics
            except Exception as e:
                print(f"Error fetching lyrics from {source.__name__}: {e}")
                continue

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

            # Get first song's lyrics
            song_id = data['result']['songs'][0]['id']

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
                return lrc_content

        except Exception as e:
            print(f"NetEase lyrics fetch error: {e}")

        return ""

    @classmethod
    def _fetch_from_qq_music(cls, title: str, artist: str) -> str:
        """
        Fetch lyrics from QQ Music.

        Note: QQ Music API is more complex, this is a simplified version.
        """
        # QQ Music requires more complex authentication
        # This is a placeholder for future implementation
        return None

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
        try:
            track_file = Path(track_path)
            lrc_path = track_file.with_suffix('.lrc')

            with open(lrc_path, 'w', encoding='utf-8') as f:
                f.write(lyrics)

            return True

        except Exception as e:
            print(f"Error saving lyrics: {e}")
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
        try:
            track_file = Path(track_path)
            lrc_path = track_file.with_suffix('.lrc')

            if lrc_path.exists():
                lrc_path.unlink()
                return True

            return False

        except Exception as e:
            print(f"Error deleting lyrics: {e}")
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
