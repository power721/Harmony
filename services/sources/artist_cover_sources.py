"""
Artist cover (avatar) source implementations.
"""

import base64
import logging
import os
import time
from typing import Optional, List

from .base import ArtistCoverSource, ArtistCoverSearchResult

logger = logging.getLogger(__name__)


class NetEaseArtistCoverSource(ArtistCoverSource):
    """NetEase Cloud Music artist cover source."""

    @property
    def name(self) -> str:
        return "NetEase"

    def search(
        self,
        artist_name: str,
        limit: int = 10
    ) -> List[ArtistCoverSearchResult]:
        """Search for artist covers from NetEase Cloud Music."""
        results = []

        try:
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

            response = self._http_client.get(
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

                            results.append(ArtistCoverSearchResult(
                                id=str(artist_info.get('id', '')),
                                name=artist_info.get('name', ''),
                                cover_url=pic_url,
                                album_count=artist_info.get('albumSize', 0),
                                source='netease'
                            ))

        except Exception as e:
            logger.debug(f"NetEase artist cover search error: {e}")

        return results

    def __init__(self, http_client):
        self._http_client = http_client


class QQMusicArtistCoverSource(ArtistCoverSource):
    """QQ Music artist cover source."""

    @property
    def name(self) -> str:
        return "QQMusic"

    def _parse_cover_url(self, url: str):
        """Parse QQ Music cover URL."""
        import re
        pattern = r"(T\d{3})R\d+x\d+M000([A-Za-z0-9]+)"
        m = re.search(pattern, url)
        if not m:
            return "", ""
        return m.group(1), m.group(2)

    def _convert_cover_url(self, url: str, size: int = 500) -> str:
        """Convert to specified size."""
        import re
        img_type, mid = self._parse_cover_url(url)
        if not img_type or not mid:
            return url
        return f"https://y.gtimg.cn/music/photo_new/{img_type}R{size}x{size}M000{mid}.jpg"

    def search(
        self,
        artist_name: str,
        limit: int = 10
    ) -> List[ArtistCoverSearchResult]:
        """Search for artist covers from QQ Music."""
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
                    # Convert cover URL if valid
                    if cover_url:
                        cover_url = self._convert_cover_url(cover_url)
                    else:
                        cover_url = None  # Will be lazy loaded via singer_mid

                    results.append(ArtistCoverSearchResult(
                        id=singer_mid,
                        name=name,
                        cover_url=cover_url,
                        album_count=album_count,
                        source='qqmusic',
                        singer_mid=singer_mid
                    ))

        except Exception as e:
            logger.debug(f"QQ Music artist cover search error: {e}")

        return results

    def __init__(self, http_client=None):
        pass


class ITunesArtistCoverSource(ArtistCoverSource):
    """iTunes Search API artist cover source."""

    @property
    def name(self) -> str:
        return "iTunes"

    def search(
        self,
        artist_name: str,
        limit: int = 10
    ) -> List[ArtistCoverSearchResult]:
        """Search for artist covers from iTunes Search API."""
        results = []

        try:
            search_url = "https://itunes.apple.com/search"
            params = {
                'term': artist_name,
                'media': 'music',
                'entity': 'album',
                'limit': limit
            }

            response = self._http_client.get(search_url, params=params, timeout=5)

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

                            results.append(ArtistCoverSearchResult(
                                id=str(item.get('artistId', '')),
                                name=name,
                                cover_url=artwork_url,
                                album_count=None,
                                source='itunes'
                            ))

        except Exception as e:
            logger.debug(f"iTunes artist cover search error: {e}")

        return results

    def __init__(self, http_client):
        self._http_client = http_client


class SpotifyArtistCoverSource(ArtistCoverSource):
    """Spotify Web API artist cover source."""

    # Spotify API credentials
    SPOTIFY_CLIENT_ID = "83e307eab4cc4e9bab3382b5bc13cc67"
    SPOTIFY_CLIENT_SECRET = "cbb426252fa44f5bb26334b3aa651fa8"
    _token = None
    _token_expires = 0

    @property
    def name(self) -> str:
        return "Spotify"

    def is_available(self) -> bool:
        """Check if Spotify credentials are available."""
        return bool(self._get_token())

    def _get_token(self) -> Optional[str]:
        """Get Spotify access token."""
        if self._token and time.time() < self._token_expires:
            return self._token

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

            response = self._http_client.post(
                "https://accounts.spotify.com/api/token",
                headers=headers,
                data=data,
                timeout=5
            )

            if response.status_code == 200:
                token_data = response.json()
                SpotifyArtistCoverSource._token = token_data["access_token"]
                # Set expiry with 60 seconds buffer
                SpotifyArtistCoverSource._token_expires = time.time() + token_data.get("expires_in", 3600) - 60
                return SpotifyArtistCoverSource._token

        except Exception as e:
            logger.debug(f"Error getting Spotify token: {e}")

        return None

    def search(
        self,
        artist_name: str,
        limit: int = 10
    ) -> List[ArtistCoverSearchResult]:
        """Search for artist covers from Spotify Web API."""
        results = []

        token = self._get_token()
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

            response = self._http_client.get(url, headers=headers, params=params, timeout=5)

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
                                results.append(ArtistCoverSearchResult(
                                    id=artist_info.get("id", ""),
                                    name=name,
                                    cover_url=cover_url,
                                    album_count=artist_info.get("popularity", 0),
                                    source='spotify'
                                ))

        except Exception as e:
            logger.debug(f"Spotify artist search error: {e}")

        return results

    def __init__(self, http_client):
        self._http_client = http_client
