import inspect
import queue
import pytest

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


def test_worker_stops_after_too_many_consecutive_failures(tmp_path):
    worker = DBWriteWorker(str(tmp_path / "failures.db"))
    worker._max_consecutive_failures = 2

    def _always_fail():
        raise RuntimeError("boom")

    try:
        first = worker.submit(_always_fail)
        second = worker.submit(_always_fail)

        with pytest.raises(RuntimeError, match="boom"):
            first.result(timeout=2)
        with pytest.raises(RuntimeError, match="boom"):
            second.result(timeout=2)

        worker._thread.join(timeout=2)

        assert worker._running is False
        assert worker._thread.is_alive() is False
    finally:
        worker.stop()


def test_write_queue_is_bounded(tmp_path):
    worker = DBWriteWorker(str(tmp_path / "bounded.db"))

    try:
        assert worker._queue.maxsize == 1000
    finally:
        worker.stop()


def test_submit_sets_future_exception_when_queue_is_full(monkeypatch, tmp_path):
    worker = DBWriteWorker(str(tmp_path / "full.db"))

    def _raise_full(_item, timeout=None):
        raise queue.Full()

    try:
        monkeypatch.setattr(worker._queue, "put", _raise_full)
        future = worker.submit(lambda: "ok")

        with pytest.raises(queue.Full):
            future.result(timeout=0)
    finally:
        worker.stop()
