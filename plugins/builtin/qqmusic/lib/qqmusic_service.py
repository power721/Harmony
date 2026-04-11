"""
QQ Music service for Harmony music player.
Provides high-level interface for QQ Music integration.
"""

import logging
import time
from typing import Optional, Dict, List, Any, TYPE_CHECKING

from .media_helpers import build_album_cover_url
from .qqmusic_client import QQMusicClient
from .search_normalizers import (
    normalize_artist_item,
    normalize_detail_song,
    normalize_top_list_track,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class QQMusicService:
    """
    Service for QQ Music integration.
    """

    def __init__(self, credential: Optional[Dict[str, Any]] = None, http_client=None):
        """
        Initialize QQ Music service.

        Args:
            credential: Optional credential dict with musicid, musickey, login_type
        """
        self.client = QQMusicClient(credential, http_client=http_client)
        self._credential = credential

    @property
    def credential(self) -> Optional[Dict[str, Any]]:
        """Get current credential."""
        return self._credential

    @staticmethod
    def _build_song_payload(song_info: Dict[str, Any]) -> Dict[str, Any]:
        normalized = normalize_detail_song(
            {
                "mid": song_info.get("mid", "") or song_info.get("songmid", ""),
                "title": song_info.get("name", "") or song_info.get("songname", "") or song_info.get("title", ""),
                "singer": song_info.get("singer", []),
                "album": song_info.get("album", {}),
                "albumname": song_info.get("albumname", ""),
                "albummid": song_info.get("albummid", ""),
                "interval": song_info.get("interval", 0) or song_info.get("duration", 0),
            }
        )
        singers = song_info.get("singer", [])
        singer_list = []
        if isinstance(singers, list):
            singer_list = [
                {
                    "mid": singer.get("mid", ""),
                    "name": singer.get("name", ""),
                }
                for singer in singers
                if isinstance(singer, dict)
            ]
        return {
            "mid": normalized["mid"],
            "songmid": normalized["mid"],
            "id": song_info.get("id"),
            "name": normalized["title"],
            "title": normalized["title"],
            "singer": singer_list,
            "album": {
                "mid": normalized["album_mid"],
                "name": normalized["album"],
            },
            "albummid": normalized["album_mid"],
            "albumname": normalized["album"],
            "interval": normalized["duration"],
        }

    def is_credential_expired(self) -> bool:
        """
        Check if credential is expired.

        Returns:
            True if expired or no expiration info, False if valid
        """
        if not self._credential:
            return True

        expired_at = self._credential.get('expired_at')
        if not expired_at:
            # No expiration info, assume valid
            return False

        # expired_at is a timestamp, check if current time is past it
        return time.time() > expired_at

    def is_credential_refreshable(self) -> bool:
        """
        Check if credential can be refreshed.

        Returns:
            True if refresh_token or refresh_key is available
        """
        if not self._credential:
            return False

        return bool(
            self._credential.get('refresh_token') or
            self._credential.get('refresh_key')
        )

    async def refresh_credential(self) -> Optional[Dict[str, Any]]:
        """
        Refresh the credential using refresh_token.
        Uses local implementation without external dependencies.

        Returns:
            New credential dict or None if refresh failed
        """
        if not self._credential:
            logger.warning("No credential to refresh")
            return None

        if not self.is_credential_refreshable():
            logger.warning("Credential is not refreshable")
            return None

        try:
            import asyncio

            # Run synchronous refresh in executor
            loop = asyncio.get_event_loop()
            new_credential = await loop.run_in_executor(
                None,
                self.client.refresh_credential
            )

            if new_credential:
                # Update internal credential
                self._credential = new_credential
                logger.info("Credential refreshed successfully")
            return new_credential

        except Exception as e:
            logger.error(f"Failed to refresh credential: {e}")
            return None

    def search_tracks(self, keyword: str, page: int = 1,
                      page_size: int = 20) -> List[Dict[str, Any]]:
        """
        Search for tracks.

        Args:
            keyword: Search keyword
            page: Page number (1-based)
            page_size: Number of results per page

        Returns:
            List of track dictionaries with keys:
            - mid: Song MID
            - title: Song title
            - singer: Singer name
            - album: Album name
            - duration: Duration in seconds
            - url: Preview URL (if available)
        """
        try:
            result = self.client.search(keyword, search_type='song',
                                        page_num=page, page_size=page_size)

            if not result or 'body' not in result or not isinstance(result.get('body'), dict):
                return []

            # Mobile API uses item_song key
            songs = result['body'].get('item_song', [])

            tracks = []
            for song in songs:
                # Handle singer data (can be dict or list)
                singer_info = song.get('singer', {})
                if isinstance(singer_info, list) and singer_info:
                    singer_name = singer_info[0].get('name', '')
                else:
                    singer_name = singer_info.get('name', '') if isinstance(singer_info, dict) else ''

                track = {
                    'mid': song.get('songmid', ''),
                    'title': song.get('songname', ''),
                    'singer': singer_name,
                    'album': song.get('albumname', ''),
                    'duration': song.get('interval', 0),  # in seconds
                    'mid_url': song.get('songmid', ''),
                }
                tracks.append(track)

            return tracks

        except Exception as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            return []

    def complete(self, keyword: str) -> List[Dict[str, Any]]:
        """
        搜索词补全建议.

        Args:
            keyword: 关键词.

        Returns:
            搜索建议列表，每个建议包含 hint 和 type 键
        """
        try:
            result = self.client.complete(keyword)

            if not result:
                return []

            # Parse suggestions from response - items is at top level
            # 实际响应格式:
            # {
            #   "items": [
            #     { "hint": "建议词", "type": 0 },
            #     ...
            #   ]
            # }

            items = result.get('items', [])
            suggestions = []
            for item in items:
                hint = item.get('hint', '')
                if hint:  # Only add non-empty hints
                    suggestions.append({
                        'type': item.get('type', 0),
                        'hint': hint,
                    })

            return suggestions

        except Exception as e:
            logger.error(f"Search completion failed: {e}", exc_info=True)
            return []

    def get_hotkey(self) -> List[Dict[str, Any]]:
        """
        获取热搜词列表.

        Returns:
            热搜词列表，每个热搜词包含 title, content 等键
        """
        try:
            result = self.client.get_hotkey()

            if not result:
                return []

            # Parse hotkey from response
            # 实际响应格式:
            # {
            #   "vec_hotkey": [  # 注意：API返回的是小写的vec_hotkey
            #     { "title": "热搜词", "query": "搜索词", ... },
            #     ...
            #   ]
            # }

            # 尝试两种键名
            hotkeys = result.get('vec_hotkey', []) or result.get('vecHotkey', [])
            results = []
            for item in hotkeys:
                title = item.get('title', '')
                query = item.get('query', title)  # query是实际搜索词
                if title:
                    results.append({
                        'title': title,
                        'query': query,
                        'content': item.get('content', query),
                    })

            return results

        except Exception as e:
            logger.error(f"Get hotkey failed: {e}", exc_info=True)
            return []

    def get_playback_url_info(self, song_mid: str, quality: str = 'flac') -> Optional[Dict[str, Any]]:
        """
        Get playback URL and file type information for a song.

        Args:
            song_mid: Song MID
            quality: Audio quality (master/atmos/flac/320/128)

        Returns:
            Dict with url/quality/extension metadata, or None if failed
        """
        try:
            result = self.client.get_song_url(song_mid, quality=quality)
            urls = result.get('urls', {})

            for url in urls.values():
                if url:
                    return {
                        'url': url,
                        'quality': result.get('quality'),
                        'file_type': result.get('file_type'),
                        'extension': result.get('extension'),
                    }

            return None

        except Exception as e:
            logger.error(f"Get playback URL failed: {e}", exc_info=True)
            return None

    def get_playback_url(self, song_mid: str, quality: str = 'flac') -> Optional[str]:
        """Get playback URL for a song."""
        info = self.get_playback_url_info(song_mid, quality=quality)
        return info.get('url') if info else None

    def get_lyrics(self, song_mid: str) -> Dict[str, Optional[str]]:
        """
        Get lyrics for a song.

        Args:
            song_mid: Song MID

        Returns:
            Dictionary with keys:
            - lyric: Plain text lyrics (lrc format)
            - qrc: Word-by-word lyrics (if available)
            - trans: Translation (if available)
        """
        try:
            result = self.client.get_lyric(song_mid, qrc=True, trans=True)

            return {
                'lyric': result.get('lyric'),
                'qrc': result.get('qrc'),
                'trans': result.get('trans'),
            }

        except Exception as e:
            logger.error(f"Get lyrics failed: {e}", exc_info=True)
            return {'lyric': None, 'qrc': None, 'trans': None}

    def get_album_info(self, album_mid: str, page: int = 1, page_size: int = 50) -> Optional[Dict[str, Any]]:
        """
        Get album information with pagination.

        Args:
            album_mid: Album MID
            page: Page number (1-based)
            page_size: Songs per page

        Returns:
            Album information dictionary or None
        """
        from . import adapter as plugin_adapter

        try:
            # Get album basic info
            basic_result = self.client.get_album(album_mid)

            if not basic_result:
                logger.warning(f"Album {album_mid} returned empty result")
                return None

            # Get album songs with pagination
            begin = (page - 1) * page_size
            songs_result = self.client.get_album_songs(album_mid, begin=begin, num=page_size)

            # Use adapter to parse
            result = plugin_adapter.parse_album_detail(basic_result, songs_result)

            if not result:
                return None

            result['page'] = page
            result['page_size'] = page_size

            return result

        except Exception as e:
            logger.error(f"Get album info failed: {e}", exc_info=True)
            return None

    def get_album_info_with_fav_status(self, album_mid: str, page: int = 1, page_size: int = 50) -> Optional[
        Dict[str, Any]]:
        """
        Get album information with fav status in a single batch request.

        This is more efficient than calling get_album_info and query_album_fav_status separately.

        Args:
            album_mid: Album MID
            page: Page number (1-based)
            page_size: Songs per page

        Returns:
            Album information dictionary with fav_status field, or None
        """
        from . import adapter as plugin_adapter

        try:
            uin = str(self.credential.get("musicid", "")) if self.credential else ""

            # Build batch request
            requests = {
                "req_1": {
                    "module": "music.musichallAlbum.AlbumInfoServer",
                    "method": "GetAlbumDetail",
                    "param": {
                        "albumMid": album_mid,
                        "albumID": 0
                    }
                },
                "req_2": {
                    "module": "music.musichallAlbum.AlbumSongList",
                    "method": "GetAlbumSongList",
                    "param": {
                        "albumMid": album_mid,
                        "albumID": 0,
                        "begin": (page - 1) * page_size,
                        "num": page_size,
                        "order": 2
                    }
                }
            }

            # Add fav status query if logged in
            if self._credential:
                requests["req_3"] = {
                    "module": "music.musicasset.AlbumFavRead",
                    "method": "IsAlbumFan",
                    "param": {
                        "uin": int(uin) if uin.isdigit() else uin,
                        "v_albumMid": [album_mid]
                    }
                }

            # Make batch request
            batch_result = self.client.make_batch_request(requests)

            if not batch_result:
                logger.warning("Album batch request returned None")
                return None

            # Parse album info from req_1 and req_2
            req_1 = batch_result.get("req_1", {})
            req_2 = batch_result.get("req_2", {})

            if req_1.get("code") != 0 or req_2.get("code") != 0:
                logger.warning(
                    f"Album batch request failed: req_1 code={req_1.get('code')}, req_2 code={req_2.get('code')}")
                return None

            # Combine results - extract data from nested structure
            req_1_data = req_1.get('data', req_1)
            req_2_data = req_2.get('data', req_2)
            result = plugin_adapter.parse_album_detail(req_1_data, req_2_data)
            if not result:
                logger.warning("Failed to parse album detail from batch request")
                return None

            result['page'] = page
            result['page_size'] = page_size

            # Parse fav status from req_3 if available
            if self._credential and "req_3" in batch_result:
                req_3 = batch_result.get("req_3", {})
                if req_3.get("code") == 0:
                    data = req_3.get("data", {})
                    m_fan = data.get("m_fan", {})
                    is_fav = m_fan.get(album_mid, False)
                    result['fav_status'] = is_fav
                    logger.debug(f"Album fav status from batch request: {is_fav}")
                else:
                    result['fav_status'] = False
            else:
                result['fav_status'] = False

            return result

        except Exception as e:
            logger.error(f"Get album info with fav status failed: {e}", exc_info=True)
            return None

    def get_playlist_info_with_fav_status(self, playlist_id: str, page: int = 1, page_size: int = 50) -> Optional[
        Dict[str, Any]]:
        """
        Get playlist information with fav status in a single batch request.

        This is more efficient than calling get_playlist_info and query_playlist_fav_status separately.

        Args:
            playlist_id: Playlist ID
            page: Page number (1-based)
            page_size: Songs per page

        Returns:
            Playlist information dictionary with fav_status field, or None
        """
        try:
            # QQ Music API max return is 30 songs per request
            # Use server-side pagination with song_begin and song_num
            song_begin = (page - 1) * page_size
            # Cap at 30 to match API limit
            song_num = min(page_size, 30)

            # Build batch request using the more complete API
            requests = {
                "req_1": {
                    "module": "music.srfDissInfo.aiDissInfo",
                    "method": "uniform_get_Dissinfo",
                    "param": {
                        "disstid": int(playlist_id),
                        "userinfo": 1,
                        "tag": 1,
                        "orderlist": 1,
                        "song_begin": song_begin,
                        "song_num": song_num,
                        "onlysonglist": 0,
                        "enc_host_uin": ""
                    }
                }
            }

            # Add fav status query only for first page if logged in
            if self._credential:
                requests["req_2"] = {
                    "module": "music.musicasset.PlaylistFavRead",
                    "method": "IsPlaylistFan",
                    "param": {
                        "v_tid": [int(playlist_id) if str(playlist_id).isdigit() else playlist_id]
                    }
                }

            # Make batch request
            batch_result = self.client.make_batch_request(requests)

            if not batch_result:
                logger.warning("Playlist batch request returned None")
                return None

            # Parse playlist info from req_1
            req_1 = batch_result.get("req_1", {})

            if req_1.get("code") != 0:
                logger.warning(f"Playlist batch request failed: req_1 code={req_1.get('code')}")
                return None

            # Extract data from req_1.data - the actual playlist data is nested here
            req_1_data = req_1.get('data', {})

            # Parse response - API returns paginated songs
            songs = req_1_data.get('songlist', []) or req_1_data.get('songs', []) or []
            # Use total_song_num from API if available, otherwise count returned songs
            total_songs = req_1_data.get('total_song_num', len(songs))

            # Get playlist info from dirinfo (for CgiGetDiss API)
            dirinfo = req_1_data.get('dirinfo', {})

            # Get playlist name - try multiple locations
            import re
            name = ''
            if dirinfo:
                name = dirinfo.get('title', '')
            if not name:
                name = req_1_data.get('dissname', '') or req_1_data.get('title', '') or req_1_data.get('name', '')
            if name:
                name = re.sub(r'<[^>]+>', '', name)  # Remove HTML tags

            # Get creator - try multiple locations
            creator = ''
            if dirinfo:
                creator_data = dirinfo.get('creator', {})
                if isinstance(creator_data, dict):
                    creator = creator_data.get('nick', '') or creator_data.get('name', '')
            if not creator:
                creator_data = req_1_data.get('creator', {})
                if isinstance(creator_data, dict):
                    creator = creator_data.get('name', '') or creator_data.get('nick', '')
                elif isinstance(creator_data, str):
                    creator = creator_data
            if not creator:
                creator = req_1_data.get('nick', '') or req_1_data.get('nickname', '')

            # Get cover
            cover = ''
            if dirinfo:
                cover = dirinfo.get('picurl', '') or dirinfo.get('picurl2', '')
            if not cover:
                cover = req_1_data.get('logo', '') or req_1_data.get('cover', '')

            playlist_result = {
                'id': dirinfo.get('id', '') if dirinfo else (
                        req_1_data.get('tid', '') or req_1_data.get('dissid', '') or str(playlist_id)),
                'name': name,
                'creator': creator,
                'cover': cover,
                'description': dirinfo.get('desc', '') if dirinfo else '',
                'songs': songs,
                'total': total_songs,
                'page': page,
                'page_size': page_size,
            }

            # Parse fav status from req_2 if available
            if self._credential and "req_2" in batch_result:
                req_2 = batch_result.get("req_2", {})
                if req_2.get("code") == 0:
                    req_2_data = req_2.get("data", {})
                    m_fan = req_2_data.get("m_fan", {})

                    # Try to match with both string and int keys
                    # API returns string keys like "8035980030"
                    is_fav = False
                    playlist_id_str = str(playlist_id)
                    if playlist_id_str in m_fan:
                        is_fav = m_fan[playlist_id_str]
                    elif playlist_id_str.isdigit() and int(playlist_id_str) in m_fan:
                        is_fav = m_fan[int(playlist_id_str)]
                    elif playlist_id in m_fan:
                        is_fav = m_fan[playlist_id]

                    playlist_result['fav_status'] = is_fav
                    logger.debug(f"Playlist fav status from batch request: {is_fav}")
                else:
                    playlist_result['fav_status'] = False
            else:
                playlist_result['fav_status'] = False

            return playlist_result

        except Exception as e:
            logger.error(f"Get playlist info with fav status failed: {e}", exc_info=True)
            return None

    def get_playlist_info(self, playlist_id: str, page: int = 1, page_size: int = 50) -> Optional[Dict[str, Any]]:
        """
        Get playlist information with pagination.

        Args:
            playlist_id: Playlist ID
            page: Page number (1-based)
            page_size: Songs per page

        Returns:
            Playlist information dictionary or None
        """
        try:
            result = self.client.get_playlist(playlist_id)

            if not result:
                logger.warning(f"Playlist {playlist_id} returned empty result")
                return None

            # Parse response
            all_songs = result.get('songlist', []) or result.get('songs', []) or []
            total_songs = len(all_songs)

            # Pagination
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            songs = all_songs[start_idx:end_idx]

            # Get playlist info from dirinfo (for CgiGetDiss API)
            dirinfo = result.get('dirinfo', {})

            # Get playlist name - try multiple locations
            import re
            name = ''
            if dirinfo:
                name = dirinfo.get('title', '')
            if not name:
                name = result.get('dissname', '') or result.get('title', '') or result.get('name', '')
            if name:
                name = re.sub(r'<[^>]+>', '', name)  # Remove HTML tags

            # Get creator - try multiple locations
            creator = ''
            if dirinfo:
                creator_data = dirinfo.get('creator', {})
                if isinstance(creator_data, dict):
                    creator = creator_data.get('nick', '') or creator_data.get('name', '')
            if not creator:
                creator_data = result.get('creator', {})
                if isinstance(creator_data, dict):
                    creator = creator_data.get('name', '') or creator_data.get('nick', '')
                elif isinstance(creator_data, str):
                    creator = creator_data
            if not creator:
                creator = result.get('nick', '') or result.get('nickname', '')

            # Get cover
            cover = ''
            if dirinfo:
                cover = dirinfo.get('picurl', '') or dirinfo.get('picurl2', '')
            if not cover:
                cover = result.get('logo', '') or result.get('cover', '')

            return {
                'id': dirinfo.get('id', '') if dirinfo else (
                        result.get('tid', '') or result.get('dissid', '') or str(playlist_id)),
                'name': name,
                'creator': creator,
                'cover': cover,
                'description': dirinfo.get('desc', '') if dirinfo else '',
                'songs': songs,
                'total': total_songs,
                'page': page,
                'page_size': page_size,
            }

        except Exception as e:
            logger.error(f"Get playlist info failed: {e}", exc_info=True)
            return None

    def get_singer_info(self, singer_mid: str, page: int = 1, page_size: int = 50) -> Optional[Dict[str, Any]]:
        """
        Get singer information with pagination.

        Args:
            singer_mid: Singer MID
            page: Page number (1-based)
            page_size: Songs per page

        Returns:
            Singer information dictionary or None
        """
        try:
            result = self.client.get_singer(singer_mid)

            if not result:
                return None

            # Parse singer_list array response
            singer_list = result.get('singer_list', [])
            if not singer_list:
                return None

            singer_data = singer_list[0]
            basic_info = singer_data.get('basic_info', {})
            ex_info = singer_data.get('ex_info', {})
            pic_info = singer_data.get('pic', {})

            # Get avatar URL - try different fields
            avatar = pic_info.get('pic') or pic_info.get('big') or pic_info.get('big_black') or pic_info.get(
                'big_white') or ''
            # If no avatar in pic, construct from singer_mid
            if not avatar:
                singer_mid_from_info = basic_info.get('singer_mid', '')
                has_photo = basic_info.get('has_photo', 0)
                if has_photo and singer_mid_from_info:
                    avatar = f"http://y.gtimg.cn/music/photo_new/T001R300x300M000{singer_mid_from_info}_{has_photo}.jpg"

            # Get singer name
            singer_name = basic_info.get('name', '')
            songs = []
            total_songs = 0

            # Get singer's songs using dedicated API
            begin = (page - 1) * page_size
            songs_result = self.client.get_singer_songs(singer_mid, number=page_size, begin=begin)

            if songs_result:
                # Get total count
                total_songs = songs_result.get('totalNum', 0)
                logger.info(f"Total songs for {singer_name}: {total_songs}")

                # Parse songs
                song_list = songs_result.get('songList', [])
                for song in song_list:
                    song_info = song.get('songInfo', song)
                    songs.append(self._build_song_payload(song_info))

                logger.info(f"Page {page}: Got {len(songs)} songs for {singer_name}")

            # Use actual returned count as page_size for accurate pagination
            # QQ Music API may return fewer songs than requested (max 30)
            actual_page_size = len(songs) if songs else page_size

            return {
                'mid': basic_info.get('singer_mid', singer_mid),
                'name': singer_name,
                'desc': ex_info.get('desc', ''),
                'avatar': avatar,
                'album_count': basic_info.get('album_total', 0),
                'songs': songs,
                'total': total_songs,
                'page': page,
                'page_size': actual_page_size,
            }

        except Exception as e:
            logger.error(f"Get singer info failed: {e}", exc_info=True)
            return None

    def get_singer_info_with_follow_status(self, singer_mid: str, page: int = 1, page_size: int = 50) -> Optional[
        Dict[str, Any]]:
        """
        Get singer information with follow status in a single batch request.

        This is more efficient than calling get_singer_info and query_singer_follow_status separately.

        Args:
            singer_mid: Singer MID
            page: Page number (1-based)
            page_size: Songs per page

        Returns:
            Singer information dictionary with follow_status field, or None
        """
        try:
            # Build batch request using the same API endpoints as the individual calls
            requests = {
                "req_1": {
                    "module": "music.musichallSinger.SingerInfoInter",
                    "method": "GetSingerDetail",
                    "param": {
                        "singer_mids": [singer_mid],
                        "ex_singer": 1,
                        "wiki_singer": 0,
                        "group_singer": 0,
                        "pic": 1,
                        "photos": 0
                    }
                },
                "req_2": {
                    "module": "musichall.song_list_server",
                    "method": "GetSingerSongList",
                    "param": {
                        "singerMid": singer_mid,
                        "order": 1,
                        "begin": (page - 1) * page_size,
                        "num": page_size
                    }
                },
                "req_3": {
                    "module": "music.musichallAlbum.AlbumListServer",
                    "method": "GetAlbumList",
                    "param": {
                        "singerMid": singer_mid,
                        "order": 0,
                        "begin": 0,
                        "num": 10,
                        "songNumTag": 0,
                        "singerID": 0
                    }
                }
            }

            # Add follow status query if logged in
            if self._credential:
                requests["req_4"] = {
                    "module": "Concern.ConcernSystemServer",
                    "method": "cgi_qry_concern_status",
                    "param": {
                        "vec_userinfo": [{"usertype": 1, "userid": singer_mid}],
                        "opertype": 5,
                        "encrypt_singerid": 1
                    }
                }

            # Make batch request
            batch_result = self.client.make_batch_request(requests)

            if not batch_result:
                logger.warning("Batch request returned None")
                return None

            # Parse singer info from req_1 and req_2
            req_1 = batch_result.get("req_1", {})
            req_2 = batch_result.get("req_2", {})
            req_3 = batch_result.get("req_3", {})

            if req_1.get("code") != 0:
                logger.warning(f"Batch request failed: req_1 code={req_1.get('code')}")
                return None

            # Extract singer data from req_1 - data is nested under req_1.data.singer_list
            req_1_data = req_1.get('data', {})
            singer_list = req_1_data.get('singer_list', [])
            if not singer_list:
                logger.warning(
                    f"Batch request succeeded but no singer_list found in req_1.data, keys: {list(req_1_data.keys())}")
                return None

            singer_data = singer_list[0]
            basic_info = singer_data.get('basic_info', {})
            ex_info = singer_data.get('ex_info', {})
            pic_info = singer_data.get('pic', {})

            # Get avatar URL
            avatar = pic_info.get('pic') or pic_info.get('big') or pic_info.get('big_black') or pic_info.get(
                'big_white') or ''
            if not avatar:
                singer_mid_from_info = basic_info.get('singer_mid', '')
                has_photo = basic_info.get('has_photo', 0)
                if has_photo and singer_mid_from_info:
                    avatar = f"http://y.gtimg.cn/music/photo_new/T001R300x300M000{singer_mid_from_info}_{has_photo}.jpg"

            singer_name = basic_info.get('name', '')
            foreign_name = ex_info.get('foreign_name', '')
            birthday = ex_info.get('birthday', '')
            desc = ex_info.get('desc', '')

            # Parse songs from req_2
            songs = []
            total_songs = 0

            if req_2.get("code") == 0:
                req_2_data = req_2.get("data", {})
                song_list = req_2_data.get("songList", [])
                total_songs = req_2_data.get("totalNum", 0)

                for song in song_list:
                    song_info = song.get("songInfo", song)
                    songs.append(self._build_song_payload(song_info))

            # Parse albums from req_3
            albums = []
            total_albums = 0

            if req_3.get("code") == 0:
                req_3_data = req_3.get("data", {})
                album_list = req_3_data.get("albumList", [])
                total_albums = req_3_data.get("total", 0)

                for album in album_list:
                    album_mid = album.get("albumMid", "")
                    cover_url = build_album_cover_url(album_mid, 300) or ""
                    albums.append({
                        'mid': album_mid,
                        'id': album.get("albumID", 0),
                        'name': album.get("albumName", ""),
                        'cover_url': cover_url,
                        'singer_name': album.get("singerName", ""),
                        'publish_date': album.get("publishDate", ""),
                    })

            # Parse follow status from req_4 if available
            follow_status = False
            if self._credential and "req_4" in batch_result:
                req_4 = batch_result.get("req_4", {})
                if req_4.get("code") == 0:
                    req_4_data = req_4.get("data", {})
                    singer_status = req_4_data.get("map_singer_status", {})
                    follow_status = singer_status.get(singer_mid, 0) == 1

            return {
                'mid': basic_info.get('singer_mid', singer_mid),
                'name': singer_name,
                'foreign_name': foreign_name,
                'birthday': birthday,
                'desc': desc,
                'avatar': avatar,
                'album_count': total_albums,
                'songs': songs,
                'albums': albums,
                'total': total_songs,
                'page': page,
                'page_size': len(songs),
                'follow_status': follow_status,
            }

        except Exception as e:
            logger.error(f"Get singer info with follow status failed: {e}", exc_info=True)
            return None

    def get_singer_albums(self, singer_mid: str, number: int = 10, begin: int = 0) -> Dict[str, Any]:
        """
        Get singer's album list.

        Args:
            singer_mid: Singer MID
            number: Number of albums to return
            begin: Pagination start position

        Returns:
            Dict with 'albums' list and 'total' count
        """
        try:
            result = self.client.get_album_list(singer_mid, number=number, begin=begin)

            if not result:
                logger.debug("get_singer_albums: client.get_album_list returned empty")
                return {'albums': [], 'total': 0}

            albums = []
            album_list = result.get('albumList', [])
            total = result.get('total', 0)
            logger.debug(f"get_singer_albums: Got {len(album_list)} albums from API, total={total}")

            for album in album_list:
                album_mid = album.get('albumMid', '') or album.get('mid', '')
                cover_url = build_album_cover_url(album_mid, 300) or ""

                albums.append({
                    'mid': album_mid,
                    'name': album.get('albumName', '') or album.get('name', ''),
                    'singer_mid': singer_mid,
                    'singer_name': album.get('singerName', ''),
                    'cover_url': cover_url,
                    'song_count': album.get('totalNum', 0),
                    'publish_date': album.get('publishDate', ''),
                    'album_type': album.get('albumType', ''),
                })

            return {'albums': albums, 'total': total}

        except Exception as e:
            logger.error(f"Get singer albums failed: {e}", exc_info=True)
            return {'albums': [], 'total': 0}

    def get_top_lists(self) -> List[Dict[str, Any]]:
        """
        Get music top lists.

        Returns:
            List of top list dictionaries with id and title
        """
        try:
            result = self.client.get_top_lists()

            if not result:
                return []

            groups = result.get('group', [])
            top_lists = [
                {
                    'id': top_list.get('topId', ''),
                    'title': top_list.get('title', ''),
                    'type': top_list.get('type', 0),
                }
                for group in groups
                for top_list in group.get('toplist', [])
            ]

            return top_lists

        except Exception as e:
            logger.error(f"Get top lists failed: {e}", exc_info=True)
            return []

    def get_top_list_songs(self, top_id: int, num: int = 100) -> List[Dict[str, Any]]:
        """
        Get songs from a specific top list.

        Args:
            top_id: Top list ID
            num: Number of songs to return

        Returns:
            List of song dictionaries
        """
        try:
            result = self.client.get_top_list_detail(top_id, num)

            if not result:
                return []

            # Songs can be in different locations:
            # - result.songInfoList (has full album and duration info - prefer this)
            # - result.data.songInfoList (newer API)
            # - result.song (some APIs)
            # - result.data.song (unsigned endpoint)
            # - result.list (signed endpoint)
            songs = result.get('songInfoList', [])
            if not songs:
                inner_data = result.get('data', {})
                if isinstance(inner_data, dict):
                    songs = inner_data.get('songInfoList', [])
                    if not songs:
                        songs = inner_data.get('song', [])
            if not songs:
                songs = result.get('song', [])
            if not songs:
                songs = result.get('list', [])

            # If songs don't have mid, query by id to get mid
            songs_need_mid = [s for s in songs if not s.get('songmid') and not s.get('mid') and s.get('songId')]
            if songs_need_mid:
                song_ids = [s['songId'] for s in songs_need_mid]
                track_infos = self.client.query_songs_by_ids(song_ids)
                # Create a map from id to track info
                id_to_track = {t.get('id'): t for t in track_infos}
                for song in songs_need_mid:
                    track_info = id_to_track.get(song.get('songId'))
                    if track_info:
                        song['songmid'] = track_info.get('mid', '')

            return [normalize_top_list_track(song) for song in songs]

        except Exception as e:
            logger.error(f"Get top list songs failed: {e}", exc_info=True)
            return []

    def _get_euin(self) -> str:
        """Get encrypted UIN from credential, fetch from API if missing."""
        if not self._credential:
            return ""
        euin = (
                self._credential.get("encrypt_uin")
                or self._credential.get("encryptUin")
        )
        if euin:
            return euin
        # Fetch euin from API via musicid
        euin = self.client.get_euin()
        if euin:
            self._credential["encrypt_uin"] = euin
            self._credential["encryptUin"] = euin
        return euin

    def _get_uin(self) -> str:
        """Get UIN from credential."""
        if not self._credential:
            return ""
        return str(self._credential.get("musicid", ""))

    def get_my_fav_songs(self, page: int = 1, num: int = 30) -> List[Dict[str, Any]]:
        """Get current user's favorite songs."""
        try:
            euin = self._get_euin()
            if not euin:
                return []
            result = self.client.get_fav_song(euin, page=page, num=num)
            if not result:
                return []
            songs = result.get("songlist", []) or []
            tracks = []
            for song in songs:
                song_info = song.get("data", song) if isinstance(song, dict) else song
                if not isinstance(song_info, dict):
                    continue
                singer_info = song_info.get("singer", [])
                if isinstance(singer_info, list) and singer_info:
                    singer_name = " / ".join(s.get("name", "") for s in singer_info)
                elif isinstance(singer_info, dict):
                    singer_name = singer_info.get("name", "")
                else:
                    singer_name = ""
                album_info = song_info.get("album", {})
                album_name = album_info.get("name", "") if isinstance(album_info, dict) else ""
                tracks.append({
                    "id": song_info.get("songid") or song_info.get("id"),
                    "mid": song_info.get("songmid", "") or song_info.get("mid", ""),
                    "title": song_info.get("songname", "") or song_info.get("name", "") or song_info.get("title", ""),
                    "singer": singer_name,
                    "album": album_name,
                    "album_mid": album_info.get("mid", "") if isinstance(album_info, dict) else "",
                    "duration": song_info.get("interval", 0) or 0,
                    "cover_url": (f"https://y.gtimg.cn/music/photo_new/T002R300x300M000{album_info.get('mid', '')}.jpg"
                                  if isinstance(album_info, dict) and album_info.get("mid") else ""),
                })
            return tracks
        except Exception as e:
            logger.error(f"Get favorite songs failed: {e}", exc_info=True)
            return []

    def get_my_created_songlists(self) -> List[Dict[str, Any]]:
        """Get current user's created playlists."""
        try:
            uin = self._get_uin()
            if not uin:
                return []
            result = self.client.get_created_songlist(uin)
            if not result:
                return []
            # API returns 'v_playlist' key
            playlists = result.get("v_playlist", []) or result.get("playlist", []) or []
            items = []
            for pl in playlists:
                if not isinstance(pl, dict):
                    continue
                items.append({
                    "id": pl.get("tid", "") or pl.get("dissid", ""),
                    "title": pl.get("dirName", "") or pl.get("dissname", "") or pl.get("name", ""),
                    "cover_url": pl.get("picUrl", "") or pl.get("bigpicUrl", "") or pl.get("logo", ""),
                    "song_count": pl.get("songNum", 0) or pl.get("song_cnt", 0),
                    "creator": pl.get("nick", "") or pl.get("nickname", ""),
                })
            return items
        except Exception as e:
            logger.error(f"Get created songlists failed: {e}", exc_info=True)
            return []

    def get_my_fav_songlists(self, page: int = 1, num: int = 30) -> List[Dict[str, Any]]:
        """Get current user's favorited external playlists."""
        try:
            euin = self._get_euin()
            if not euin:
                return []
            result = self.client.get_fav_songlist(euin, page=page, num=num)
            if not result:
                return []
            # API returns 'v_list' key
            playlists = result.get("v_list", []) or result.get("playlist", []) or []
            items = []
            for pl in playlists:
                if not isinstance(pl, dict):
                    continue
                items.append({
                    "id": pl.get("tid", "") or pl.get("dissid", ""),
                    "title": pl.get("name", "") or pl.get("dissname", ""),
                    "cover_url": pl.get("logo", "") or pl.get("albumPicUrl", ""),
                    "song_count": pl.get("songnum", 0) or pl.get("song_cnt", 0),
                    "creator": pl.get("nickname", ""),
                })
            return items
        except Exception as e:
            logger.error(f"Get favorite songlists failed: {e}", exc_info=True)
            return []

    def get_my_fav_albums(self, page: int = 1, num: int = 30) -> List[Dict[str, Any]]:
        """Get current user's favorited albums."""
        try:
            euin = self._get_euin()
            if not euin:
                return []
            result = self.client.get_fav_album(euin, page=page, num=num)
            if not result:
                return []
            # API returns 'v_list' key
            albums = result.get("v_list", []) or result.get("albumList", []) or []
            items = []
            for album in albums:
                if not isinstance(album, dict):
                    continue
                album_mid = album.get("mid", "") or album.get("albumMid", "")
                # Build singer list from v_singer
                v_singer = album.get("v_singer", [])
                singer_name = ""
                if isinstance(v_singer, list) and v_singer:
                    singer_name = " / ".join(s.get("name", "") for s in v_singer if isinstance(s, dict))
                items.append({
                    "mid": album_mid,
                    "title": album.get("name", "") or album.get("albumName", ""),
                    "cover_url": (f"https://y.gtimg.cn/music/photo_new/T002R300x300M000{album_mid}.jpg"
                                  if album_mid else album.get("logo", "")),
                    "singer_name": singer_name or album.get("singerName", ""),
                    "song_count": album.get("songnum", 0) or album.get("totalNum", 0),
                })
            return items
        except Exception as e:
            logger.error(f"Get favorite albums failed: {e}", exc_info=True)
            return []

    def get_followed_singers(self, page: int = 1, size: int = 10) -> List[Dict[str, Any]]:
        """Get current user's followed singers."""
        try:
            uin = self._get_uin()
            if not uin:
                return []
            result = self.client.get_followed_singers(uin, from_idx=(page - 1) * size, size=size)
            if not result:
                return []
            singers = (
                    result.get("List", [])
                    or result.get("list", [])
                    or result.get("singerList", [])
                    or []
            )
            items = []
            for singer in singers:
                if not isinstance(singer, dict):
                    continue
                normalized = normalize_artist_item(
                    {
                        **singer,
                        "cover_url": singer.get("AvatarUrl", "") or singer.get("cover_url", ""),
                    }
                )
                items.append({
                    "mid": normalized["mid"] or singer.get("MID", ""),
                    "name": normalized["name"] or singer.get("Name", ""),
                    "desc": singer.get("desc", "") or singer.get("Desc", ""),
                    "cover_url": normalized["avatar_url"] or singer.get("AvatarUrl", ""),
                    "fan_count": normalized["fan_count"],
                })
            return items
        except Exception as e:
            logger.error(f"Get followed singers failed: {e}", exc_info=True)
            return []

    def follow_singer(self, singer_mid: str) -> bool:
        """Follow a singer. Returns True on success."""
        try:
            if not self._credential:
                return False
            result = self.client.follow_singer(singer_mid)
            return bool(result)
        except Exception as e:
            logger.error(f"Follow singer failed: {e}", exc_info=True)
            return False

    def unfollow_singer(self, singer_mid: str) -> bool:
        """Unfollow a singer. Returns True on success."""
        try:
            if not self._credential:
                return False
            result = self.client.unfollow_singer(singer_mid)
            return bool(result)
        except Exception as e:
            logger.error(f"Unfollow singer failed: {e}", exc_info=True)
            return False

    def fav_song(self, song_id: int) -> bool:
        """Add a song to favorites. Returns True on success."""
        try:
            if not self._credential:
                return False
            result = self.client.fav_song(song_id)
            return bool(result)
        except Exception as e:
            logger.error(f"Favorite song failed: {e}", exc_info=True)
            return False

    def unfav_song(self, song_id: int) -> bool:
        """Remove a song from favorites. Returns True on success."""
        try:
            if not self._credential:
                return False
            result = self.client.unfav_song(song_id)
            return bool(result)
        except Exception as e:
            logger.error(f"Unfavorite song failed: {e}", exc_info=True)
            return False

    def fav_album(self, album_mid: str) -> bool:
        """Favorite an album. Returns True on success."""
        try:
            if not self._credential:
                return False
            result = self.client.fav_album(album_mid)
            return bool(result)
        except Exception as e:
            logger.error(f"Favorite album failed: {e}", exc_info=True)
            return False

    def unfav_album(self, album_mid: str) -> bool:
        """Unfavorite an album. Returns True on success."""
        try:
            if not self._credential:
                return False
            result = self.client.unfav_album(album_mid)
            return bool(result)
        except Exception as e:
            logger.error(f"Unfavorite album failed: {e}", exc_info=True)
            return False

    def fav_playlist(self, playlist_id) -> bool:
        """Favorite a playlist. Returns True on success."""
        try:
            if not self._credential:
                return False
            result = self.client.fav_playlist(playlist_id)
            return bool(result)
        except Exception as e:
            logger.error(f"Favorite playlist failed: {e}", exc_info=True)
            return False

    def unfav_playlist(self, playlist_id) -> bool:
        """Unfavorite a playlist. Returns True on success."""
        try:
            if not self._credential:
                return False
            result = self.client.unfav_playlist(playlist_id)
            return bool(result)
        except Exception as e:
            logger.error(f"Unfavorite playlist failed: {e}", exc_info=True)
            return False

    def set_credential(self, credential: Dict[str, Any]):
        """
        Update credential for authenticated requests.

        Args:
            credential: Credential dict with musicid, musickey, login_type
        """
        self._credential = credential
        self.client.credential = credential
        self.client._set_credential_headers()

    def get_home_feed(self) -> List[Dict[str, Any]]:
        """
        获取每日30首推荐歌曲.

        Returns:
            歌曲列表
        """
        try:
            result = self.client.get_home_feed()

            if not isinstance(result, dict) or 'v_shelf' not in result:
                return []

            # 找到"每日30首"卡片或"猜你喜欢"卡片
            target_id = None
            shelves = result['v_shelf']

            for shelf in shelves:
                if not isinstance(shelf, dict):
                    continue

                for niche in shelf.get('v_niche', []):
                    if not isinstance(niche, dict):
                        continue

                    for card in niche.get('v_card', []):
                        if not isinstance(card, dict):
                            continue

                        # 优先找"每日30首"，其次"猜你喜欢"
                        if card.get('title') == '每日30首' and card.get('id'):
                            target_id = card.get('id')
                            break
                        elif card.get('title') == '猜你喜欢' and card.get('id') and not target_id:
                            target_id = card.get('id')

                    if target_id:
                        break

                if target_id:
                    break

            if not target_id:
                return []

            # 用 ID 获取歌单详情
            playlist_result = self.client.get_playlist(str(target_id))

            if not playlist_result:
                return []

            # 提取歌曲列表
            songs = playlist_result.get('songlist', []) or playlist_result.get('songs', [])

            return songs

        except Exception as e:
            logger.error(f"Get home feed failed: {e}", exc_info=True)
            return []

    def get_guess_recommend(self) -> List[Dict[str, Any]]:
        """
        获取猜你喜欢推荐数据.

        Returns:
            推荐列表
        """
        try:
            result = self.client.get_guess_recommend()
            if not result:
                return []
            if isinstance(result, list):
                return result
            if isinstance(result, dict):
                # trackList is the key for guess recommend
                for key in ['trackList', 'songlist', 'songs', 'list', 'items', 'data', 'tracks']:
                    if key in result and isinstance(result[key], list):
                        return result[key]
            return []
        except Exception as e:
            logger.error(f"Get guess recommend failed: {e}", exc_info=True)
            return []

    def get_radar_recommend(self) -> List[Dict[str, Any]]:
        """
        获取雷达推荐数据.

        Returns:
            推荐列表
        """
        try:
            result = self.client.get_radar_recommend()
            if not result:
                return []
            if isinstance(result, list):
                return result
            if isinstance(result, dict):
                # VecSongs is the key for radar recommend (capitalized)
                for key in ['VecSongs', 'songlist', 'songs', 'list', 'items', 'trackList', 'data', 'tracks']:
                    if key in result and isinstance(result[key], list):
                        return result[key]
            return []
        except Exception as e:
            logger.error(f"Get radar recommend failed: {e}", exc_info=True)
            return []

    def get_recommend_songlist(self) -> List[Dict[str, Any]]:
        """
        获取推荐歌单数据.

        Returns:
            推荐歌单列表
        """
        try:
            result = self.client.get_recommend_songlist()
            if not result:
                return []
            if isinstance(result, list):
                return result
            if isinstance(result, dict):
                # List is the key for recommend songlist (capitalized)
                for key in ['List', 'songlist', 'songs', 'list', 'items', 'data']:
                    if key in result and isinstance(result[key], list):
                        return result[key]
            return []
        except Exception as e:
            logger.error(f"Get recommend songlist failed: {e}", exc_info=True)
            return []

    def get_recommend_newsong(self) -> List[Dict[str, Any]]:
        """
        获取推荐新歌数据.

        Returns:
            推荐新歌列表
        """
        try:
            result = self.client.get_recommend_newsong()
            if not result:
                return []
            if isinstance(result, list):
                return result
            if isinstance(result, dict):
                # songlist is the key for new songs
                for key in ['songlist', 'songs', 'list', 'items', 'data']:
                    if key in result and isinstance(result[key], list):
                        return result[key]
            return []
        except Exception as e:
            logger.error(f"Get recommend newsong failed: {e}", exc_info=True)
            return []
