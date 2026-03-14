"""
HTTP client wrapper for network requests.
"""

import logging
from typing import Dict, Any
import requests

logger = logging.getLogger(__name__)


class HttpClient:
    """Wrapper around requests library with common configuration."""

    def __init__(self, default_headers: Dict[str, str] = None, timeout: int = 30):
        """
        Initialize HTTP client.

        Args:
            default_headers: Default headers for all requests
            timeout: Default timeout in seconds
        """
        self.default_headers = default_headers or {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.timeout = timeout

    def get(self, url: str, params: Dict = None, headers: Dict = None,
            timeout: int = None) -> requests.Response:
        """
        Make a GET request.

        Args:
            url: Request URL
            params: Query parameters
            headers: Additional headers
            timeout: Request timeout

        Returns:
            Response object
        """
        final_headers = {**self.default_headers, **(headers or {})}
        return requests.get(url, params=params, headers=final_headers,
                           timeout=timeout or self.timeout)

    def post(self, url: str, json: Any = None, data: Any = None,
             headers: Dict = None, timeout: int = None) -> requests.Response:
        """
        Make a POST request.

        Args:
            url: Request URL
            json: JSON body
            data: Form data
            headers: Additional headers
            timeout: Request timeout

        Returns:
            Response object
        """
        final_headers = {**self.default_headers, **(headers or {})}
        return requests.post(url, json=json, data=data, headers=final_headers,
                            timeout=timeout or self.timeout)

    def download(self, url: str, dest_path: str, headers: Dict = None,
                 chunk_size: int = 8192, progress_callback=None) -> bool:
        """
        Download a file.

        Args:
            url: Download URL
            dest_path: Destination file path
            headers: Additional headers
            chunk_size: Download chunk size
            progress_callback: Callback for progress updates (current, total)

        Returns:
            True if download successful
        """
        final_headers = {**self.default_headers, **(headers or {})}

        try:
            response = requests.get(url, headers=final_headers, stream=True,
                                   timeout=self.timeout)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(dest_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(downloaded, total_size)

            return True

        except Exception as e:
            logger.error(f"Download failed: {e}", exc_info=True)
            return False
