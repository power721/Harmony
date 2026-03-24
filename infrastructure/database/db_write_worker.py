"""
DB Write Worker - Serializes all database write operations.

SQLite is single-writer. This worker ensures all writes go through
a single thread to prevent "database is locked" errors.
"""

import logging
import queue
import sqlite3
import threading
from concurrent.futures import Future
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class DBWriteWorker:
    """
    Single-threaded worker for database write operations.

    All write operations are serialized through a queue to prevent
    SQLite locking issues when multiple threads write simultaneously.

    Usage:
        worker = DBWriteWorker(db_path)
        future = worker.submit(db_method, arg1, arg2)
        result = future.result()  # Blocks until complete

        # Or fire-and-forget:
        worker.submit_async(db_method, arg1, arg2)
    """

    def __init__(self, db_path: str):
        """
        Initialize the write worker.

        Args:
            db_path: Path to SQLite database
        """
        self._db_path = db_path
        self._queue: queue.Queue = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._conn: Optional[sqlite3.Connection] = None

        self._start()

    def _start(self):
        """Start the worker thread."""
        if self._thread is not None and self._thread.is_alive():
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._run,
            name="DBWriteWorker",
            daemon=True
        )
        self._thread.start()
        logger.info("[DBWriteWorker] Started")

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create the worker's database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(
                self._db_path,
                check_same_thread=False,
                timeout=30.0
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=30000")
            logger.info("[DBWriteWorker] Connection created with WAL mode")
        return self._conn

    def _run(self):
        """Main worker loop - runs in dedicated thread."""
        logger.debug(f"[DBWriteWorker] Thread started: {threading.current_thread().name}")

        while self._running:
            try:
                # Wait for task with timeout to allow checking _running
                try:
                    task = self._queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                func, args, kwargs, future = task

                try:
                    # Inject connection if callable expects 'conn' parameter
                    import inspect
                    sig = inspect.signature(func)
                    if 'conn' in sig.parameters and 'conn' not in kwargs:
                        kwargs['conn'] = self._get_connection()

                    result = func(*args, **kwargs)

                    if future:
                        future.set_result(result)

                except Exception as e:
                    logger.error(f"[DBWriteWorker] Task failed: {e}", exc_info=True)
                    if future:
                        future.set_exception(e)

                finally:
                    self._queue.task_done()

            except Exception as e:
                logger.error(f"[DBWriteWorker] Worker error: {e}", exc_info=True)

        # Cleanup
        if self._conn:
            try:
                self._conn.close()
                logger.info("[DBWriteWorker] Connection closed")
            except Exception:
                pass
            self._conn = None

        logger.info("[DBWriteWorker] Stopped")

    def submit(self, func: Callable, *args, **kwargs) -> Future:
        """
        Submit a write operation and return a Future.

        The operation will be executed in the worker thread.
        Caller can wait for result with future.result().

        Args:
            func: Function to execute (will receive 'conn' kwarg if it has that param)
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Future that will contain the result
        """
        future = Future()
        caller_thread = threading.current_thread().name

        # Ensure worker thread is running
        if not self._thread or not self._thread.is_alive():
            logger.warning(f"[DBWriteWorker] Thread not alive, restarting...")
            self._start()

        logger.debug(f"[DBWriteWorker] Submit from {caller_thread}: {func.__name__}, queue size: {self._queue.qsize()}")
        self._queue.put((func, args, kwargs, future))
        return future

    def submit_async(self, func: Callable, *args, **kwargs):
        """
        Submit a write operation without waiting for result.

        Fire-and-forget for operations where you don't need the result.

        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
        """
        self._queue.put((func, args, kwargs, None))

    def stop(self):
        """Stop the worker thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None

    def wait_idle(self):
        """Wait until all pending operations complete."""
        self._queue.join()


# Global singleton instance
_write_worker: Optional[DBWriteWorker] = None
_worker_lock = threading.Lock()


def get_write_worker(db_path: str = "Harmony.db") -> DBWriteWorker:
    """
    Get the global DBWriteWorker instance.

    Args:
        db_path: Database path (only used on first call)

    Returns:
        DBWriteWorker singleton
    """
    global _write_worker

    with _worker_lock:
        if _write_worker is None:
            _write_worker = DBWriteWorker(db_path)
        return _write_worker
