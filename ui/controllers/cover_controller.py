"""
Cover controller for managing cover search and download operations.
"""
import logging
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable

from PySide6.QtCore import QObject, Signal, QTimer

from infrastructure.network import HttpClient
from services.metadata import CoverService

logger = logging.getLogger(__name__)


class CoverController(QObject):
    """Manages cover search and download operations with thread pool."""

    search_completed = Signal(list)  # Emits list of search results
    search_failed = Signal(str)  # Emits error message
    download_completed = Signal(bytes, str)  # Emits cover data and source
    download_failed = Signal(str)  # Emits error message

    def __init__(self, cover_service: CoverService, parent=None):
        super().__init__(parent)
        self._cover_service = cover_service
        self._executor = ThreadPoolExecutor(max_workers=3)
        self._active_futures = []
        self._shutdown = False

    def search(self, search_func: Callable, on_complete: Callable, on_error: Callable):
        """Run search in thread pool.

        Args:
            search_func: Callable that performs the search and returns List[dict]
            on_complete: Callback for successful search, receives List[dict]
            on_error: Callback for failed search, receives error message str
        """
        future = self._executor.submit(self._search_task, search_func)
        future.add_done_callback(
            lambda f: self._on_search_done(f, on_complete, on_error)
        )
        self._active_futures.append(future)

    def download(self, url: str, on_complete: Callable, on_error: Callable, source: str = ""):
        """Download cover in thread pool.

        Args:
            url: URL to download
            on_complete: Callback for successful download, receives (bytes, str)
            on_error: Callback for failed download, receives error message str
            source: Source name for tracking
        """
        future = self._executor.submit(self._download_task, url, source)
        future.add_done_callback(
            lambda f: self._on_download_done(f, on_complete, on_error)
        )
        self._active_futures.append(future)

    def download_from_data(self, download_func: Callable, on_complete: Callable, on_error: Callable):
        """Download cover using custom function (for lazy fetch).

        Args:
            download_func: Callable that returns bytes
            on_complete: Callback for successful download, receives (bytes, str)
            on_error: Callback for failed download, receives error message str
        """
        future = self._executor.submit(download_func)
        future.add_done_callback(
            lambda f: self._on_lazy_fetch_done(f, on_complete, on_error)
        )
        self._active_futures.append(future)

    def cancel_all(self):
        """Cancel all pending operations."""
        for future in self._active_futures:
            future.cancel()
        self._active_futures.clear()

    def _dispatch_to_main(self, func, *args, **kwargs):
        """Dispatch a callable to the main Qt thread."""
        if self._shutdown:
            return
        QTimer.singleShot(0, lambda: func(*args, **kwargs))

    def _search_task(self, search_func: Callable) -> list:
        """Execute search function in thread pool.

        Args:
            search_func: Callable that performs search

        Returns:
            List of search results
        """
        try:
            return search_func()
        except Exception as e:
            logger.error(f"Error in search task: {e}", exc_info=True)
            raise

    def _download_task(self, url: str, source: str) -> tuple:
        """Download cover from URL in thread pool.

        Args:
            url: URL to download
            source: Source name

        Returns:
            Tuple of (cover_data, source)
        """
        try:
            http_client = HttpClient()
            cover_data = http_client.get_content(url, timeout=10)
            if cover_data:
                return (cover_data, source)
            else:
                raise ValueError("No content received from URL")
        except Exception as e:
            logger.error(f"Error downloading cover: {e}", exc_info=True)
            raise

    def _on_search_done(self, future: Future, on_complete: Callable, on_error: Callable):
        """Handle search completion.

        Args:
            future: Completed future
            on_complete: Success callback
            on_error: Error callback
        """
        try:
            results = future.result()
            self._dispatch_to_main(on_complete, results)
        except Exception as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            self._dispatch_to_main(on_error, str(e))
        finally:
            if future in self._active_futures:
                self._active_futures.remove(future)

    def _on_download_done(self, future: Future, on_complete: Callable, on_error: Callable):
        """Handle download completion.

        Args:
            future: Completed future
            on_complete: Success callback
            on_error: Error callback
        """
        try:
            cover_data, source = future.result()
            self._dispatch_to_main(on_complete, cover_data, source)
        except Exception as e:
            logger.error(f"Download failed: {e}", exc_info=True)
            self._dispatch_to_main(on_error, str(e))
        finally:
            if future in self._active_futures:
                self._active_futures.remove(future)

    def _on_lazy_fetch_done(self, future: Future, on_complete: Callable, on_error: Callable):
        """Handle lazy fetch completion.

        Args:
            future: Completed future
            on_complete: Success callback
            on_error: Error callback
        """
        try:
            cover_data = future.result()
            # For lazy fetch, source is always qqmusic
            self._dispatch_to_main(on_complete, cover_data, 'qqmusic')
        except Exception as e:
            logger.error(f"Lazy fetch failed: {e}", exc_info=True)
            self._dispatch_to_main(on_error, str(e))
        finally:
            if future in self._active_futures:
                self._active_futures.remove(future)

    def shutdown(self):
        """Shutdown the executor."""
        self._shutdown = True
        self.cancel_all()
        self._executor.shutdown(wait=False)
