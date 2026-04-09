"""
Cover art source implementations.
"""

import logging
from typing import Optional, List

from .base import CoverSource, CoverSearchResult

logger = logging.getLogger(__name__)


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
