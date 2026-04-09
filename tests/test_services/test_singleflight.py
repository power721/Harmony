"""Behavioral tests for SingleFlight concurrency guarantees."""

from __future__ import annotations

import threading
import time

from services._singleflight import SingleFlight


def test_do_deduplicates_new_call_arriving_during_leader_completion():
    singleflight = SingleFlight[str]()
    before_set = threading.Event()
    allow_set = threading.Event()
    release_leader = threading.Event()
    release_third = threading.Event()
    call_count = 0
    count_lock = threading.Lock()
    original_event_set = threading.Event.set

    def wrapped_set(event: threading.Event) -> None:
        before_set.set()
        assert allow_set.wait(timeout=1)
        original_event_set(event)

    def work(label: str, release: threading.Event) -> str:
        nonlocal call_count
        with count_lock:
            call_count += 1
        assert release.wait(timeout=1)
        return label

    def leader() -> None:
        assert singleflight.do("same-key", lambda: work("leader", release_leader)) == "leader"

    def follower(results: list[str]) -> None:
        results.append(singleflight.do("same-key", lambda: work("follower", release_third)))

    first_results: list[str] = []
    second_results: list[str] = []

    leader_thread = threading.Thread(target=leader)
    follower_thread = threading.Thread(target=follower, args=(first_results,))

    leader_thread.start()
    time.sleep(0.05)
    follower_thread.start()
    time.sleep(0.05)

    leader_state = singleflight._calls["same-key"]
    monkeypatch = None

    try:
        leader_state.event.set = lambda: wrapped_set(leader_state.event)  # type: ignore[method-assign]
        release_leader.set()
        assert before_set.wait(timeout=1)

        third_thread = threading.Thread(target=follower, args=(second_results,))
        third_thread.start()
        time.sleep(0.05)
        allow_set.set()
        release_third.set()

        third_thread.join(timeout=2)
    finally:
        leader_thread.join(timeout=2)
        follower_thread.join(timeout=2)

    assert first_results == ["leader"]
    assert second_results == ["leader"]
    assert call_count == 1
