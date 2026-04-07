"""
Cover art source implementations.
"""

import logging
import os
from typing import Optional, List

from .base import CoverSource, CoverSearchResult

logger = logging.getLogger(__name__)


class NetEaseCoverSource(CoverSource):
    """NetEase Cloud Music cover source."""

    @property
    def name(self) -> str:
        return "NetEase"

    def search(
        self,
        title: str,
        artist: str,
        album: str = "",
        duration: Optional[float] = None
    ) -> List[CoverSearchResult]:
        """Search for covers from NetEase Cloud Music."""
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

            response = self._http_client.get(
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

                            results.append(CoverSearchResult(
                                title=album_info.get('name', ''),
                                artist=album_info.get('artist', {}).get('name', ''),
                                album=album_info.get('name', ''),
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

            response = self._http_client.get(
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

                            results.append(CoverSearchResult(
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

    def __init__(self, http_client):
        self._http_client = http_client


class LastFmCoverSource(CoverSource):
    """Last.fm API cover source."""

    @property
    def name(self) -> str:
        return "Last.fm"

    def is_available(self) -> bool:
        """Check if API key is available."""
        api_key = os.getenv("LASTFM_API_KEY")
        return bool(api_key and api_key != "YOUR_LASTFM_API_KEY") or True  # Has default key

    def search(
        self,
        title: str,
        artist: str,
        album: str = "",
        duration: Optional[float] = None
    ) -> List[CoverSearchResult]:
        """Search for covers from Last.fm API."""
        results = []

        api_key = os.getenv("LASTFM_API_KEY")
        if not api_key or api_key == "YOUR_LASTFM_API_KEY":
            api_key = "9b0cdcf446cc96dea3e747787ad23575"

        try:
            url = "http://ws.audioscrobbler.com/2.0/"
            params = {
                'method': 'album.getinfo',
                'api_key': api_key,
                'artist': artist,
                'album': album or title,
                'format': 'json'
            }

            response = self._http_client.get(url, params=params, timeout=5)

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
                        results.append(CoverSearchResult(
                            title=album_info.get('name', ''),
                            artist=album_info.get('artist', ''),
                            album=album_info.get('name', ''),
                            source='lastfm',
                            id=album_info.get('mbid', ''),
                            cover_url=image_url
                        ))

        except Exception as e:
            logger.debug(f"Last.fm search error: {e}")

        return results

    def __init__(self, http_client):
        self._http_client = http_client


class MusicBrainzCoverSource(CoverSource):
    """MusicBrainz Cover Art Archive source."""

    @property
    def name(self) -> str:
        return "MusicBrainz"

    def search(
        self,
        title: str,
        artist: str,
        album: str = "",
        duration: Optional[float] = None
    ) -> List[CoverSearchResult]:
        """Search for covers from MusicBrainz Cover Art Archive."""
        results = []

        try:
            search_url = "https://musicbrainz.org/ws/2/release/"
            params = {
                'query': f'artist:"{artist}" AND release:"{album or title}"',
                'limit': 5,
                'fmt': 'json'
            }

            response = self._http_client.get(
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

                            results.append(CoverSearchResult(
                                title=release.get('title', ''),
                                artist=', '.join([a.get('name', '') for a in release.get('artist-credit', []) if isinstance(a, dict) and 'name' in a]) or artist,
                                album=release.get('title', ''),
                                source='musicbrainz',
                                id=release_id,
                                cover_url=cover_url
                            ))

        except Exception as e:
            logger.debug(f"MusicBrainz search error: {e}")

        return results

    def __init__(self, http_client):
        self._http_client = http_client


class SpotifyCoverSource(CoverSource):
    """Spotify Web API cover source."""

    @property
    def name(self) -> str:
        return "Spotify"

    def is_available(self) -> bool:
        """Check if Spotify credentials are available."""
        return bool(self._get_token())

    def _get_token(self) -> Optional[str]:
        """Get Spotify access token."""
        try:
            import base64
            import os

            client_id = os.getenv("SPOTIFY_CLIENT_ID")
            client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")

            if not client_id or not client_secret:
                return None

            auth_url = "https://accounts.spotify.com/api/token"
            auth_string = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

            response = self._http_client.post(
                auth_url,
                headers={
                    "Authorization": f"Basic {auth_string}",
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                data={"grant_type": "client_credentials"},
                timeout=5
            )

            if response.status_code == 200:
                return response.json().get("access_token")

        except Exception as e:
            logger.debug(f"Spotify token error: {e}")

        return None

    def search(
        self,
        title: str,
        artist: str,
        album: str = "",
        duration: Optional[float] = None
    ) -> List[CoverSearchResult]:
        """Search for album covers from Spotify Web API."""
        results = []

        token = self._get_token()
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

            response = self._http_client.get(url, headers=headers, params=params, timeout=5)

            if response.status_code == 200:
                data = response.json()
                albums = data.get("albums", {}).get("items", [])

                for album_info in albums:
                    images = album_info.get("images", [])
                    if images:
                        # Get the largest image (first in list)
                        cover_url = images[0].get("url")

                        if cover_url:
                            results.append(CoverSearchResult(
                                title=album_info.get("name", ""),
                                artist=(album_info.get("artists") or [{}])[0].get("name", ""),
                                album=album_info.get("name", ""),
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

                response = self._http_client.get(url, headers=headers, params=params_album_only, timeout=5)

                if response.status_code == 200:
                    data = response.json()
                    albums = data.get("albums", {}).get("items", [])

                    for album_info in albums:
                        images = album_info.get("images", [])
                        if images:
                            cover_url = images[0].get("url")

                            if cover_url:
                                results.append(CoverSearchResult(
                                    title=album_info.get("name", ""),
                                    artist=album_info.get("artists", [{}])[0].get("name", ""),
                                    album=album_info.get("name", ""),
                                    source='spotify',
                                    id=album_info.get("id", ""),
                                    cover_url=cover_url
                                ))

        except Exception as e:
            logger.debug(f"Spotify album search error: {e}")

        return results

    def __init__(self, http_client):
        self._http_client = http_client
