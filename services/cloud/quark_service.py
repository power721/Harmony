"""
Quark Drive cloud storage service.
"""
import json
import logging
import re
import traceback

import requests

from domain import CloudFile

# Configure logging
logger = logging.getLogger(__name__)
import time
from typing import Optional, Dict, List, Tuple
from urllib.parse import parse_qs, urlparse


class QuarkDriveService:
    """Service for Quark Drive cloud storage integration"""

    BASE_URL = "https://drive-pc.quark.cn"

    @staticmethod
    def _safe_json_parse(response: requests.Response, context: str = "") -> Optional[Dict]:
        """
        Safely parse JSON from response with error handling.

        Args:
            response: HTTP response object
            context: Context string for error logging

        Returns:
            Parsed JSON dict or None if parsing failed
        """
        try:
            return response.json()
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Invalid JSON response{f' ({context})' if context else ''}: {e}")
            return None
    AUTH_URL = "https://uop.quark.cn"
    CLIENT_ID = "532"

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) quark-cloud-drive/2.5.20 Chrome/100.0.4896.160 '
                      'Electron/18.3.5.4-b478491100 Safari/537.36 Channel/pckk_other_ch',
        'Referer': 'https://pan.quark.cn/',
        'Origin': 'https://pan.quark.cn'
    }

    # Class-level session for connection pooling
    _session = None

    @classmethod
    def _get_session(cls):
        """Get or create the shared session for connection pooling."""
        if cls._session is None:
            cls._session = requests.Session()
        return cls._session

    @classmethod
    def _update_cookie_from_response(cls, access_token: str, response_cookies) -> str:
        """Update access token cookie with new __puus if present in response cookies."""
        if not response_cookies:
            return access_token

        # Extract cookies from response
        cookie_dict = {}
        for name, value in response_cookies.items():
            cookie_dict[name] = value

        # Check if __puus is in response cookies
        if '__puus' in cookie_dict:
            # Parse existing cookie string
            existing_cookies = {}
            if access_token:
                for cookie in access_token.split(';'):
                    cookie = cookie.strip()
                    if '=' in cookie:
                        name, value = cookie.split('=', 1)
                        existing_cookies[name.strip()] = value.strip()

            # Update or add __puus
            existing_cookies['__puus'] = cookie_dict['__puus']

            # Rebuild cookie string
            updated_cookie = '; '.join([f"{k}={v}" for k, v in existing_cookies.items()])
            return updated_cookie

        return access_token

    @staticmethod
    def parse_share_url(share_url: str) -> Tuple[str, str]:
        """Parse Quark share URL and return (pwd_id, passcode)."""
        if not share_url:
            return "", ""

        pwd_match = re.search(r"/s/([^/?#]+)", share_url)
        if not pwd_match:
            return "", ""

        pwd_id = pwd_match.group(1).strip()

        parsed = urlparse(share_url)
        query = parse_qs(parsed.query)
        passcode = query.get("pwd", [""])[0].strip()
        return pwd_id, passcode

    @classmethod
    def generate_qr_code(cls) -> Optional[Dict[str, str]]:
        """Generate QR code for login"""
        try:
            t = int(time.time() * 1000)
            url = f"{cls.AUTH_URL}/cas/ajax/getTokenForQrcodeLogin"
            params = {
                'client_id': cls.CLIENT_ID,
                'v': '1.2',
                'request_id': t
            }

            response = cls._get_session().get(url, params=params, timeout=10)

            data = QuarkDriveService._safe_json_parse(response, "QR code generation")
            if data is None:
                return None

            if data.get('status') == 2000000:
                token = data['data']['members']['token']
                qr_url = f"https://su.quark.cn/4_eMHBJ?token={token}&client_id={cls.CLIENT_ID}&ssb=weblogin&uc_param_str=&uc_biz_str=S%3Acustom%7COPT%3ASAREA%400%7COPT%3AIMMERSIVE%401%7COPT%3ABACK_BTN_STYLE%400"
                return {
                    'token': token,
                    'qr_url': qr_url
                }
            else:
                logger.debug(f"QR code generation failed with status: {data.get('status')}")
                logger.debug(f"Error message: {data.get('message')}")
        except Exception as e:
            logger.error(f"Quark QR generation error: {e}", exc_info=True)
            logger.debug(f"Traceback: {traceback.format_exc()}")
        return None

    @classmethod
    def poll_login_status(cls, token: str, max_attempts: int = 60,
                          poll_interval: int = 2) -> Optional[Dict[str, str]]:
        """Poll for login status after QR scan"""
        for attempt in range(max_attempts):
            try:
                t = int(time.time() * 1000)
                url = f"{cls.AUTH_URL}/cas/ajax/getServiceTicketByQrcodeToken"
                params = {
                    'client_id': cls.CLIENT_ID,
                    'v': '1.2',
                    'token': token,
                    'request_id': t
                }

                response = cls._get_session().get(url, params=params, timeout=10)
                data = QuarkDriveService._safe_json_parse(response, "login status poll")
                if data is None:
                    continue
                status = data.get('status')
                message = data.get('message', '')

                if status == 2000000:
                    # Success - extract cookie and user info
                    ticket = data['data']['members']['service_ticket']

                    # Get account info with ticket
                    info_url = f"https://pan.quark.cn/account/info"
                    info_params = {'st': ticket, 'lw': 'scan'}
                    info_response = cls._get_session().get(info_url, params=info_params, timeout=10)

                    # Extract cookies
                    cookies = info_response.cookies
                    cookie_dict = {name: value for name, value in cookies.items()}
                    cookie_str = '; '.join([f"{k}={v}" for k, v in cookie_dict.items()])

                    info_data = QuarkDriveService._safe_json_parse(info_response, "account info after login")
                    if info_data is None:
                        return {'status': 'error', 'message': 'Failed to parse account info'}

                    nickname = info_data.get('data', {}).get('nickname', 'Unknown')
                    logger.debug(f"User nickname: {nickname}")

                    return {
                        'account_email': nickname,
                        'access_token': cookie_str,
                        'status': 'success'
                    }
                elif status == 50004001:
                    # Waiting for scan - return waiting status
                    return {'status': 'waiting', 'message': message or 'Waiting for scan'}
                elif status == 50004002:
                    # QR expired
                    logger.debug("QR code expired")
                    return {'status': 'expired', 'message': message}
                else:
                    logger.debug(f"Unknown status code: {status}")
                    return {'status': 'error', 'message': message}

            except Exception as e:
                logger.error(f"Quark login poll error: {e}", exc_info=True)
                logger.debug(f"Traceback: {traceback.format_exc()}")

        return {'status': 'timeout', 'message': 'Login timeout'}

    @classmethod
    def get_file_list(cls, access_token: str, parent_id: str = '0') -> tuple:
        """Get list of files and folders in parent directory.

        Returns:
            tuple: (files_list, updated_access_token or None)
        """
        try:
            url = f"{cls.BASE_URL}/1/clouddrive/file/sort"
            params = {
                'pr': 'ucpro',
                'fr': 'pc',
                'uc_param_str': '',
                'pdir_fid': parent_id,
                '_page': '1',
                '_size': '2000',
                '_fetch_total': 'true',
                '_fetch_sub_dirs': '1',
                '_sort': 'file_type:asc,file_name:asc'
            }

            headers = cls.HEADERS.copy()
            headers['Cookie'] = access_token

            response = requests.get(url, params=params, headers=headers, timeout=30)

            # Check for updated cookies
            updated_token = cls._update_cookie_from_response(access_token, response.cookies)

            data = QuarkDriveService._safe_json_parse(response, "file list")
            if data is None:
                return [], None

            if data.get('status') == 200:
                files_list = data.get('data', {}).get('list', [])

                files = []
                for i, item in enumerate(files_list):
                    file_id = item.get('fid', '')
                    name = item.get('file_name', '')
                    is_file = item.get('file', False)
                    size = item.get('size', 0)
                    category = item.get('category', 0)
                    file_type_num = item.get('file_type', 0)  # Direct file type field
                    duration = None

                    # Determine file type
                    if not is_file:
                        file_type = 'folder'
                    elif category == 2 or file_type_num == 1:  # Audio category in Quark
                        file_type = 'audio'
                        duration = item.get('duration', 0)
                    else:
                        file_type = 'other'

                    cloud_file = CloudFile(
                        file_id=file_id,
                        parent_id=parent_id,
                        name=name,
                        file_type=file_type,
                        size=size if is_file else None,
                        duration=duration if file_type == 'audio' else None
                    )
                    files.append(cloud_file)

                # Return files and updated token if changed
                if updated_token != access_token:
                    return files, updated_token
                return files, None
            else:
                logger.debug(f"File list API returned error: {data.get('status')}")
                logger.debug(f"Error message: {data.get('message')}")
        except Exception as e:
            logger.error(f"Quark file list error: {e}", exc_info=True)
            logger.debug(f"Traceback: {traceback.format_exc()}")
        return [], None

    @classmethod
    def create_folder(cls, access_token: str, folder_name: str, parent_id: str = "0") -> tuple:
        """Create folder in Quark drive.

        Returns:
            tuple: (fid or None, updated_access_token or None)
        """
        try:
            url = f"{cls.BASE_URL}/1/clouddrive/file"
            params = {
                "pr": "ucpro",
                "fr": "pc",
                "uc_param_str": "",
                "__dt": 1000,
                "__t": int(time.time() * 1000),
            }
            payload = {
                "pdir_fid": parent_id,
                "file_name": folder_name,
                "dir_path": "",
                "dir_init_lock": False,
            }

            headers = cls.HEADERS.copy()
            headers["Cookie"] = access_token
            headers["Content-Type"] = "application/json"

            response = cls._get_session().post(
                url, params=params, json=payload, headers=headers, timeout=30
            )

            updated_token = cls._update_cookie_from_response(access_token, response.cookies)
            data = cls._safe_json_parse(response, "create folder")
            if data is None:
                return None, None

            if data.get("code") == 0:
                fid = data.get("data", {}).get("fid")
                if updated_token != access_token:
                    return fid, updated_token
                return fid, None
            return None, None
        except Exception as e:
            logger.error(f"Quark create folder error: {e}", exc_info=True)
            return None, None

    @classmethod
    def ensure_share_save_folder(
            cls,
            access_token: str,
            folder_name: str = "Harmony",
    ) -> tuple:
        """Ensure fixed folder exists in root and return its fid.

        Returns:
            tuple: (folder_fid or None, updated_access_token or None)
        """
        files, updated_token = cls.get_file_list(access_token, "0")
        token_for_next = updated_token or access_token
        for item in files:
            if item.file_type == "folder" and item.name == folder_name:
                return item.file_id, updated_token

        created_fid, created_token = cls.create_folder(token_for_next, folder_name, "0")
        if created_token:
            return created_fid, created_token
        return created_fid, updated_token

    @classmethod
    def get_share_stoken(cls, access_token: str, pwd_id: str, password: str = "") -> Optional[str]:
        """Get stoken for a shared link."""
        try:
            url = f"{cls.BASE_URL}/1/clouddrive/share/sharepage/token"
            params = {"pr": "ucpro", "fr": "pc"}
            payload = {"pwd_id": pwd_id, "passcode": password}
            headers = cls.HEADERS.copy()
            headers["Cookie"] = access_token
            headers["Content-Type"] = "application/json"

            response = cls._get_session().post(
                url, params=params, json=payload, headers=headers, timeout=30
            )
            data = cls._safe_json_parse(response, "share stoken")
            if data is None:
                return None
            if data.get("status") == 200:
                return data.get("data", {}).get("stoken")
            return None
        except Exception as e:
            logger.error(f"Quark share stoken error: {e}", exc_info=True)
            return None

    @classmethod
    def get_share_detail(
            cls,
            access_token: str,
            pwd_id: str,
            stoken: str,
            pdir_fid: str = "0",
    ) -> List[dict]:
        """Get share folder detail list (single page)."""
        try:
            url = f"{cls.BASE_URL}/1/clouddrive/share/sharepage/detail"
            params = {
                "pr": "ucpro",
                "fr": "pc",
                "pwd_id": pwd_id,
                "stoken": stoken,
                "pdir_fid": pdir_fid,
                "_page": "1",
                "_size": "200",
                "_sort": "file_type:asc,file_name:asc",
            }
            headers = cls.HEADERS.copy()
            headers["Cookie"] = access_token
            response = cls._get_session().get(url, params=params, headers=headers, timeout=30)
            data = cls._safe_json_parse(response, "share detail")
            if data is None:
                return []
            if data.get("status") != 200:
                return []
            return data.get("data", {}).get("list", []) or []
        except Exception as e:
            logger.error(f"Quark share detail error: {e}", exc_info=True)
            return []

    @classmethod
    def poll_task(cls, access_token: str, task_id: str, retry: int = 30) -> bool:
        """Poll task status until done."""
        headers = cls.HEADERS.copy()
        headers["Cookie"] = access_token
        for i in range(retry):
            try:
                params = {
                    "pr": "ucpro",
                    "fr": "pc",
                    "uc_param_str": "",
                    "task_id": task_id,
                    "retry_index": i,
                    "__dt": 1000,
                    "__t": int(time.time() * 1000),
                }
                url = f"{cls.BASE_URL}/1/clouddrive/task"
                response = cls._get_session().get(url, params=params, headers=headers, timeout=30)
                data = cls._safe_json_parse(response, "poll task")
                if data and data.get("message") == "ok":
                    status = data.get("data", {}).get("status")
                    if status == 2:
                        return True
                time.sleep(0.6)
            except Exception:
                time.sleep(0.6)
        return False

    @classmethod
    def save_share_items(
            cls,
            access_token: str,
            pwd_id: str,
            stoken: str,
            fid_list: List[str],
            fid_token_list: List[str],
            to_pdir_fid: str,
    ) -> bool:
        """Save share items to user drive and wait until task completed."""
        try:
            url = "https://drive.quark.cn/1/clouddrive/share/sharepage/save"
            params = {
                "pr": "ucpro",
                "fr": "pc",
                "uc_param_str": "",
                "__dt": 1000,
                "__t": int(time.time() * 1000),
            }
            payload = {
                "fid_list": fid_list,
                "fid_token_list": fid_token_list,
                "to_pdir_fid": to_pdir_fid,
                "pwd_id": pwd_id,
                "stoken": stoken,
                "pdir_fid": "0",
                "scene": "link",
            }
            headers = cls.HEADERS.copy()
            headers["Cookie"] = access_token
            headers["Content-Type"] = "application/json"

            response = cls._get_session().post(
                url, params=params, json=payload, headers=headers, timeout=30
            )
            data = cls._safe_json_parse(response, "save share")
            if data is None:
                return False
            task_id = data.get("data", {}).get("task_id")
            if not task_id:
                return False
            return cls.poll_task(access_token, task_id)
        except Exception as e:
            logger.error(f"Quark save share error: {e}", exc_info=True)
            return False

    @classmethod
    def get_download_url(cls, access_token: str, file_id: str) -> tuple:
        """Get download URL for a file.

        Returns:
            tuple: (download_url or None, updated_access_token or None)
        """
        try:
            url = f"{cls.BASE_URL}/1/clouddrive/file/download"
            params = {
                'pr': 'ucpro',
                'fr': 'pc'
            }
            headers = cls.HEADERS.copy()
            headers['Cookie'] = access_token
            headers['Content-Type'] = 'application/json'

            data = {'fids': [file_id]}

            response = cls._get_session().post(url, params=params, json=data,
                                     headers=headers, timeout=30)

            # Check for updated cookies
            updated_token = cls._update_cookie_from_response(access_token, response.cookies)

            response_data = QuarkDriveService._safe_json_parse(response, "download URL")
            if response_data is None:
                return None, None

            if response_data.get('status') == 200:
                download_list = response_data.get('data', [])

                if download_list:
                    download_url = download_list[0].get('download_url')

                    # Return URL and updated token if changed
                    if updated_token != access_token:
                        return download_url, updated_token
                    return download_url, None
                else:
                    logger.debug("No download URL in response")
            else:
                logger.debug(f"API returned error status: {response_data.get('status')}")
                logger.debug(f"API message: {response_data.get('message')}")
        except Exception as e:
            logger.error(f"Quark download URL error: {e}", exc_info=True)
            logger.debug(f"Traceback: {traceback.format_exc()}")
        return None, None

    @classmethod
    def get_account_info(cls, access_token: str, account_email: str) -> tuple:
        """Get account information including VIP status and nickname.

        Returns:
            tuple: (account_info or None, updated_access_token or None)
        """
        try:
            # First call: Get member info
            headers = {
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0",
                "origin": "https://pan.quark.cn",
                "referer": "https://pan.quark.cn/",
                "cookie": access_token
            }

            url1 = "https://drive-pc.quark.cn/1/clouddrive/member?pr=ucpro&fr=pc&uc_param_str=&fetch_subscribe=true&_ch=home&fetch_identity=true"

            response1 = requests.get(url1, headers=headers, timeout=30)

            if response1.status_code != 200:
                logger.debug(f"Failed to get member info: {response1.status_code}")
                return None, None

            data1 = QuarkDriveService._safe_json_parse(response1, "member info")
            if data1 is None:
                return None, None

            # Check for updated cookies from first response
            updated_token = cls._update_cookie_from_response(access_token, response1.cookies)

            # Second call: Get account nickname
            url2 = "https://pan.quark.cn/account/info?fr=pc&platform=pc"

            response2 = requests.get(url2, headers=headers, timeout=30)

            # Check for updated cookies from second response
            updated_token = cls._update_cookie_from_response(updated_token, response2.cookies)

            if response2.status_code != 200:
                logger.debug(f"Failed to get account nickname: {response2.status_code}")
                # Still return partial info
                nickname = account_email
            else:
                data2 = QuarkDriveService._safe_json_parse(response2, "account nickname")
                if data2 is None:
                    nickname = account_email
                else:
                    nickname = data2.get('data', {}).get('nickname', account_email)

            # Extract member info
            if data1.get('status') == 200:
                member_data = data1.get('data', {})
                member_type = member_data.get('member_type', 'unknown')
                is_vip = member_type in ['vip', 'svip', 'premium', 'SUPER_VIP']

                # Extract timestamps (in milliseconds)
                created_at = member_data.get('created_at')  # Account creation time
                exp_at = member_data.get('exp_at')  # VIP expiration time

                # Extract capacity info (in bytes)
                total_capacity = member_data.get('total_capacity', 0)
                use_capacity = member_data.get('use_capacity', 0)

                account_info = {
                    'nickname': nickname,
                    'member_type': member_type,
                    'is_vip': is_vip,
                    'created_at': created_at,
                    'exp_at': exp_at,
                    'total_capacity': total_capacity,
                    'use_capacity': use_capacity
                }

                # Return info and updated token if changed
                if updated_token != access_token:
                    return account_info, updated_token
                return account_info, None
            else:
                return None, None

        except Exception as e:
            logger.error(f"Get account info error: {e}", exc_info=True)
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
            # Test cookie by getting account info
            account_info, _ = cls.get_account_info(cookie_str, '')

            if account_info:
                return {
                    'account_email': account_info.get('nickname', ''),
                    'access_token': cookie_str,
                    'status': 'success'
                }
            return None
        except Exception as e:
            logger.error(f"Quark cookie validation error: {e}", exc_info=True)
            return None

    @classmethod
    def download_file(cls, url: str, dest_path: str,
                      access_token: str = None) -> bool:
        """Download file from URL to destination"""
        try:
            headers = {}
            if access_token:
                headers = {
                    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0",
                    "origin": "https://pan.quark.cn",
                    "referer": "https://pan.quark.cn/",
                    "cookie": access_token
                }

            response = requests.get(url, headers=headers, timeout=60, stream=True)

            if response.status_code == 200:
                downloaded_size = 0
                chunk_count = 0

                with open(dest_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            chunk_count += 1

                # Verify file was created
                import os
                if os.path.exists(dest_path):
                    return True
                else:
                    return False
            else:
                return False
        except Exception as e:
            logger.error(f"Quark download file error: {e}", exc_info=True)
            return False
