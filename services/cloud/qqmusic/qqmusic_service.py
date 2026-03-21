"""
QQ Music service for Harmony music player.
Provides high-level interface for QQ Music integration.
"""

import asyncio
import json
import logging
import time
from typing import Optional, Dict, List, Any, TYPE_CHECKING

from .client import QQMusicClient

if TYPE_CHECKING:
    from system.config import ConfigManager

logger = logging.getLogger(__name__)


class QQMusicService:
    """
    Service for QQ Music integration.
    """

    def __init__(self, credential: Optional[Dict[str, Any]] = None):
        """
        Initialize QQ Music service.

        Args:
            credential: Optional credential dict with musicid, musickey, login_type
        """
        self.client = QQMusicClient(credential)
        self._credential = credential

    @property
    def credential(self) -> Optional[Dict[str, Any]]:
        """Get current credential."""
        return self._credential

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
            from qqmusic_api.login import Credential

            # Create Credential object from stored data
            cred = Credential(
                musicid=int(self._credential.get('musicid', 0) or 0),
                musickey=self._credential.get('musickey', ''),
                login_type=self._credential.get('login_type') or self._credential.get('loginType', 2),
                openid=self._credential.get('openid', ''),
                refresh_token=self._credential.get('refresh_token', ''),
                access_token=self._credential.get('access_token', ''),
                expired_at=self._credential.get('expired_at', 0),
                unionid=self._credential.get('unionid', ''),
                str_musicid=self._credential.get('str_musicid', ''),
                refresh_key=self._credential.get('refresh_key', ''),
                encrypt_uin=self._credential.get('encrypt_uin') or self._credential.get('encryptUin', ''),
                extra_fields=self._credential.get('extra_fields', ''),
            )

            # Check if can refresh
            can_refresh = await cred.can_refresh()
            if not can_refresh:
                logger.warning("Credential cannot be refreshed")
                return None

            # Perform refresh
            await cred.refresh()

            # Extract new credential data
            new_credential = {}
            for attr in ['musicid', 'musickey', 'login_type', 'openid',
                         'refresh_token', 'access_token', 'expired_at',
                         'unionid', 'str_musicid', 'refresh_key',
                         'encrypt_uin']:
                if hasattr(cred, attr):
                    value = getattr(cred, attr)
                    if attr == 'musicid':
                        new_credential[attr] = str(value) if value else ''
                    else:
                        new_credential[attr] = value

            # Merge extra_fields into main dict (contains musickeyCreateTime, keyExpiresIn, etc.)
            if hasattr(cred, 'extra_fields') and isinstance(cred.extra_fields, dict):
                new_credential.update(cred.extra_fields)
                # Map API field names to our storage format
                if 'keyExpiresIn' in new_credential:
                    new_credential['key_expires_in'] = new_credential['keyExpiresIn']
                if 'musickeyCreateTime' in new_credential:
                    new_credential['musickey_createtime'] = new_credential['musickeyCreateTime']

            # Add create time for refresh tracking
            new_credential['musickey_createtime'] = int(time.time())

            logger.info(f"Credential refreshed successfully, new expired_at: {new_credential.get('expired_at')}")
            return new_credential

        except ImportError:
            logger.error("qqmusic_api library not installed for credential refresh")
            return None
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

            if not result or 'body' not in result:
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

    def get_playback_url(self, song_mid: str, quality: str = 'flac') -> Optional[str]:
        """
        Get playback URL for a song.

        Args:
            song_mid: Song MID
            quality: Audio quality (master/atmos/flac/320/128)

        Returns:
            Playback URL or None if failed
        """
        try:
            result = self.client.get_song_url(song_mid, quality=quality)

            urls = result.get('urls', {})

            # Return first valid URL
            for mid, url in urls.items():
                if url:
                    return url

            return None

        except Exception as e:
            logger.error(f"Get playback URL failed: {e}", exc_info=True)
            return None

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
        from services.online.adapter import OnlineMusicAdapter

        try:
            # Get album basic info
            basic_result = self.client.get_album(album_mid)

            if not basic_result:
                logger.warning(f"Album {album_mid} returned empty result")
                return None

            # Get album songs
            songs_result = self.client.get_album_songs(album_mid)

            # Use adapter to parse
            result = OnlineMusicAdapter.parse_album_detail(basic_result, songs_result)

            if not result:
                return None

            # Pagination
            songs = result.get('songs', [])
            total_songs = result.get('total', len(songs))
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size

            result['songs'] = songs[start_idx:end_idx]
            result['total'] = total_songs
            result['page'] = page
            result['page_size'] = page_size

            return result

        except Exception as e:
            logger.error(f"Get album info failed: {e}", exc_info=True)
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

            logger.debug(f"Playlist result keys: {result.keys()}")
            logger.debug(f"Playlist result: title={result.get('title')}, dissname={result.get('dissname')}, name={result.get('name')}")

            # Parse response - new API format
            all_songs = result.get('songlist', []) or result.get('songs', []) or result.get('data', {}).get('song', []) or []
            total_songs = len(all_songs)

            logger.info(f"Playlist {playlist_id} has {total_songs} songs")

            # Pagination
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            songs = all_songs[start_idx:end_idx]

            # Get playlist name - try multiple fields
            name = result.get('dissname', '') or result.get('title', '') or result.get('name', '')

            # Get creator - try multiple fields
            creator = ''
            creator_data = result.get('creator', {})
            if isinstance(creator_data, dict):
                creator = creator_data.get('name', '') or creator_data.get('nick', '')
            elif isinstance(creator_data, str):
                creator = creator_data
            if not creator:
                creator = result.get('nick', '') or result.get('nickname', '')

            return {
                'id': result.get('tid', '') or result.get('dissid', '') or str(playlist_id),
                'name': name,
                'creator': creator,
                'cover': result.get('logo', '') or result.get('cover', ''),
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
            avatar = pic_info.get('pic') or pic_info.get('big') or pic_info.get('big_black') or pic_info.get('big_white') or ''
            # If no avatar in pic, construct from singer_mid
            if not avatar:
                singer_mid = basic_info.get('singer_mid', '')
                has_photo = basic_info.get('has_photo', 0)
                if has_photo and singer_mid:
                    avatar = f"http://y.gtimg.cn/music/photo_new/T001R300x300M000{singer_mid}_{has_photo}.jpg"

            # Get singer name and search for their songs
            singer_name = basic_info.get('name', '')
            songs = []
            total_songs = 0

            if singer_name:
                # Get requested page
                search_results = self.client.search(singer_name, search_type='song', page_num=page, page_size=page_size)

                # Get total count from meta
                if search_results and 'meta' in search_results:
                    meta = search_results['meta']
                    total_songs = meta.get('sum', 0)  # Total search results for this singer
                    logger.info(f"Total songs for {singer_name}: {total_songs}")

                # Parse and filter songs from this page
                if search_results and 'body' in search_results:
                    item_song = search_results['body'].get('item_song', [])
                    for song in item_song:
                        # Search API returns 'mid' and 'name' (NOT 'songmid' and 'songname')
                        songmid = song.get('mid', '')
                        songname = song.get('name', '') or song.get('title_main', '') or song.get('title', '')
                        songid = song.get('id')

                        # Check if this song is by the singer
                        singer_info = song.get('singer', {})
                        song_singers = []
                        if isinstance(singer_info, list):
                            song_singers = [s.get('name', '') for s in singer_info]
                        elif isinstance(singer_info, dict):
                            song_singers = [singer_info.get('name', '')]

                        # Include if singer name matches
                        if singer_name in song_singers:
                            # Build album info
                            album_data = song.get('album', {})
                            if isinstance(album_data, dict):
                                albummid = album_data.get('mid', '')
                                albumname = album_data.get('name', '')
                            else:
                                albummid = song.get('albummid', '')
                                albumname = song.get('albumname', '')

                            # Build singer list
                            singer_list = []
                            if isinstance(singer_info, list):
                                for s in singer_info:
                                    singer_list.append({
                                        'mid': s.get('mid', ''),
                                        'name': s.get('name', '')
                                    })
                            elif isinstance(singer_info, dict):
                                singer_list.append({
                                    'mid': singer_info.get('mid', ''),
                                    'name': singer_info.get('name', '')
                                })

                            songs.append({
                                'mid': songmid or '',  # Use empty string if no mid
                                'songmid': songmid or '',
                                'id': songid,
                                'name': songname or '',
                                'title': songname or '',
                                'singer': singer_list,
                                'album': {
                                    'mid': albummid,
                                    'name': albumname
                                },
                                'albummid': albummid,
                                'albumname': albumname,
                                'interval': song.get('interval', 0),
                            })

                logger.info(f"Page {page}: Got {len(songs)} songs for {singer_name}")

            return {
                'mid': basic_info.get('singer_mid', singer_mid),
                'name': singer_name,
                'desc': ex_info.get('desc', ''),
                'avatar': avatar,
                'songs': songs,
                'total': total_songs,  # Total song count
                'page': page,
                'page_size': page_size,
            }

        except Exception as e:
            logger.error(f"Get singer info failed: {e}", exc_info=True)
            return None

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
            top_lists = []

            for group in groups:
                for top_list in group.get('toplist', []):
                    top_lists.append({
                        'id': top_list.get('topId', ''),
                        'title': top_list.get('title', ''),
                        'type': top_list.get('type', 0),
                    })

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
            # - result.song (some APIs)
            # - result.data.song (unsigned endpoint)
            # - result.list (signed endpoint)
            songs = result.get('song', [])
            if not songs:
                inner_data = result.get('data', {})
                if isinstance(inner_data, dict):
                    songs = inner_data.get('song', [])
            if not songs:
                songs = result.get('list', [])

            logger.debug(f"get_top_list_songs: top_id={top_id}, found {len(songs)} songs")

            # If songs don't have mid, query by id to get mid
            songs_need_mid = [s for s in songs if not s.get('songmid') and not s.get('mid') and s.get('songId')]
            if songs_need_mid:
                song_ids = [s['songId'] for s in songs_need_mid]
                logger.debug(f"Querying mids for {len(song_ids)} songs")
                track_infos = self.client.query_songs_by_ids(song_ids)
                # Create a map from id to track info
                id_to_track = {t.get('id'): t for t in track_infos}
                for song in songs_need_mid:
                    track_info = id_to_track.get(song.get('songId'))
                    if track_info:
                        song['songmid'] = track_info.get('mid', '')

            tracks = []

            for song in songs:
                # Handle singer data - can be singerName (string) or singer (list/dict)
                singer_info = song.get('singer', song.get('singerName', ''))
                if isinstance(singer_info, str):
                    singer_name = singer_info
                elif isinstance(singer_info, list) and singer_info:
                    singer_name = singer_info[0].get('name', '')
                elif isinstance(singer_info, dict):
                    singer_name = singer_info.get('name', '')
                else:
                    singer_name = ''

                # Handle album data - can be albumName (string) or album (dict)
                album_info = song.get('album', {})
                if isinstance(album_info, str):
                    album_name = album_info
                elif isinstance(album_info, dict):
                    album_name = album_info.get('name', '')
                else:
                    album_name = song.get('albumName', '')

                track = {
                    'mid': song.get('songmid', '') or song.get('mid', ''),
                    'title': song.get('songname', '') or song.get('title', ''),
                    'singer': singer_name,
                    'album': album_name,
                    'duration': song.get('interval', 0),
                }
                tracks.append(track)

            return tracks

        except Exception as e:
            logger.error(f"Get top list songs failed: {e}", exc_info=True)
            return []

    def set_credential(self, credential: Dict[str, Any]):
        """
        Update credential for authenticated requests.

        Args:
            credential: Credential dict with musicid, musickey, login_type
        """
        self._credential = credential
        self.client.credential = credential
        self.client._set_credential_headers()
