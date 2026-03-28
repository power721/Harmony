"""
Online music service.
Provides unified interface for online music search and browsing.
"""

import logging
from typing import Dict, List, Any, Optional, TYPE_CHECKING

import requests

from domain.online_music import (
    OnlineTrack, OnlineArtist, OnlineAlbum, OnlinePlaylist,
    SearchResult, SearchType
)
from .adapter import OnlineMusicAdapter, ApiSource

if TYPE_CHECKING:
    from system.config import ConfigManager

logger = logging.getLogger(__name__)


class OnlineMusicService:
    """
    Service for online music search and browsing.

    Uses api.ygking.top by default, falls back to QQ Music local API
    if credential is available.
    """

    # API endpoints
    YGKING_BASE_URL = "https://api.ygking.top"

    def __init__(self, config_manager: Optional["ConfigManager"] = None,
                 qqmusic_service=None):
        """
        Initialize online music service.

        Args:
            config_manager: ConfigManager for QQ Music credential
            qqmusic_service: Optional QQMusicService instance
        """
        self._config = config_manager
        self._qqmusic = qqmusic_service
        self._http_client = requests.Session()
        self._http_client.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        })

    def _has_qqmusic_credential(self) -> bool:
        """Check if QQ Music credential is available."""
        # Check if qqmusic_service has credential
        if self._qqmusic and self._qqmusic.credential:
            return True

        # Check config if available
        if not self._config:
            return False

        # Use get_qqmusic_credential() method which handles both formats
        credential = self._config.get_qqmusic_credential()
        return credential is not None

    def search(
        self,
        keyword: str,
        search_type: str = SearchType.SONG,
        page: int = 1,
        page_size: int = 50
    ) -> SearchResult:
        """
        Search for music.

        Args:
            keyword: Search keyword
            search_type: Type of search (song/singer/album/playlist)
            page: Page number (1-based)
            page_size: Number of results per page

        Returns:
            SearchResult object
        """
        # Prefer QQ Music local API if credential is available
        if self._has_qqmusic_credential() and self._qqmusic:
            return self._search_qqmusic(keyword, search_type, page, page_size)

        # Use YGKing API
        return self._search_ygking(keyword, search_type, page, page_size)

    def _search_ygking(
        self,
        keyword: str,
        search_type: str,
        page: int,
        page_size: int
    ) -> SearchResult:
        """Search using YGKing API."""
        try:
            url = f"{self.YGKING_BASE_URL}/api/search"
            params = {
                "keyword": keyword,
                "type": search_type,
                "num": page_size,
                "page": page,
            }

            response = self._http_client.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            return OnlineMusicAdapter.normalize_search_result(
                ApiSource.YGKING,
                data,
                search_type,
                keyword,
                page,
                page_size
            )

        except Exception as e:
            logger.error(f"YGKing search failed: {e}")
            return SearchResult(
                keyword=keyword,
                search_type=search_type,
                page=page,
                page_size=page_size
            )

    def _search_qqmusic(
        self,
        keyword: str,
        search_type: str,
        page: int,
        page_size: int
    ) -> SearchResult:
        """Search using QQ Music local API."""
        try:
            result = self._qqmusic.client.search(
                keyword,
                search_type=search_type,
                page_num=page,
                page_size=page_size
            )

            return OnlineMusicAdapter.normalize_search_result(
                ApiSource.QQMUSIC,
                result,
                search_type,
                keyword,
                page,
                page_size
            )

        except Exception as e:
            logger.error(f"QQ Music search failed: {e}, falling back to YGKing")
            return self._search_ygking(keyword, search_type, page, page_size)

    def get_top_lists(self) -> List[Dict[str, Any]]:
        """
        Get music top list / ranking list.

        Returns:
            List of top lists with id and name
        """
        # Prefer QQ Music local API if credential is available
        if self._has_qqmusic_credential() and self._qqmusic:
            return self._get_top_lists_qqmusic()

        return self._get_top_lists_ygking()

    def _get_top_lists_qqmusic(self) -> List[Dict[str, Any]]:
        """Get top lists using QQ Music local API."""
        try:
            result = self._qqmusic.get_top_lists()
            if result:
                logger.debug(f"Got {len(result)} top lists from QQ Music local API")
                return result
            # Empty result, fallback to YGKing
            logger.debug("QQ Music returned empty top lists, falling back to YGKing")
            return self._get_top_lists_ygking()
        except Exception as e:
            logger.error(f"QQ Music get top lists failed: {e}, falling back to YGKing")
            return self._get_top_lists_ygking()

    def _get_top_lists_ygking(self) -> List[Dict[str, Any]]:
        """Get top lists using YGKing API."""
        try:
            url = f"{self.YGKING_BASE_URL}/api/top"
            response = self._http_client.get(url, timeout=20)
            response.raise_for_status()
            data = response.json()

            if data.get("code") == 0:
                # YGKing returns group[].toplist[] structure
                groups = data.get("data", {}).get("group", [])
                top_lists = []
                for group in groups:
                    for top_list in group.get("toplist", []):
                        top_lists.append({
                            'id': top_list.get('topId', ''),
                            'title': top_list.get('title', ''),
                        })
                return top_lists

            return []

        except Exception as e:
            logger.error(f"Get top lists failed: {e}")
            return self._get_default_top_lists()

    def _get_default_top_lists(self) -> List[Dict[str, Any]]:
        """Get default top lists as fallback."""
        return [
            {"id": 4, "title": "巅峰榜·流行指数"},
            {"id": 26, "title": "巅峰榜·热歌"},
            {"id": 27, "title": "巅峰榜·新歌"},
            {"id": 62, "title": "巅峰榜·网络歌曲"},
        ]

    def get_top_list_songs(self, top_id: int, num: int = 100) -> List[OnlineTrack]:
        """
        Get songs from a specific top list.

        Args:
            top_id: Top list ID (e.g., 4 for 流行指数, 26 for 热歌)
            num: Number of songs to return

        Returns:
            List of OnlineTrack objects
        """
        # Prefer QQ Music local API (GetDetail works without login)
        if self._qqmusic:
            return self._get_top_list_songs_qqmusic(top_id, num)

        return self._get_top_list_songs_ygking(top_id, num)

    def _get_top_list_songs_qqmusic(self, top_id: int, num: int) -> List[OnlineTrack]:
        """Get top list songs using QQ Music local API."""
        try:
            songs = self._qqmusic.get_top_list_songs(top_id, num)
            if songs:
                logger.debug(f"Got {len(songs)} songs from QQ Music local API for top_id={top_id}")
                return OnlineMusicAdapter._parse_qqmusic_tracks(songs)
            # Empty result, fallback to YGKing
            logger.debug(f"QQ Music returned empty songs for top_id={top_id}, falling back to YGKing")
            return self._get_top_list_songs_ygking(top_id, num)
        except Exception as e:
            logger.error(f"QQ Music get top list songs failed: {e}, falling back to YGKing")
            return self._get_top_list_songs_ygking(top_id, num)

    def _get_top_list_songs_ygking(self, top_id: int, num: int) -> List[OnlineTrack]:
        """Get top list songs using YGKing API."""
        try:
            url = f"{self.YGKING_BASE_URL}/api/top"
            params = {
                "id": top_id,
                "num": num,
            }

            response = self._http_client.get(url, params=params, timeout=20)
            response.raise_for_status()
            data = response.json()

            if data.get("code") == 0:
                # Prefer songInfoList which has full album and duration info
                songs = data.get("data", {}).get("songInfoList", [])
                if songs:
                    return OnlineMusicAdapter._parse_ygking_song_info_list(songs)
                # Fallback to data.data.song[] structure
                songs = data.get("data", {}).get("data", {}).get("song", [])
                return OnlineMusicAdapter._parse_ygking_top_songs(songs)

            return []

        except Exception as e:
            logger.error(f"Get top list songs failed: {e}")
            return []

    def get_artist_detail(self, singer_mid: str, page: int = 1, page_size: int = 50) -> Optional[Dict[str, Any]]:
        """
        Get artist detail information.

        Args:
            singer_mid: Singer MID
            page: Page number (1-based)
            page_size: Songs per page

        Returns:
            Artist detail dict or None
        """
        # Prefer QQ Music API for detail
        if self._has_qqmusic_credential() and self._qqmusic:
            result = self._qqmusic.get_singer_info(singer_mid, page=page, page_size=page_size)
            if result:
                return result
            logger.debug(f"QQ Music returned no artist detail, falling back to YGKing")

        # Use YGKing API
        return self._get_artist_detail_ygking(singer_mid, page, page_size)

    def _get_artist_detail_ygking(self, singer_mid: str, page: int, page_size: int) -> Optional[Dict[str, Any]]:
        """Get artist detail using YGKing API."""
        try:
            url = f"{self.YGKING_BASE_URL}/api/singer"
            params = {"mid": singer_mid}

            response = self._http_client.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            result = OnlineMusicAdapter.parse_ygking_singer_detail(data)
            if not result:
                return None

            # YGKing singer API doesn't return songs, search by singer name
            singer_name = result.get("name", "")
            if singer_name:
                search_result = self._search_ygking(singer_name, SearchType.SONG, page, page_size)
                result['songs'] = [
                    {
                        'mid': t.mid,
                        'id': t.id,
                        'name': t.title,
                        'title': t.title,
                        'singer': [{'mid': s.mid, 'name': s.name} for s in t.singer],
                        'album': {'mid': t.album.mid, 'name': t.album.name} if t.album else {},
                        'albummid': t.album.mid if t.album else "",
                        'albumname': t.album.name if t.album else "",
                        'interval': t.duration,
                    }
                    for t in search_result.tracks
                ]
                result['total'] = search_result.total

            result['page'] = page
            result['page_size'] = page_size

            return result

        except Exception as e:
            logger.error(f"Get artist detail from YGKing failed: {e}")
            return None

    def get_artist_albums(self, singer_mid: str, number: int = 10, begin: int = 0) -> Dict[str, Any]:
        """
        Get artist's album list.

        Args:
            singer_mid: Singer MID
            number: Number of albums to return
            begin: Pagination start position

        Returns:
            Dict with 'albums' list and 'total' count
        """
        logger.debug(f"get_artist_albums: singer_mid={singer_mid}, number={number}, begin={begin}")
        # Prefer QQ Music API if credential is available
        if self._has_qqmusic_credential() and self._qqmusic:
            result = self._qqmusic.get_singer_albums(singer_mid, number=number, begin=begin)
            if result and result.get('albums'):
                logger.debug(f"get_artist_albums: QQ Music returned {len(result['albums'])} albums, total={result.get('total', 0)}")
                return result
            logger.debug("QQ Music returned no artist albums")

        # Use YGKing API fallback
        logger.debug("get_artist_albums: Using YGKing API fallback")
        return self._get_artist_albums_ygking(singer_mid, number, begin)

    def _get_artist_albums_ygking(self, singer_mid: str, number: int, begin: int) -> Dict[str, Any]:
        """Get artist albums by searching albums with singer name."""
        try:
            # First get singer name from singer_mid
            singer_detail = self._get_artist_detail_ygking(singer_mid)
            if not singer_detail:
                logger.warning(f"Cannot get singer detail for {singer_mid}")
                return {'albums': [], 'total': 0}

            singer_name = singer_detail.get('name', '')
            if not singer_name:
                logger.warning(f"Singer name not found for {singer_mid}")
                return {'albums': [], 'total': 0}

            # Search albums by singer name
            page = (begin // number) + 1 if number > 0 else 1
            search_result = self._search_ygking(singer_name, SearchType.ALBUM, page, number)

            albums = []
            for album in search_result.albums:
                # Filter albums that belong to this singer
                if album.singer_mid == singer_mid or singer_name in album.singer_name:
                    albums.append({
                        "mid": album.mid,
                        "name": album.name,
                        "singer_mid": singer_mid,
                        "singer_name": album.singer_name,
                        "cover_url": album.cover_url,
                        "song_count": album.song_count,
                        "publish_date": album.publish_date,
                    })

            return {'albums': albums, 'total': search_result.total}

        except Exception as e:
            logger.error(f"Get artist albums from YGKing failed: {e}")
            return {'albums': [], 'total': 0}

    def get_album_detail(self, album_mid: str, page: int = 1, page_size: int = 50) -> Optional[Dict[str, Any]]:
        """
        Get album detail information.

        Args:
            album_mid: Album MID
            page: Page number (1-based)
            page_size: Songs per page

        Returns:
            Album detail dict or None
        """
        # Prefer QQ Music API for detail
        if self._has_qqmusic_credential() and self._qqmusic:
            result = self._qqmusic.get_album_info(album_mid, page=page, page_size=page_size)
            if result:
                return result
            logger.debug(f"QQ Music returned no album detail, falling back to YGKing")

        # Use YGKing API
        return self._get_album_detail_ygking(album_mid, page, page_size)

    def _get_album_detail_ygking(self, album_mid: str, page: int, page_size: int) -> Optional[Dict[str, Any]]:
        """Get album detail using YGKing API."""
        try:
            url = f"{self.YGKING_BASE_URL}/api/album"
            params = {"mid": album_mid}

            response = self._http_client.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            result = OnlineMusicAdapter.parse_ygking_album_detail(data)
            if result:
                # If YGKing API doesn't return songs, use search API
                songs = result.get('songs', [])
                if not songs:
                    album_name = result.get('name', '')
                    singer_name = result.get('singer', '')
                    if album_name:
                        # Search by album name + singer name
                        keyword = f"{album_name} {singer_name}".strip()
                        search_result = self._search_ygking(keyword, SearchType.SONG, page, page_size)
                        # Filter songs by album_mid
                        songs = [
                            {
                                'mid': t.mid,
                                'id': t.id,
                                'name': t.title,
                                'title': t.title,
                                'singer': [{'mid': s.mid, 'name': s.name} for s in t.singer],
                                'album': {'mid': t.album.mid, 'name': t.album.name} if t.album else {},
                                'albummid': t.album.mid if t.album else "",
                                'albumname': t.album.name if t.album else "",
                                'interval': t.duration,
                            }
                            for t in search_result.tracks
                            if t.album and t.album.mid == album_mid
                        ]
                        # If no exact match, use all search results
                        if not songs:
                            songs = [
                                {
                                    'mid': t.mid,
                                    'id': t.id,
                                    'name': t.title,
                                    'title': t.title,
                                    'singer': [{'mid': s.mid, 'name': s.name} for s in t.singer],
                                    'album': {'mid': t.album.mid, 'name': t.album.name} if t.album else {},
                                    'albummid': t.album.mid if t.album else "",
                                    'albumname': t.album.name if t.album else "",
                                    'interval': t.duration,
                                }
                                for t in search_result.tracks
                            ]
                        result['total'] = len(songs)

                # Apply pagination
                total = result.get('total', len(songs))
                start_idx = (page - 1) * page_size
                end_idx = start_idx + page_size
                result['songs'] = songs[start_idx:end_idx]
                result['total'] = total
                result['page'] = page
                result['page_size'] = page_size

            return result

        except Exception as e:
            logger.error(f"Get album detail from YGKing failed: {e}")
            return None

    def get_playlist_detail(self, playlist_id: str, page: int = 1, page_size: int = 50) -> Optional[Dict[str, Any]]:
        """
        Get playlist detail information.

        Args:
            playlist_id: Playlist ID
            page: Page number (1-based)
            page_size: Songs per page

        Returns:
            Playlist detail dict or None
        """
        # Prefer QQ Music API for detail
        if self._has_qqmusic_credential() and self._qqmusic:
            result = self._qqmusic.get_playlist_info(playlist_id, page=page, page_size=page_size)
            if result:
                return result
            logger.debug(f"QQ Music returned no playlist detail, falling back to YGKing")

        # Use YGKing API
        return self._get_playlist_detail_ygking(playlist_id, page, page_size)

    def _get_playlist_detail_ygking(self, playlist_id: str, page: int, page_size: int) -> Optional[Dict[str, Any]]:
        """Get playlist detail using YGKing API."""
        try:
            url = f"{self.YGKING_BASE_URL}/api/playlist"
            params = {"id": playlist_id}

            response = self._http_client.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            result = OnlineMusicAdapter.parse_ygking_playlist_detail(data)
            if result:
                # Apply pagination
                songs = result.get('songs', [])
                total = result.get('total', len(songs))
                start_idx = (page - 1) * page_size
                end_idx = start_idx + page_size
                result['songs'] = songs[start_idx:end_idx]
                result['total'] = total
                result['page'] = page
                result['page_size'] = page_size

            return result

        except Exception as e:
            logger.error(f"Get playlist detail from YGKing failed: {e}")
            return None

    def get_playback_url(self, song_mid: str, quality: Optional[str] = None) -> Optional[str]:
        """
        Get playback URL for a song.

        Args:
            song_mid: Song MID
            quality: Audio quality (master/flac/320/128), uses config default if None

        Returns:
            Playback URL or None
        """
        # Use configured quality if not specified
        if quality is None:
            quality = self._config.get_qqmusic_quality() if self._config else "320"

        # Prefer QQ Music local API if credential is available
        if self._has_qqmusic_credential() and self._qqmusic:
            # Try different qualities in order
            quality_fallback = ["320", "128", "flac"]
            start_index = quality_fallback.index(quality) if quality in quality_fallback else 0

            for q in quality_fallback[start_index:]:
                url = self._qqmusic.get_playback_url(song_mid, q)
                if url:
                    return url

            logger.debug(f"No playback URL via QQ Music local API for {song_mid}, trying remote API")

        # Use remote API (api.ygking.top) as fallback or when not logged in
        return self._get_playback_url_remote(song_mid, quality)

    def _get_playback_url_remote(self, song_mid: str, quality: str = "320") -> Optional[str]:
        """Get playback URL from remote API."""
        try:
            url = f"{self.YGKING_BASE_URL}/api/song/url"
            params = {
                "mid": song_mid,
                "quality": quality,
            }

            response = self._http_client.get(url, params=params, timeout=20)
            response.raise_for_status()
            data = response.json()

            if data.get("code") == 0:
                urls = data.get("data", {})
                if song_mid in urls and urls[song_mid]:
                    return urls[song_mid]

            logger.warning(f"No playback URL available for {song_mid}")
            return None

        except Exception as e:
            logger.error(f"Get playback URL from remote failed: {e}")
            return None

    def get_lyrics(self, song_mid: str) -> Dict[str, Optional[str]]:
        """
        Get lyrics for a song.

        Args:
            song_mid: Song MID

        Returns:
            Dict with lyric, qrc, trans keys
        """
        if self._has_qqmusic_credential() and self._qqmusic:
            return self._qqmusic.get_lyrics(song_mid)

        return {"lyric": None, "qrc": None, "trans": None}

    def get_song_detail(self, song_mid: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed song information.

        Args:
            song_mid: Song MID

        Returns:
            Dict with song details or None
        """
        # Prefer QQ Music local API if credential is available
        if self._has_qqmusic_credential() and self._qqmusic:
            return self._get_song_detail_qqmusic(song_mid)

        # Use YGKing remote API
        return self._get_song_detail_ygking(song_mid)

    def _get_song_detail_qqmusic(self, song_mid: str) -> Optional[Dict[str, Any]]:
        """Get song detail using QQ Music local API."""
        try:
            result = self._qqmusic.client.get_song_detail(song_mid)
            track_info = result.get("track_info", {})
            if track_info:
                return {
                    "title": track_info.get("title", ""),
                    "artist": ", ".join(s.get("name", "") for s in track_info.get("singer", [])),
                    "album": track_info.get("album", {}).get("name", "") if track_info.get("album") else "",
                    "duration": track_info.get("interval", 0),
                    "genre": track_info.get("genre"),
                    "language": track_info.get("language"),
                    "publish_date": track_info.get("publish_date"),
                }
        except Exception as e:
            logger.debug(f"QQ Music get_song_detail failed: {e}")

        return None

    def _get_song_detail_ygking(self, song_mid: str) -> Optional[Dict[str, Any]]:
        """Get song detail using YGKing remote API."""
        try:
            url = f"{self.YGKING_BASE_URL}/api/song/detail"
            params = {"mid": song_mid}

            response = self._http_client.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("code") == 0:
                song_data = data.get("data", {})
                return {
                    "title": song_data.get("title", ""),
                    "artist": ", ".join(s.get("name", "") for s in song_data.get("singer", [])),
                    "album": song_data.get("album", {}).get("name", "") if song_data.get("album") else "",
                    "duration": song_data.get("interval", 0),
                    "genre": song_data.get("genre"),
                    "language": song_data.get("language"),
                    "publish_date": song_data.get("publish_date"),
                }

        except Exception as e:
            logger.debug(f"YGKing get_song_detail failed: {e}")

        return None
