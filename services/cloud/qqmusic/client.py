"""
QQ Music API client.
Handles direct communication with QQ Music servers.
"""

import json
import logging
import time
from typing import Dict, List, Optional, Any, TYPE_CHECKING

import requests

from .crypto import generate_sign
from .common import (
    APIConfig, get_guid, get_search_id, parse_quality, SongFileType,
    SearchType, parse_search_type
)

if TYPE_CHECKING:
    from system.config import ConfigManager

logger = logging.getLogger(__name__)


class QQMusicClient:
    """
    Client for QQ Music API.
    """

    def __init__(self, credential: Optional[Dict[str, Any]] = None,
                 on_credential_updated: Optional[callable] = None):
        """
        Initialize QQ Music client.

        Args:
            credential: Optional credential dict with musicid, musickey, login_type
            on_credential_updated: Optional callback when credential is refreshed
        """
        self.credential = credential
        self._on_credential_updated = on_credential_updated
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://y.qq.com/',
            'Origin': 'https://y.qq.com',
            'Content-Type': 'application/json',
        })

        if credential:
            self._set_credential_headers()

    def _set_credential_headers(self):
        """Set credential-related headers and cookies."""
        if not self.credential:
            return

        # Set cookie
        cookies = [
            f"uin={self.credential.get('musicid', '')}",
            f"qqmusic_key={self.credential.get('musickey', '')}",
            f"qm_keyst={self.credential.get('musickey', '')}",
            f"tmeLoginType={self.credential.get('login_type') or self.credential.get('loginType', 2)}",
        ]
        self.session.headers['Cookie'] = '; '.join(cookies)

    def needs_refresh(self) -> bool:
        """
        Check if credential needs refresh.

        Returns:
            True if credential needs refresh, False otherwise
        """
        if not self.credential:
            return False

        # Check if we have refresh capability
        if not self.credential.get('refresh_key') or not self.credential.get('refresh_token'):
            return False

        # Check expiration
        create_time = self.credential.get('musickey_createtime') or self.credential.get('musickeyCreateTime', 0)
        expires_in = self.credential.get('key_expires_in') or self.credential.get('keyExpiresIn', 259200)  # Default 3 days

        if not create_time:
            return False

        # Refresh if less than 48 hours remaining
        remaining = (create_time + expires_in) - time.time()
        return remaining < 48 * 3600

    def refresh_credential(self) -> Optional[Dict[str, Any]]:
        """
        Refresh credential using refresh_key and refresh_token.

        Returns:
            Updated credential dict or None if refresh failed
        """
        if not self.credential:
            logger.warning("No credential to refresh")
            return None

        refresh_key = self.credential.get('refresh_key')
        refresh_token = self.credential.get('refresh_token')

        if not refresh_key or not refresh_token:
            logger.warning("Missing refresh_key or refresh_token")
            return None

        logger.info("Attempting to refresh QQ Music credential...")

        # Build refresh request
        params = {
            'refresh_key': refresh_key,
            'refresh_token': refresh_token,
            'musickey': self.credential.get('musickey', ''),
            'musicid': int(self.credential.get('musicid', 0) or 0),
        }

        # Build common params with login_type
        common = self._build_common_params()
        common['tmeLoginType'] = str(self.credential.get('login_type', 2))

        request_data = {
            'comm': common,
            'music.login.LoginServer.Login': {
                'module': 'music.login.LoginServer',
                'method': 'Login',
                'param': params,
            }
        }

        try:
            # Use same JSON serialization for both sign and request body
            json_str = json.dumps(request_data, separators=(',', ':'), ensure_ascii=False)
            signature = generate_sign(request_data)
            url = f"{APIConfig.ENDPOINT}?sign={signature}"

            response = self.session.post(
                url,
                data=json_str.encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            response.raise_for_status()

            data = response.json()
            result = data.get('music.login.LoginServer.Login')

            if not result or result.get('code') != 0:
                code = result.get('code') if result else -1
                error_msgs = {
                    10006: "refresh_token invalid or expired",
                    1000: "credential expired",
                    2000: "invalid signature",
                }
                msg = error_msgs.get(code, f"unknown error code {code}")
                logger.error(f"Credential refresh failed: {msg}")
                return None

            # Extract new credential data
            new_data = result.get('data', {})
            if not new_data:
                logger.error("No data in refresh response")
                return None

            # Update credential
            now = int(time.time())
            updated = {
                **self.credential,
                'musickey': new_data.get('musickey', self.credential.get('musickey')),
                'musicid': new_data.get('musicid', self.credential.get('musicid')),
                'refresh_key': new_data.get('refresh_key', refresh_key),
                'refresh_token': new_data.get('refresh_token', refresh_token),
                'musickey_createtime': now,
                'key_expires_in': new_data.get('keyExpiresIn', 259200),
            }

            # Update internal credential
            self.credential = updated
            self._set_credential_headers()

            # Notify callback if set
            if self._on_credential_updated:
                try:
                    self._on_credential_updated(updated)
                except Exception as e:
                    logger.warning(f"Credential update callback failed: {e}")

            logger.info(f"Credential refreshed successfully, valid for {updated['key_expires_in'] // 3600} hours")
            return updated

        except Exception as e:
            logger.error(f"Failed to refresh credential: {e}")
            return None

    def _build_common_params(self) -> Dict[str, Any]:
        """Build common request parameters."""
        params = {
            'cv': APIConfig.VERSION_CODE,
            'v': APIConfig.VERSION_CODE,
            'QIMEI36': '8888888888888888',
            'ct': '11',
            'tmeAppID': 'qqmusic',
            'format': 'json',
            'inCharset': 'utf-8',
            'outCharset': 'utf-8',
            'uid': '3931641530',
        }

        if self.credential:
            params['qq'] = str(self.credential.get('musicid', ''))
            params['authst'] = self.credential.get('musickey', '')
            params['tmeLoginType'] = str(self.credential.get('login_type', 2))

        return params

    def _make_request(self, module: str, method: str, params: Dict, _retry: bool = False) -> Dict:
        """
        Make API request.

        Args:
            module: Module name
            method: Method name
            params: Request parameters
            _retry: Internal flag to prevent infinite retry loop

        Returns:
            Response data
        """
        common = self._build_common_params()

        request_data = {
            'comm': common,
            f'{module}.{method}': {
                'module': module,
                'method': method,
                'param': params,
            }
        }

        # Use same JSON serialization for both sign and request body
        json_str = json.dumps(request_data, separators=(',', ':'), ensure_ascii=False)
        signature = generate_sign(request_data)
        url = f"{APIConfig.ENDPOINT}?sign={signature}"

        response = self.session.post(
            url,
            data=json_str.encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        response.raise_for_status()

        data = response.json()
        result_key = f'{module}.{method}'

        if result_key not in data:
            raise ValueError(f"Invalid response: missing {result_key}")

        result = data[result_key]

        if result.get('code') != 0:
            code = result.get('code')
            # Code 2000 = need login - try refresh if possible
            if code == 2000:
                if not _retry and self._try_refresh_credential():
                    # Retry with new credential
                    return self._make_request(module, method, params, _retry=True)
                logger.debug("QQ Music API requires login credential")
            else:
                logger.error(f"API error: {code}")
            return {}

        return result.get('data', result)

    def _try_refresh_credential(self) -> bool:
        """
        Try to refresh credential if refresh_key and refresh_token are available.

        Returns:
            True if refresh was successful, False otherwise
        """
        if not self.credential:
            return False

        refresh_key = self.credential.get('refresh_key')
        refresh_token = self.credential.get('refresh_token')

        if not refresh_key or not refresh_token:
            logger.debug("No refresh capability (missing refresh_key or refresh_token)")
            return False

        logger.info("Credential expired, attempting refresh...")
        return self.refresh_credential() is not None

    def search(self, keyword: str, search_type: str = 'song',
               page_num: int = 1, page_size: int = 20) -> Dict:
        """
        Search for songs, artists, albums, or playlists.

        Args:
            keyword: Search keyword
            search_type: Type of search (song/singer/album/playlist)
            page_num: Page number (1-based)
            page_size: Number of results per page

        Returns:
            Search results dictionary
        """
        search_type_enum = parse_search_type(search_type)

        params = {
            'searchid': get_search_id(),
            'query': keyword,
            'search_type': search_type_enum.value,
            'num_per_page': page_size,
            'page_num': page_num,
            'highlight': 1,
            'grp': 1,
        }

        return self._make_request('music.search.SearchCgiService', 'DoSearchForQQMusicMobile', params)

    def get_song_url(self, song_mid: str, quality: str = 'flac') -> Dict:
        """
        Get playback URL for a song.

        Args:
            song_mid: Song MID (can be comma-separated for multiple songs)
            quality: Audio quality (master/atmos/flac/320/128)

        Returns:
            Dictionary with song URLs
        """
        # Support comma-separated MIDs
        mids = [m.strip() for m in song_mid.split(',') if m.strip()]

        if not mids:
            return {}

        # Try quality fallback
        for q in APIConfig.QUALITY_FALLBACK:
            if APIConfig.QUALITY_FALLBACK.index(q) < APIConfig.QUALITY_FALLBACK.index(quality):
                continue

            file_type = parse_quality(q)
            domain = "https://isure.stream.qqmusic.qq.com/"

            file_names = [f"{file_type['s']}{mid}{mid}{file_type['e']}" for mid in mids]

            params = {
                'filename': file_names,
                'guid': get_guid(),
                'songmid': mids,
                'songtype': [0] * len(mids),
            }

            result = self._make_request('music.vkey.GetVkey', 'UrlGetVkey', params)

            if result and result.get('midurlinfo'):
                urls = {}
                has_valid = False

                for info in result['midurlinfo']:
                    purl = info.get('purl') or info.get('wifiurl', '')
                    if purl:
                        urls[info['songmid']] = domain + purl
                        has_valid = True
                    else:
                        urls[info['songmid']] = ''

                if has_valid:
                    return {'urls': urls, 'quality': q}

        return {'urls': {}, 'quality': None}

    def get_song_detail(self, song_mid: str) -> Dict:
        """
        Get detailed information about a song.

        Args:
            song_mid: Song MID

        Returns:
            Song detail dictionary
        """
        params = {
            'song_mid': song_mid,
        }

        return self._make_request('music.songInfo.SongInfoService', 'GetSongDetail', params)

    def get_lyric(self, song_mid: str, qrc: bool = True,
                  trans: bool = False, roma: bool = False) -> Dict:
        """
        Get lyrics for a song.

        Args:
            song_mid: Song MID
            qrc: Include word-by-word lyrics (QRC)
            trans: Include translation
            roma: Include romanization

        Returns:
            Lyrics dictionary
        """
        params = {
            'song_mid': song_mid,
        }

        result = self._make_request('music.lyric.GetLyric', 'GetLyric', params)

        # Parse lyric content
        if not result:
            return {}

        lyric_data = {}

        # Regular lyrics
        if 'lyric' in result:
            lyric_data['lyric'] = result['lyric']

        # QRC (word-by-word) lyrics
        if qrc and 'qrc' in result:
            from .crypto import qrc_decrypt
            lyric_data['qrc'] = qrc_decrypt(result['qrc'])

        # Translation
        if trans and 'trans' in result:
            lyric_data['trans'] = result['trans']

        # Romanization
        if roma and 'roma' in result:
            from .crypto import qrc_decrypt
            lyric_data['roma'] = qrc_decrypt(result['roma'])

        return lyric_data

    def get_album(self, album_mid: str) -> Dict:
        """
        Get album information.

        Args:
            album_mid: Album MID

        Returns:
            Album detail dictionary
        """
        params = {
            'album_mid': album_mid,
        }

        return self._make_request('music.album.AlbumInfoService', 'GetAlbumDetail', params)

    def get_playlist(self, playlist_id: str) -> Dict:
        """
        Get playlist information.

        Args:
            playlist_id: Playlist ID

        Returns:
            Playlist detail dictionary
        """
        params = {
            'playlist_id': playlist_id,
        }

        return self._make_request('music.playlist.PlaylistInfoService', 'GetPlaylistDetail', params)

    def get_singer(self, singer_mid: str) -> Dict:
        """
        Get singer information.

        Args:
            singer_mid: Singer MID

        Returns:
            Singer detail dictionary
        """
        params = {
            'singer_mid': singer_mid,
        }

        return self._make_request('music.singer.SingerInfoService', 'GetSingerDetail', params)

    def get_top_lists(self) -> Dict:
        """
        Get music top lists.

        Returns:
            Top lists dictionary
        """
        params = {}

        return self._make_request('music.topList.TopListInfoService', 'GetTopList', params)

    def verify_login(self) -> Dict[str, Any]:
        """
        Verify if current credential is valid by calling profile API.

        Returns:
            Dict with keys:
                - valid: bool - whether login is valid
                - nick: str - nickname if valid
                - uin: int - user ID if valid
        """
        result = {
            'valid': False,
            'nick': '',
            'uin': 0,
        }

        if not self.credential:
            return result

        try:
            musicid = self.credential.get('musicid', '')

            # Use profile homepage API to verify login
            url = 'https://c6.y.qq.com/rsc/fcgi-bin/fcg_get_profile_homepage.fcg'

            # Build cookies from credential
            cookies = {
                'uin': str(musicid),
                'qqmusic_key': self.credential.get('musickey', ''),
                'qm_keyst': self.credential.get('musickey', ''),
                'tmeLoginType': str(self.credential.get('login_type', 2)),
            }

            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
                'Referer': 'https://y.qq.com/',
            }

            params = {
                'format': 'json',
                'uin': musicid,
                'cid': '205360838',
                'reqfrom': '1',
                'reqtype': '0',
            }

            response = self.session.get(
                url,
                params=params,
                cookies=cookies,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()

            data = response.json()

            if data.get('code') == 0:
                creator = data.get('data', {}).get('creator', {})
                if creator:
                    result['valid'] = True
                    result['nick'] = creator.get('nick', '')
                    result['uin'] = creator.get('uin', 0)

            return result

        except Exception as e:
            logger.error(f"Failed to verify login: {e}")
            return result
