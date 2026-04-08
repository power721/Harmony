"""
HTTP client wrapper for network requests.
"""

import atexit
from contextlib import contextmanager
import logging
from pathlib import Path
import threading
from typing import Dict, Any, Optional, Iterator

import requests
from requests.adapters import HTTPAdapter

logger = logging.getLogger(__name__)


class HttpClient:
    """Wrapper around requests library with common configuration and connection pooling."""

    DEFAULT_TIMEOUT = 30
    DEFAULT_POOL_CONNECTIONS = 20
    DEFAULT_POOL_MAXSIZE = 20
    DEFAULT_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    _shared_clients = {}
    _shared_lock = threading.Lock()
    _atexit_registered = False

    def __init__(
        self,
        default_headers: Dict[str, str] = None,
        timeout: int = DEFAULT_TIMEOUT,
        pool_connections: int = DEFAULT_POOL_CONNECTIONS,
        pool_maxsize: int = DEFAULT_POOL_MAXSIZE,
        pool_block: bool = True,
    ):
        """
        Initialize HTTP client.

        Args:
            default_headers: Default headers for all requests
            timeout: Default timeout in seconds
        """
        self.default_headers = default_headers or self.DEFAULT_HEADERS.copy()
        self.timeout = timeout
        self._session = self._create_session(
            default_headers=self.default_headers,
            pool_connections=pool_connections,
            pool_maxsize=pool_maxsize,
            pool_block=pool_block,
        )

    @classmethod
    def _create_session(
        cls,
        default_headers: Dict[str, str],
        pool_connections: int,
        pool_maxsize: int,
        pool_block: bool,
    ) -> requests.Session:
        """Create a requests session with a mounted pooled adapter."""
        session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=pool_connections,
            pool_maxsize=pool_maxsize,
            pool_block=pool_block,
        )
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update(default_headers)
        return session

    @classmethod
    def shared(
        cls,
        default_headers: Dict[str, str] = None,
        timeout: int = DEFAULT_TIMEOUT,
        pool_connections: int = DEFAULT_POOL_CONNECTIONS,
        pool_maxsize: int = DEFAULT_POOL_MAXSIZE,
        pool_block: bool = True,
    ) -> "HttpClient":
        """Get or create a shared HttpClient for the given configuration."""
        headers = default_headers or cls.DEFAULT_HEADERS.copy()
        key = (
            timeout,
            tuple(sorted(headers.items())),
            pool_connections,
            pool_maxsize,
            pool_block,
        )
        with cls._shared_lock:
            if not cls._atexit_registered:
                atexit.register(cls.close_shared_clients)
                cls._atexit_registered = True
            client = cls._shared_clients.get(key)
            if client is None:
                client = cls(
                    default_headers=headers,
                    timeout=timeout,
                    pool_connections=pool_connections,
                    pool_maxsize=pool_maxsize,
                    pool_block=pool_block,
                )
                cls._shared_clients[key] = client
            return client

    @classmethod
    def close_shared_clients(cls) -> None:
        with cls._shared_lock:
            for client in cls._shared_clients.values():
                client.close()
            cls._shared_clients = {}

    def request(
        self,
        method: str,
        url: str,
        params: Dict = None,
        json: Any = None,
        data: Any = None,
        headers: Dict = None,
        timeout: int = None,
        stream: bool = False,
        **request_kwargs,
    ) -> requests.Response:
        """Make an HTTP request using the configured shared session."""
        method = method.upper()
        request_timeout = timeout or self.timeout
        verify = request_kwargs.pop("verify", True)
        if method == "GET":
            return self._session.get(
                url,
                params=params,
                headers=headers,
                timeout=request_timeout,
                stream=stream,
                verify=verify,
                **request_kwargs,
            )
        if method == "POST":
            return self._session.post(
                url,
                json=json,
                data=data,
                headers=headers,
                timeout=request_timeout,
                stream=stream,
                verify=verify,
                **request_kwargs,
            )
        return self._session.request(
            method,
            url,
            params=params,
            json=json,
            data=data,
            headers=headers,
            timeout=request_timeout,
            stream=stream,
            verify=verify,
            **request_kwargs,
        )

    def get(self, url: str, params: Dict = None, headers: Dict = None,
            timeout: int = None, **request_kwargs) -> requests.Response:
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
        return self.request("GET", url, params=params, headers=headers, timeout=timeout, **request_kwargs)

    @contextmanager
    def stream(
        self,
        method: str,
        url: str,
        params: Dict = None,
        json: Any = None,
        data: Any = None,
        headers: Dict = None,
        timeout: int = None,
        **request_kwargs,
    ) -> Iterator[requests.Response]:
        """Open a streamed response and always close it after use."""
        response = self.request(
            method,
            url,
            params=params,
            json=json,
            data=data,
            headers=headers,
            timeout=timeout,
            stream=True,
            **request_kwargs,
        )
        try:
            response.raise_for_status()
            yield response
        finally:
            response.close()

    def get_content(self, url: str, params: Dict = None, headers: Dict = None,
                    timeout: int = None) -> Optional[bytes]:
        """
        Make a GET request and return content as bytes.

        Args:
            url: Request URL
            params: Query parameters
            headers: Additional headers
            timeout: Request timeout

        Returns:
            Response content as bytes, or None if request failed
        """
        try:
            with self.stream("GET", url, params=params, headers=headers, timeout=timeout) as response:
                return response.content
        except Exception as e:
            logger.error(f"GET content failed for {url}: {e}")
            return None

    def post(self, url: str, json: Any = None, data: Any = None,
             headers: Dict = None, timeout: int = None, **request_kwargs) -> requests.Response:
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
        return self.request("POST", url, json=json, data=data, headers=headers, timeout=timeout, **request_kwargs)

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
        response = None

        try:
            with self.stream("GET", url, headers=headers, timeout=self.timeout) as response:
                try:
                    total_size = int(response.headers.get('content-length', 0))
                except (ValueError, TypeError):
                    total_size = 0
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
            # Clean up incomplete file on failure
            if Path(dest_path).exists():
                try:
                    Path(dest_path).unlink()
                except OSError:
                    pass
            return False

    def close(self):
        """Close the session and release resources."""
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
