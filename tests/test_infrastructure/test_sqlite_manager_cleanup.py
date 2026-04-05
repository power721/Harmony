"""Cleanup behavior tests for DatabaseManager."""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import infrastructure.database.sqlite_manager as sqlite_manager_module
from infrastructure.database.sqlite_manager import DatabaseManager


def test_database_manager_registers_atexit_cleanup_and_stops_write_worker(monkeypatch):
    """DatabaseManager should register cleanup and stop its write worker when closed."""
    registered_callbacks = []
    fake_worker = Mock()

    monkeypatch.setattr(
        sqlite_manager_module.atexit,
        "register",
        lambda callback: registered_callbacks.append(callback),
    )
    monkeypatch.setattr(sqlite_manager_module, "get_write_worker", lambda _db_path: fake_worker)

    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = str(Path(temp_dir) / "cleanup.db")
        manager = DatabaseManager(db_path)
        conn = manager._get_connection()

        assert manager.close in registered_callbacks
        assert conn.execute("SELECT 1").fetchone()[0] == 1

        manager.close()

        fake_worker.stop.assert_called_once_with()
        assert not hasattr(manager.local, "conn")
