"""
Baidu Drive cloud storage service.
"""
import logging
import threading
import traceback
import time
import re
from typing import Optional, Dict, List
from urllib.parse import quote

import requests

from domain import CloudFile

# Configure logging
logger = logging.getLogger(__name__)

# Rate limiting (thread-safe)
_last_request_time = 0
_request_interval = 0.2  # 200ms between requests
_rate_limit_lock = threading.Lock()


def _rate_limit():
    """Simple rate limiting for Baidu API (thread-safe)."""
    global _last_request_time
    with _rate_limit_lock:
        elapsed = time.time() - _last_request_time
        if elapsed < _request_interval:
            time.sleep(_request_interval - elapsed)
        _last_request_time = time.time()


# Error codes
BAIDU_ERRNO = {
    0: '成功',
    -6: '未登录或登录已过期',
    -7: '权限不足',
    111: '需要验证码',
    112: '页面已过期',
    113: '签名错误',
    310: '参数错误',
    404: '文件不存在',
    9013: '文件列表为空',
}


class BaiduDriveService:
    """Service for Baidu Drive cloud storage integration"""

    # Class-level session for connection pooling
    _session = None

    @classmethod
    def _get_session(cls):
        """Get or create the shared session for connection pooling."""
        if cls._session is None:
            cls._session = requests.Session()
        return cls._session

    BASE_URL = "https://pan.baidu.com"
    PASSPORT_URL = "https://passport.baidu.com"

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
        'Referer': 'https://pan.baidu.com/',
        'Accept': 'application/json, text/plain, */*',
    }

    @classmethod
    def _get_errmsg(cls, errno: int) -> str:
        """Get error message for errno."""
        return BAIDU_ERRNO.get(errno, f'未知错误 ({errno})')

    @classmethod
    def generate_qr_code(cls) -> Optional[Dict[str, str]]:
        """Generate QR code for login"""
        try:
            url = f"{cls.PASSPORT_URL}/v2/api/getqrcode"
            params = {
                'lp': 'pc',
                'tpl': 'netdisk',
                'apiver': 'v3',
                'tt': int(time.time() * 1000),
            }

            response = cls._get_session().get(url, params=params, headers=cls.HEADERS, timeout=10)

            # Check if response is valid
            if not response.text:
                logger.error("Baidu QR code generation: empty response")
                return None

            data = response.json()

            # Baidu returns 0 for success
            if data.get('errno') == 0 or 'sign' in data:
                sign = data.get('sign', '')
                imgurl = data.get('imgurl', '')
                # QR code URL - use the imgurl directly or construct it
                qr_url = imgurl if imgurl else f"{cls.PASSPORT_URL}/v2/api/qrcode?sign={sign}"
                return {
                    'sign': sign,
                    'qr_url': qr_url,
                    'imgurl': imgurl
                }
            else:
                logger.error(f"Baidu QR code generation failed: {data}")
        except Exception as e:
            logger.error(f"Baidu QR generation error: {e}", exc_info=True)
        return None

    @classmethod
    def poll_login_status(cls, sign: str, max_attempts: int = 60,
                          poll_interval: int = 2) -> Optional[Dict[str, str]]:
        """Poll for login status after QR scan"""
        for attempt in range(max_attempts):
            try:
                # Poll unicast channel
                url = f"{cls.PASSPORT_URL}/channel/unicast"
                params = {
                    'channel_id': sign,
                    'tpl': 'netdisk',
                    'callback': ''
                }

                response = cls._get_session().get(url, params=params, headers=cls.HEADERS, timeout=10)

                if not response.text:
                    return {'status': 'waiting', 'message': 'Waiting for scan'}

                data = response.json()
                errno = data.get('errno', -1)

                if errno == 0:
                    # Login confirmed, get BDUSS
                    return cls._get_bduss_from_login(sign)
                elif errno == 50000001:
                    # Not scanned yet
                    return {'status': 'waiting', 'message': 'Waiting for scan'}
                elif errno == 50000002:
                    # QR expired
                    return {'status': 'expired', 'message': 'QR code expired'}
                else:
                    logger.debug(f"Baidu poll status: {errno}")
                    return {'status': 'waiting', 'message': f'Status: {errno}'}

            except Exception as e:
                logger.debug(f"Baidu poll error: {e}")

            time.sleep(poll_interval)

        return {'status': 'timeout', 'message': 'Login timeout'}

    @classmethod
    def _get_bduss_from_login(cls, sign: str) -> Optional[Dict[str, str]]:
        """Complete login and extract BDUSS cookie"""
        try:
            url = f"{cls.PASSPORT_URL}/v3/login/main/qrbdusslogin"
            params = {
                'sign': sign,
                'tpl': 'netdisk',
                'u': 'https://pan.baidu.com/disk/main',
                'isvoice': '0',
                'callback': ''
            }

            response = cls._get_session().get(url, params=params, headers=cls.HEADERS,
                                    timeout=10, allow_redirects=True)

            # Extract cookies from both the response and the redirect chain
            bduss = ''
            stoken = ''

            # Try to get from response cookies
            cookies = response.cookies
            bduss = cookies.get('BDUSS', '')
            stoken = cookies.get('STOKEN', '')

            # If not found, try to extract from Set-Cookie headers
            if not bduss:
                for hist_response in response.history + [response]:
                    set_cookie = hist_response.headers.get('Set-Cookie', '')
                    if 'BDUSS=' in set_cookie:
                        # Parse BDUSS from Set-Cookie header
                        match = re.search(r'BDUSS=([^;]+)', set_cookie)
                        if match:
                            bduss = match.group(1)
                    if 'STOKEN=' in set_cookie:
                        match = re.search(r'STOKEN=([^;]+)', set_cookie)
                        if match:
                            stoken = match.group(1)
                    # Also check cookies
                    if not bduss:
                        bduss = hist_response.cookies.get('BDUSS', '')
                    if not stoken:
                        stoken = hist_response.cookies.get('STOKEN', '')

            if bduss:
                cookie_str = f"BDUSS={bduss}"
                if stoken:
                    cookie_str += f"; STOKEN={stoken}"

                # Try to get username, but it's ok if we can't
                username = 'Baidu User'
                try:
                    account_info, _ = cls.get_account_info(cookie_str, '')
                    if account_info and account_info.get('nickname'):
                        username = account_info['nickname']
                except Exception:
                    pass

                return {
                    'account_email': username,
                    'access_token': cookie_str,
                    'status': 'success'
                }
            else:
                logger.error("Baidu login: BDUSS not found in response")

        except Exception as e:
            logger.error(f"Baidu get BDUSS error: {e}", exc_info=True)
        return None

    @classmethod
    def get_file_list(cls, access_token: str, dir: str = '/') -> tuple:
        """Get list of files and folders in directory.

        Returns:
            tuple: (files_list, updated_access_token or None)
        """
        try:
            _rate_limit()
            if dir == '0':
                dir = '/'

            # Use xpan API - stable and only needs BDUSS + STOKEN
            url = f"{cls.BASE_URL}/rest/2.0/xpan/file"
            params = {
                'method': 'list',
                'dir': dir,
                'start': 0,
                'limit': 100,
                'web': 1,
                'app_id': 250528,
            }

            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
                'Referer': 'https://pan.baidu.com/',
                'Origin': 'https://pan.baidu.com',
            }

            headers['Cookie'] = access_token

            response = cls._get_session().get(url, params=params, headers=headers, timeout=30)

            if not response.text:
                logger.error("Baidu file list: empty response")
                return [], None

            data = response.json()

            # xpan API uses errno in different ways
            errno = data.get('errno', 0)

            # Handle error codes
            if errno == -6:
                logger.error("Baidu file list: 登录已过期，请重新登录")
                return [], None
            elif errno != 0:
                logger.error(f"Baidu file list error: {cls._get_errmsg(errno)}")
                return [], None

            raw_list = data.get('list', [])
            files = []

            for item in raw_list:
                # Use server_filename first, fallback to path
                filename = item.get('server_filename', '')
                if not filename:
                    path = item.get('path', '')
                    filename = path.split('/')[-1] if path else ''

                is_dir = item.get('isdir', 0) == 1
                size = item.get('size', 0)
                fs_id = str(item.get('fs_id', ''))
                category = item.get('category', 0)  # 2 = audio

                # Determine file type
                if is_dir:
                    file_type = 'folder'
                elif category == 2:  # Audio
                    file_type = 'audio'
                else:
                    # Check by extension
                    ext = filename.lower().split('.')[-1] if '.' in filename else ''
                    if ext in ('mp3', 'flac', 'wav', 'm4a', 'aac', 'ogg', 'wma', 'ape'):
                        file_type = 'audio'
                    else:
                        file_type = 'other'

                cloud_file = CloudFile(
                    file_id=fs_id,
                    parent_id=dir,
                    name=filename,
                    file_type=file_type,
                    size=size if not is_dir else None,
                )
                # Store full path in metadata for download (mediainfo API needs path)
                path = item.get('path', '')
                cloud_file.metadata = path
                files.append(cloud_file)

            return files, None

        except Exception as e:
            logger.error(f"Baidu file list error: {e}", exc_info=True)
        return [], None

    @classmethod
    def get_download_url(cls, access_token: str, fs_id: str, file_path: str = None) -> tuple:
        """Get download URL for a file.

        Args:
            access_token: Cookie string
            fs_id: File ID
            file_path: File path (optional, used for mediainfo/filemetas API)

        Returns:
            tuple: (download_url or None, updated_access_token or None)
        """
        try:
            _rate_limit()

            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
                'Referer': 'https://pan.baidu.com/',
                'Origin': 'https://pan.baidu.com',
                "Cookie": access_token
            }

            if file_path and (".mp3" in file_path or ".wav" in file_path or ".m4a" in file_path):
                try:
                    media_url = f"{cls.BASE_URL}/api/mediainfo"
                    params = {
                        'type': 'VideoURL',
                        'path': file_path,
                        'fs_id': fs_id,
                        'devuid': '0%1',
                        'clienttype': '1',
                        'channel': 'android_15_25010PN30C_bd-netdisk_1523a',
                        'nom3u8': '1',
                        'dlink': '1',
                        'media': '1',
                        'origin': 'dlna',
                    }

                    response = cls._get_session().get(media_url, params=params, headers=headers, timeout=30)

                    if response.text:
                        data = response.json()
                        info = data.get('info', {})
                        dlink = info.get('dlink', '')
                        if dlink:
                            return dlink, None
                except Exception as e:
                    logger.debug(f"Mediainfo API failed: {e}")

            meta_url = f"{cls.BASE_URL}/rest/2.0/xpan/multimedia"
            params = {
                'method': 'filemetas',
                'fsids': f'[{fs_id}]',
                'dlink': 1,
                "app_id": 250528,
                "web": 1
            }

            response = cls._get_session().get(meta_url, params=params, headers=headers, timeout=30)

            if not response.text:
                logger.error("Baidu download: empty response")
                return None, None

            data = response.json()
            errno = data.get('errno', 0)

            if errno == -6:
                logger.error("Baidu download: 登录已过期，请重新登录")
                return None, None
            elif errno != 0:
                logger.error(f"Baidu download error: {cls._get_errmsg(errno)}")
                return None, None

            download_info = data.get('list', [])
            if download_info:
                dlink = download_info[0].get('dlink', '')

                if dlink:
                    # Return dlink, let download_file handle 302 redirect
                    return dlink, None
                else:
                    logger.error("No dlink in response")
            else:
                logger.error("No download info in response")

        except Exception as e:
            logger.error(f"Baidu download URL error: {e}", exc_info=True)
        return None, None

    @classmethod
    def get_account_info(cls, access_token: str, account_email: str) -> tuple:
        """Get account information including VIP status and nickname.

        Returns:
            tuple: (account_info or None, updated_access_token or None)
        """
        try:
            _rate_limit()

            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
                'Referer': 'https://pan.baidu.com/',
                'Origin': 'https://pan.baidu.com',
                'Cookie': access_token,
            }

            total = 0
            used = 0
            username = account_email
            is_vip = False
            vip_type = 0

            # Get user info via xpan nas API
            svip_type = 0
            try:
                user_url = f"{cls.BASE_URL}/rest/2.0/xpan/nas"
                params = {'method': 'uinfo'}
                user_response = cls._get_session().get(user_url, params=params, headers=headers, timeout=30)
                if user_response.status_code == 200 and user_response.text:
                    user_data = user_response.json()
                    if user_data.get('errno') == 0:
                        username = user_data.get('baidu_name', account_email)
                        vip_type = user_data.get('vip_type', 0)
                        svip_type = user_data.get('svip_type', 0)
                        is_vip = vip_type > 0 or svip_type > 0
            except Exception as e:
                logger.debug(f"Could not get Baidu user info: {e}")

            # Get quota info via api/quota
            try:
                quota_url = f"{cls.BASE_URL}/api/quota"
                params = {
                    "clienttype": 0,
                    "app_id": 250528,
                    "web": 1,
                    "channel": "chunlei"
                }
                quota_response = cls._get_session().get(quota_url, params=params, headers=headers, timeout=30)
                if quota_response.status_code == 200 and quota_response.text:
                    quota_data = quota_response.json()
                    if quota_data.get('errno') == 0:
                        total = quota_data.get('total', 0)
                        used = quota_data.get('used', 0)
            except Exception as e:
                logger.debug(f"Could not get Baidu quota info: {e}")

            # Determine member type for UI translation
            if svip_type > 0:
                member_type = 'svip'
            elif vip_type > 0:
                member_type = 'vip'
            else:
                member_type = 'normal'

            account_info = {
                'nickname': username,
                'member_type': member_type,
                'is_vip': is_vip,
                'vip_type': vip_type,
                'svip_type': svip_type,
                'total_capacity': total,
                'use_capacity': used
            }

            return account_info, None

        except Exception as e:
            logger.error(f"Get Baidu account info error: {e}", exc_info=True)
        return None, None

    @classmethod
    def validate_cookie(cls, cookie_str: str) -> Optional[Dict[str, str]]:
        """Validate cookie and get account info.

        Args:
            cookie_str: Cookie string to validate

        Returns:
            Dict with account info if valid, None if invalid
        """
        try:
            _rate_limit()

            if 'BDUSS=' not in cookie_str:
                return None

            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
                'Referer': 'https://pan.baidu.com/',
                'Origin': 'https://pan.baidu.com',
                'Cookie': cookie_str,
            }

            # Test cookie via xpan nas API
            user_url = f"{cls.BASE_URL}/rest/2.0/xpan/nas"
            params = {'method': 'uinfo'}
            response = cls._get_session().get(user_url, params=params, headers=headers, timeout=30)

            if response.status_code == 200 and response.text:
                data = response.json()
                if data.get('errno') == 0:
                    username = data.get('baidu_name', 'Baidu User')

                    return {
                        'account_email': username,
                        'access_token': cookie_str,
                        'status': 'success'
                    }

            return None
        except Exception as e:
            logger.error(f"Baidu cookie validation error: {e}", exc_info=True)
            return None

    @classmethod
    def download_file(cls, url: str, dest_path: str,
                      access_token: str = None) -> bool:
        """Download file from URL to destination.

        FLAC files need 302 redirect to get real CDN URL.
        Other formats (mp3, etc.) can be downloaded directly.
        """
        try:
            # Check if FLAC file - needs 302 redirect
            is_flac = dest_path.lower().endswith('.flac')

            if is_flac:
                # Step 1: Get real URL via 302 redirect
                headers = {
                    'User-Agent': 'netdisk',
                    'Referer': 'https://pan.baidu.com/',
                    'Cookie': access_token,
                }

                r = cls._get_session().get(url, headers=headers,
                                allow_redirects=False, timeout=10)

                real_url = r.headers.get('Location')
                if real_url:
                    url = real_url

            # Download with proper headers
            headers = {
                'User-Agent': 'netdisk',
                'Referer': 'https://pan.baidu.com/',
                'Accept-Encoding': 'identity',  # Required for audio streaming/seeking
                'Cookie': access_token,
            }

            response = cls._get_session().get(url, headers=headers, timeout=120, stream=True)

            if response.status_code == 200:
                with open(dest_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                import os
                if os.path.exists(dest_path):
                    return True
            return False
        except Exception as e:
            logger.error(f"Baidu download error: {e}", exc_info=True)
            return False
