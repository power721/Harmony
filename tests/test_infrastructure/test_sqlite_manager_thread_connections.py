import threading
import tempfile
from pathlib import Path

from infrastructure.database.sqlite_manager import DatabaseManager


def test_close_shuts_down_connections_created_on_other_threads():
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = str(Path(temp_dir) / "thread-connections.db")
        manager = DatabaseManager(db_path)
        worker_conn = None

        def open_connection():
            nonlocal worker_conn
            worker_conn = manager._get_connection()
            worker_conn.execute("SELECT 1").fetchone()

        thread = threading.Thread(target=open_connection)
        thread.start()
        thread.join(timeout=2)

        assert worker_conn is not None
        manager.close()

        try:
            worker_conn.execute("SELECT 1")
        except Exception as exc:
            assert "closed" in str(exc).lower()
        else:
            raise AssertionError("worker connection should be closed by manager.close()")
