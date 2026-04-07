"""
Artist cover (avatar) source implementations.
"""

import base64
import logging
import time
from typing import Optional, List

from .base import ArtistCoverSource, ArtistCoverSearchResult

logger = logging.getLogger(__name__)


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
