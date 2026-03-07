"""
Quark Drive cloud storage service.
"""
import requests
import json
import time
from typing import Optional, Dict, List, Any
from database.models import CloudFile


class QuarkDriveService:
    """Service for Quark Drive cloud storage integration"""

    BASE_URL = "https://drive-pc.quark.cn"
    AUTH_URL = "https://uop.quark.cn"
    CLIENT_ID = "532"

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) quark-cloud-drive/2.5.20 Chrome/100.0.4896.160 '
                      'Electron/18.3.5.4-b478491100 Safari/537.36 Channel/pckk_other_ch',
        'Referer': 'https://pan.quark.cn/',
        'Origin': 'https://pan.quark.cn'
    }

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
            print(f"[DEBUG] Found __puus in response cookies: {cookie_dict['__puus'][:20]}...")

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
            print(f"[DEBUG] Updated cookie with __puus")
            return updated_cookie

        return access_token

    @classmethod
    def generate_qr_code(cls) -> Optional[Dict[str, str]]:
        """Generate QR code for login"""
        try:
            print(f"[DEBUG] Generating QR code for login...")
            t = int(time.time() * 1000)
            url = f"{cls.AUTH_URL}/cas/ajax/getTokenForQrcodeLogin"
            params = {
                'client_id': cls.CLIENT_ID,
                'v': '1.2',
                'request_id': t
            }

            print(f"[DEBUG] QR code request URL: {url}")
            print(f"[DEBUG] QR code request params: {params}")

            response = requests.get(url, params=params, timeout=10)
            print(f"[DEBUG] QR code response status: {response.status_code}")

            data = response.json()
            print(f"[DEBUG] QR code response data: {data}")

            if data.get('status') == 2000000:
                token = data['data']['members']['token']
                qr_url = f"https://su.quark.cn/4_eMHBJ?token={token}&client_id={cls.CLIENT_ID}&ssb=weblogin&uc_param_str=&uc_biz_str=S%3Acustom%7COPT%3ASAREA%400%7COPT%3AIMMERSIVE%401%7COPT%3ABACK_BTN_STYLE%400"
                print(f"[DEBUG] QR token generated: {token[:50]}...")
                print(f"[DEBUG] QR URL: {qr_url[:100]}...")
                return {
                    'token': token,
                    'qr_url': qr_url
                }
            else:
                print(f"[DEBUG] QR code generation failed with status: {data.get('status')}")
                print(f"[DEBUG] Error message: {data.get('message')}")
        except Exception as e:
            print(f"[DEBUG] Quark QR generation error: {e}")
            import traceback
            print(f"[DEBUG] Traceback: {traceback.format_exc()}")
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

                response = requests.get(url, params=params, timeout=10)
                data = response.json()
                print(f"[DEBUG] Poll response: {data}")
                status = data.get('status')
                message = data.get('message', '')

                if status == 2000000:
                    # Success - extract cookie and user info
                    print(f"[DEBUG] Login successful, extracting cookies...")
                    ticket = data['data']['members']['service_ticket']
                    print(f"[DEBUG] Service ticket: {ticket[:50] if ticket else 'None'}...")

                    # Get account info with ticket
                    info_url = f"https://pan.quark.cn/account/info"
                    info_params = {'st': ticket, 'lw': 'scan'}
                    print(f"[DEBUG] Getting account info from: {info_url}")
                    info_response = requests.get(info_url, params=info_params, timeout=10)

                    print(f"[DEBUG] Account info response status: {info_response.status_code}")
                    print(f"[DEBUG] Account info response cookies: {dict(info_response.cookies)}")

                    # Extract cookies
                    cookies = info_response.cookies
                    cookie_dict = {name: value for name, value in cookies.items()}
                    cookie_str = '; '.join([f"{k}={v}" for k, v in cookie_dict.items()])
                    print(f"[DEBUG] Cookie string length: {len(cookie_str)}")
                    print(f"[DEBUG] Cookie string preview: {cookie_str[:100]}...")

                    info_data = info_response.json()
                    print(f"[DEBUG] Account info data: {info_data}")

                    nickname = info_data.get('data', {}).get('nickname', 'Unknown')
                    print(f"[DEBUG] User nickname: {nickname}")

                    return {
                        'account_email': nickname,
                        'access_token': cookie_str,
                        'status': 'success'
                    }
                elif status == 50004001:
                    # Waiting for scan - return waiting status
                    print(f"[DEBUG] Waiting for user to scan QR code")
                    return {'status': 'waiting', 'message': message or 'Waiting for scan'}
                elif status == 50004002:
                    # QR expired
                    print(f"[DEBUG] QR code expired")
                    return {'status': 'expired', 'message': message}
                else:
                    print(f"[DEBUG] Unknown status code: {status}")
                    return {'status': 'error', 'message': message}

            except Exception as e:
                print(f"[DEBUG] Quark login poll error: {e}")
                import traceback
                print(f"[DEBUG] Traceback: {traceback.format_exc()}")

        return {'status': 'timeout', 'message': 'Login timeout'}

    @classmethod
    def get_file_list(cls, access_token: str, parent_id: str = '0') -> tuple:
        """Get list of files and folders in parent directory.

        Returns:
            tuple: (files_list, updated_access_token or None)
        """
        try:
            print(f"[DEBUG] Getting file list for parent_id: {parent_id}")
            url = f"{cls.BASE_URL}/1/clouddrive/file/sort"
            params = {
                'pr': 'ucpro',
                'fr': 'pc',
                'uc_param_str': '',
                'pdir_fid': parent_id,
                '_page': '1',
                '_size': '100',
                '_fetch_total': 'true',
                '_fetch_sub_dirs': '1',
                '_sort': 'file_type:asc,updated_at:desc'
            }

            headers = cls.HEADERS.copy()
            headers['Cookie'] = access_token

            print(f"[DEBUG] File list request URL: {url}")
            print(f"[DEBUG] Request params: {params}")

            response = requests.get(url, params=params, headers=headers, timeout=30)
            print(f"[DEBUG] File list response status: {response.status_code}")

            # Check for updated cookies
            updated_token = cls._update_cookie_from_response(access_token, response.cookies)

            data = response.json()
            print(f"[DEBUG] File list response status: {data.get('status')}")
            print(f"[DEBUG] File list response data keys: {list(data.get('data', {}).keys())}")

            if data.get('status') == 200:
                files_list = data.get('data', {}).get('list', [])
                print(f"[DEBUG] Files found: {len(files_list)}")

                files = []
                for i, item in enumerate(files_list):
                    file_id = item.get('fid', '')
                    name = item.get('file_name', '')
                    is_file = item.get('file', False)
                    size = item.get('size', 0)
                    category = item.get('category', 0)
                    file_type_num = item.get('file_type', 0)  # Direct file type field

                    print(f"[DEBUG] File {i+1}: {name}")
                    print(f"[DEBUG]   - ID: {file_id}")
                    print(f"[DEBUG]   - is_file: {is_file}")
                    print(f"[DEBUG]   - category: {category}")
                    print(f"[DEBUG]   - file_type: {file_type_num}")
                    print(f"[DEBUG]   - size: {size}")
                    if 'media_meta' in item:
                        print(f"[DEBUG]   - media_meta: {item['media_meta']}")

                    # Determine file type
                    if not is_file:
                        file_type = 'folder'
                    elif category == 2 or file_type_num == 'audio':  # Audio category in Quark
                        file_type = 'audio'
                        # Extract duration if available
                        duration = None
                        if 'media_meta' in item:
                            duration = item['media_meta'].get('duration')
                            print(f"[DEBUG]   - duration: {duration}")
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

                print(f"[DEBUG] Created {len(files)} CloudFile objects")
                print(f"[DEBUG] Audio files: {sum(1 for f in files if f.file_type == 'audio')}")
                print(f"[DEBUG] Folders: {sum(1 for f in files if f.file_type == 'folder')}")

                # Return files and updated token if changed
                if updated_token != access_token:
                    return files, updated_token
                return files, None
            else:
                print(f"[DEBUG] File list API returned error: {data.get('status')}")
                print(f"[DEBUG] Error message: {data.get('message')}")
        except Exception as e:
            print(f"[DEBUG] Quark file list error: {e}")
            import traceback
            print(f"[DEBUG] Traceback: {traceback.format_exc()}")
        return [], None

    @classmethod
    def get_download_url(cls, access_token: str, file_id: str) -> tuple:
        """Get download URL for a file.

        Returns:
            tuple: (download_url or None, updated_access_token or None)
        """
        try:
            print(f"[DEBUG] Getting download URL for file_id: {file_id}")
            url = f"{cls.BASE_URL}/1/clouddrive/file/download"
            params = {
                'pr': 'ucpro',
                'fr': 'pc'
            }
            headers = cls.HEADERS.copy()
            headers['Cookie'] = access_token
            headers['Content-Type'] = 'application/json'

            data = {'fids': [file_id]}

            print(f"[DEBUG] Request URL: {url}")
            print(f"[DEBUG] Request params: {params}")
            print(f"[DEBUG] Request data: {data}")
            print(f"[DEBUG] Cookie length: {len(access_token)}")

            response = requests.post(url, params=params, json=data,
                                    headers=headers, timeout=30)
            print(f"[DEBUG] Response status code: {response.status_code}")
            print(f"[DEBUG] Response headers: {dict(response.headers)}")

            # Check for updated cookies
            updated_token = cls._update_cookie_from_response(access_token, response.cookies)

            response_data = response.json()
            print(f"[DEBUG] Response data: {response_data}")

            if response_data.get('status') == 200:
                download_list = response_data.get('data', [])
                print(f"[DEBUG] Download list count: {len(download_list)}")

                if download_list:
                    download_url = download_list[0].get('download_url')
                    print(f"[DEBUG] Download URL retrieved: {download_url[:100] if download_url else 'None'}...")

                    # Return URL and updated token if changed
                    if updated_token != access_token:
                        return download_url, updated_token
                    return download_url, None
                else:
                    print(f"[DEBUG] No download URL in response")
            else:
                print(f"[DEBUG] API returned error status: {response_data.get('status')}")
                print(f"[DEBUG] API message: {response_data.get('message')}")
        except Exception as e:
            print(f"[DEBUG] Quark download URL error: {e}")
            import traceback
            print(f"[DEBUG] Traceback: {traceback.format_exc()}")
        return None, None

    @classmethod
    def get_account_info(cls, access_token: str, account_email: str) -> tuple:
        """Get account information including VIP status and nickname.

        Returns:
            tuple: (account_info or None, updated_access_token or None)
        """
        try:
            print(f"[DEBUG] Getting account info for: {account_email}")

            # First call: Get member info
            headers = {
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0",
                "origin": "https://pan.quark.cn",
                "referer": "https://pan.quark.cn/",
                "cookie": access_token
            }

            url1 = "https://drive-pc.quark.cn/1/clouddrive/member?pr=ucpro&fr=pc&uc_param_str=&fetch_subscribe=true&_ch=home&fetch_identity=true"
            print(f"[DEBUG] Member info URL: {url1}")

            response1 = requests.get(url1, headers=headers, timeout=30)
            print(f"[DEBUG] Member info response status: {response1.status_code}")

            if response1.status_code != 200:
                print(f"[DEBUG] Failed to get member info: {response1.status_code}")
                return None, None

            data1 = response1.json()
            print(f"[DEBUG] Member info data: {data1}")

            # Check for updated cookies from first response
            updated_token = cls._update_cookie_from_response(access_token, response1.cookies)

            # Second call: Get account nickname
            url2 = "https://pan.quark.cn/account/info?fr=pc&platform=pc"
            print(f"[DEBUG] Account info URL: {url2}")

            response2 = requests.get(url2, headers=headers, timeout=30)
            print(f"[DEBUG] Account info response status: {response2.status_code}")

            # Check for updated cookies from second response
            updated_token = cls._update_cookie_from_response(updated_token, response2.cookies)

            if response2.status_code != 200:
                print(f"[DEBUG] Failed to get account nickname: {response2.status_code}")
                # Still return partial info
                nickname = account_email
            else:
                data2 = response2.json()
                print(f"[DEBUG] Account info data: {data2}")
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
                    'vip_type': 'VIP' if is_vip else '普通用户',
                    'created_at': created_at,
                    'exp_at': exp_at,
                    'total_capacity': total_capacity,
                    'use_capacity': use_capacity
                }

                print(f"[DEBUG] Account info extracted: {account_info}")

                # Return info and updated token if changed
                if updated_token != access_token:
                    return account_info, updated_token
                return account_info, None
            else:
                print(f"[DEBUG] Member info API returned error: {data1.get('status')}")
                return None, None

        except Exception as e:
            print(f"[DEBUG] Get account info error: {e}")
            import traceback
            print(f"[DEBUG] Traceback: {traceback.format_exc()}")
            return None, None

    @classmethod
    def download_file(cls, url: str, dest_path: str,
                     access_token: str = None) -> bool:
        """Download file from URL to destination"""
        try:
            print(f"[DEBUG] Downloading file from URL: {url[:100]}...")
            print(f"[DEBUG] Destination path: {dest_path}")

            headers = {}
            if access_token:
                headers = {
                    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0",
                    "origin": "https://pan.quark.cn",
                    "referer": "https://pan.quark.cn/",
                    "cookie": access_token
                }
                print(f"[DEBUG] Using access token, headers set")

            print(f"[DEBUG] Starting download request...")
            response = requests.get(url, headers=headers, timeout=60, stream=True)
            print(f"[DEBUG] Download response status code: {response.status_code}")
            print(f"[DEBUG] Download response headers: {dict(response.headers)}")

            if response.status_code == 200:
                content_length = response.headers.get('Content-Length')
                print(f"[DEBUG] Content-Length: {content_length} ({float(content_length)/(1024*1024):.2f} MB)" if content_length else "[DEBUG] No Content-Length header")

                downloaded_size = 0
                chunk_count = 0

                with open(dest_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            chunk_count += 1

                            if chunk_count % 10 == 0:  # Log every 10 chunks
                                print(f"[DEBUG] Downloaded {downloaded_size / (1024*1024):.2f} MB...")

                print(f"[DEBUG] Download completed: {downloaded_size} bytes ({downloaded_size/(1024*1024):.2f} MB)")
                print(f"[DEBUG] File saved to: {dest_path}")

                # Verify file was created
                import os
                if os.path.exists(dest_path):
                    file_size = os.path.getsize(dest_path)
                    print(f"[DEBUG] Verified file exists, size: {file_size} bytes")
                    return True
                else:
                    print(f"[DEBUG] ERROR: File was not created at {dest_path}")
                    return False
            else:
                print(f"[DEBUG] Download failed with status code: {response.status_code}")
                print(f"[DEBUG] Response content: {response.text[:500]}")
                return False
        except Exception as e:
            print(f"[DEBUG] Quark file download error: {e}")
            import traceback
            print(f"[DEBUG] Traceback: {traceback.format_exc()}")
            return False
