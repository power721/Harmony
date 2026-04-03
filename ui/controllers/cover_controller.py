"""
Production-grade CoverController v2
Features:
- Qt Signal/Slot (thread-safe, no manual dispatch)
- Task deduplication (avoid duplicate searches/downloads)
- Cancellation with token
- Future lifecycle management
- Optional simple in-memory cache
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable, Dict, Any, Optional

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


class CoverController(QObject):
    # ===== Signals (always delivered in main thread) =====
    search_completed = Signal(object, list)   # token, results
    search_failed = Signal(object, str)       # token, error

    download_completed = Signal(object, bytes, str)  # token, data, source
    download_failed = Signal(object, str)            # token, error

    def __init__(self, max_workers: int = 4, parent=None):
        super().__init__(parent)
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._futures: Dict[str, Future] = {}
        self._lock = threading.Lock()
        self._shutdown = False

        # simple cache (can replace with LRU)
        self._cache: Dict[str, Any] = {}

    # ===================== Public API =====================

    def search(self, key: str, task: Callable[[], list]):
        """
        key: unique key for dedup (e.g. artist+title)
        """
        if self._shutdown:
            return None

        token = self._make_token("search", key)

        with self._lock:
            # Dedup: if same task running, skip
            if token in self._futures:
                logger.debug(f"[CoverController] search dedup hit: {token}")
                return token

            # Cache hit
            if key in self._cache:
                logger.debug(f"[CoverController] search cache hit: {key}")
                self.search_completed.emit(token, self._cache[key])
                return token

            future = self._executor.submit(self._wrap_search, token, key, task)
            self._futures[token] = future

            future.add_done_callback(self._cleanup)

        return token

    def download(self, key: str, task: Callable[[], tuple]):
        """
        task returns (bytes, source)
        """
        if self._shutdown:
            return None

        token = self._make_token("download", key)

        with self._lock:
            if token in self._futures:
                logger.debug(f"[CoverController] download dedup hit: {token}")
                return token

            future = self._executor.submit(self._wrap_download, token, key, task)
            self._futures[token] = future
            future.add_done_callback(self._cleanup)

        return token

    def cancel(self, token: str):
        with self._lock:
            future = self._futures.get(token)
            if future:
                future.cancel()
                logger.debug(f"[CoverController] cancelled: {token}")

    def cancel_all(self):
        with self._lock:
            for token, future in self._futures.items():
                future.cancel()
            self._futures.clear()

    def shutdown(self):
        if self._shutdown:
            return
        self._shutdown = True
        self.cancel_all()
        self._executor.shutdown(wait=True, cancel_futures=True)

    # ===================== Internal =====================

    def _wrap_search(self, token: str, key: str, task: Callable):
        try:
            results = task()
            if self._shutdown:
                return
            self._cache[key] = results
            self.search_completed.emit(token, results)
        except Exception as e:
            if self._shutdown:
                return
            logger.error(f"Search failed: {e}", exc_info=True)
            self.search_failed.emit(token, str(e))

    def _wrap_download(self, token: str, key: str, task: Callable):
        try:
            data, source = task()
            if self._shutdown:
                return
            self.download_completed.emit(token, data, source)
        except Exception as e:
            if self._shutdown:
                return
            logger.error(f"Download failed: {e}", exc_info=True)
            self.download_failed.emit(token, str(e))

    def _cleanup(self, future: Future):
        with self._lock:
            for k, f in list(self._futures.items()):
                if f is future:
                    del self._futures[k]

    def _make_token(self, prefix: str, key: str) -> str:
        return f"{prefix}:{key}"
