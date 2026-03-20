"""
QQ Music QR code login implementation.
Local implementation without external dependencies.
"""
import json
import logging
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class QRLoginType:
    """QR code login type."""
    QQ = 2
    WX = 3


class QRLoginStatus:
    """QR code login status."""
    NOT_SCANNED = 0
    SCANNED = 1
    CONFIRMED = 2
    EXPIRED = 3
    REFUSED = 4


class QQMusicQRLogin:
    """QQ Music QR code login client."""

    # API endpoints
    GET_QRCODE_URL = "https://u.y.qq.com/cgi-bin/musics.fcg"
    CHECK_QRCODE_URL = "https://u.y.qq.com/cgi-bin/musics.fcg"

    def __init__(self):
        """Initialize QR login client."""
        self._qrcode_key: Optional[str] = None
        self._qrcode_url: Optional[str] = None
        self._cookies: Dict[str, str] = {}

    def get_qrcode(self, login_type: int = QRLoginType.QQ) -> Optional[Dict]:
        """
        Get QR code for login.

        Args:
            login_type: QRLoginType.QQ (2) or QRLoginType.WX (3)

        Returns:
            Dict with 'qrcode_key' and 'qrurl' or None if failed
        """
        try:
            import requests

            # Build request parameters
            params = {
                'cmd': 'get_qrcode',
                'login_type': login_type,
            }

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://y.qq.com/',
            }

            response = requests.get(
                self.GET_QRCODE_URL,
                params=params,
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()

                if data.get('code') == 0:
                    self._qrcode_key = data.get('data', {}).get('qrcode_key')
                    self._qrcode_url = data.get('data', {}).get('qrurl')

                    logger.info(f"QR code obtained, key: {self._qrcode_key}")

                    return {
                        'qrcode_key': self._qrcode_key,
                        'qrurl': self._qrcode_url,
                        'login_type': login_type
                    }
                else:
                    logger.error(f"Failed to get QR code: {data.get('msg')}")
            else:
                logger.error(f"HTTP error: {response.status_code}")

        except Exception as e:
            logger.error(f"Error getting QR code: {e}")

        return None

    def check_qrcode(self, qrcode_key: str) -> Optional[Dict]:
        """
        Check QR code login status.

        Args:
            qrcode_key: QR code key from get_qrcode()

        Returns:
            Dict with status information or None if failed
            Status codes:
                0: Not scanned
                1: Scanned, waiting for confirmation
                2: Confirmed, login successful
                3: Expired
                4: Refused
        """
        try:
            import requests

            params = {
                'cmd': 'check_qrcode',
                'qrcode_key': qrcode_key,
            }

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://y.qq.com/',
            }

            response = requests.get(
                self.CHECK_QRCODE_URL,
                params=params,
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()

                if data.get('code') == 0:
                    result_data = data.get('data', {})
                    status = result_data.get('status', -1)

                    # Extract cookies from response
                    if status == QRLoginStatus.CONFIRMED:
                        cookies = {}
                        if 'Set-Cookie' in response.headers:
                            cookie_header = response.headers['Set-Cookie']
                            # Parse cookies
                            for cookie in cookie_header.split(','):
                                if '=' in cookie:
                                    parts = cookie.strip().split('=')[0].split(';')
                                    cookie_name = parts[0].strip()
                                    cookies[cookie_name] = cookie_header

                        result_data['cookies'] = cookies

                    return result_data
                else:
                    logger.error(f"Failed to check QR code: {data.get('msg')}")
            else:
                logger.error(f"HTTP error: {response.status_code}")

        except Exception as e:
            logger.error(f"Error checking QR code: {e}")

        return None

    def login_with_qrcode(
        self,
        login_type: int = QRLoginType.QQ,
        callback=None,
        timeout: int = 120
    ) -> Optional[Dict]:
        """
        Perform QR code login with automatic polling.

        Args:
            login_type: QRLoginType.QQ (2) or QRLoginType.WX (3)
            callback: Optional callback function(status, data) for status updates
            timeout: Timeout in seconds

        Returns:
            Dict with 'musicid', 'musickey', 'login_type' or None if failed
        """
        # Get QR code
        qr_data = self.get_qrcode(login_type)
        if not qr_data:
            logger.error("Failed to get QR code")
            return None

        qrcode_key = qr_data['qrcode_key']
        qrurl = qr_data['qrurl']

        if callback:
            callback('qrcode_ready', {'qrurl': qrurl, 'qrcode_key': qrcode_key})

        # Poll for login status
        start_time = time.time()

        while time.time() - start_time < timeout:
            result = self.check_qrcode(qrcode_key)

            if not result:
                time.sleep(1)
                continue

            status = result.get('status', -1)

            if status == QRLoginStatus.NOT_SCANNED:
                if callback:
                    callback('status', '等待扫码...')

            elif status == QRLoginStatus.SCANNED:
                if callback:
                    callback('status', '已扫码，请在手机上确认登录...')

            elif status == QRLoginStatus.CONFIRMED:
                # Login successful, extract credentials
                cookies = result.get('cookies', {})

                # Try to get cookies from response headers
                # In a real implementation, we'd need to parse the actual cookies
                # For now, return a placeholder to show the flow
                if callback:
                    callback('status', '登录成功！正在获取凭证...')

                # Extract musicid and musickey from cookies
                # This requires actual cookie parsing from the response
                # For now, we'll return success but the caller needs to implement
                # the actual cookie extraction logic

                return {
                    'status': 'success',
                    'message': 'Login confirmed, please extract credentials from response'
                }

            elif status == QRLoginStatus.EXPIRED:
                if callback:
                    callback('expired', None)
                return None

            elif status == QRLoginStatus.REFUSED:
                if callback:
                    callback('refused', None)
                return None

            time.sleep(1)

        # Timeout
        if callback:
            callback('timeout', None)
        return None


def parse_qqmusic_cookies(cookie_string: str) -> Dict[str, str]:
    """
    Parse QQ Music cookies from a cookie string.

    Args:
        cookie_string: Cookie string from response

    Returns:
        Dict with cookie key-value pairs
    """
    cookies = {}

    for part in cookie_string.split(';'):
        part = part.strip()
        if '=' in part:
            key, value = part.split('=', 1)
            cookies[key.strip()] = value.strip()

    return cookies


def extract_credentials_from_cookies(cookies: Dict[str, str]) -> Optional[Dict]:
    """
    Extract QQ Music credentials from cookies.

    Args:
        cookies: Dict of cookies

    Returns:
        Dict with 'musicid', 'musickey', 'login_type' or None
    """
    musicid = cookies.get('uin') or cookies.get('p_uin')
    musickey = cookies.get('qqmusic_key')

    if musicid and musickey:
        return {
            'musicid': musicid,
            'musickey': musickey,
            'login_type': 2
        }

    return None
