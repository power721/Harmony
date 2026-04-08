"""Helpers for deduplicating concurrent requests with the same key."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Callable, Dict, Generic, Hashable, TypeVar

T = TypeVar("T")


@dataclass
class _CallState(Generic[T]):
    event: threading.Event = field(default_factory=threading.Event)
    result: T | None = None
    error: BaseException | None = None


class SingleFlight(Generic[T]):
    """Ensure only one concurrent call runs for a given key."""

    def __init__(self):
        self._lock = threading.Lock()
        self._calls: Dict[Hashable, _CallState[T]] = {}

    def do(self, key: Hashable, fn: Callable[[], T]) -> T:
        with self._lock:
            state = self._calls.get(key)
            if state is None:
                state = _CallState[T]()
                self._calls[key] = state
                is_leader = True
            else:
                is_leader = False

        if is_leader:
            try:
                state.result = fn()
            except BaseException as exc:
                state.error = exc
            finally:
                state.event.set()
                with self._lock:
                    self._calls.pop(key, None)

            if state.error is not None:
                raise state.error
            return state.result

        state.event.wait()
        if state.error is not None:
            raise state.error
        return state.result
