import inspect

import infrastructure.database.db_write_worker as dbw
from infrastructure.database.db_write_worker import DBWriteWorker


def _func_requires_conn(conn=None):
    return conn is not None


def test_callable_accepts_conn_is_cached(monkeypatch, tmp_path):
    worker = DBWriteWorker(str(tmp_path / "cache.db"))
    calls = {"count": 0}
    real_signature = inspect.signature

    def _counting_signature(fn):
        calls["count"] += 1
        return real_signature(fn)

    try:
        monkeypatch.setattr(dbw.inspect, "signature", _counting_signature)
        assert worker._callable_accepts_conn(_func_requires_conn) is True
        assert worker._callable_accepts_conn(_func_requires_conn) is True
        assert calls["count"] == 1
    finally:
        worker.stop()
