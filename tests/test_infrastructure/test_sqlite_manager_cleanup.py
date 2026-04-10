"""Cleanup behavior tests for DatabaseManager."""

import tempfile
import sqlite3
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


def test_database_manager_logs_when_wal_mode_is_not_applied(monkeypatch, caplog, tmp_path):
    """DatabaseManager should verify WAL mode instead of assuming the pragma succeeded."""

    class _FakeCursor:
        def __init__(self, row=None):
            self._row = row

        def fetchone(self):
            return self._row

    class _FakeConnection:
        def __init__(self):
            self.row_factory = None
            self.executed = []

        def execute(self, sql):
            self.executed.append(sql)
            if sql == "PRAGMA journal_mode=WAL":
                return _FakeCursor(("delete",))
            return _FakeCursor((1,))

        def close(self):
            return None

    fake_conn = _FakeConnection()
    fake_worker = Mock()

    monkeypatch.setattr(sqlite_manager_module, "get_write_worker", lambda _db_path: fake_worker)
    monkeypatch.setattr(sqlite_manager_module.sqlite3, "connect", lambda *_args, **_kwargs: fake_conn)
    monkeypatch.setattr(DatabaseManager, "_init_database", lambda self: None)

    manager = DatabaseManager(str(tmp_path / "wal.db"))
    manager._get_connection()

    assert "WAL mode was not applied" in caplog.text


def test_build_safe_fts_query_normalizes_unicode_and_strips_control_chars():
    query = "Cafe\u0301\x00Title"

    result = DatabaseManager._build_safe_fts_query(query)

    assert result == '"Cafe" "Title"'


def test_build_safe_fts_query_limits_term_length():
    query = "a" * 80

    result = DatabaseManager._build_safe_fts_query(query)

    assert result == f'"{"a" * 64}"'
