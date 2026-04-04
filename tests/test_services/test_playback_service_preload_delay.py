"""Behavioral tests for delayed next-track preloading scheduling."""

from __future__ import annotations

from typing import List

from domain.playlist_item import PlaylistItem
from domain.playback import PlayMode, PlaybackState
from domain.track import TrackSource
from services.playback.playback_service import PlaybackService


FEATURE_DELAY_MS = 10_000


class FakeSignal:
    def __init__(self) -> None:
        self._slots: List = []

    def connect(self, slot) -> None:
        self._slots.append(slot)

    def emit(self, *args, **kwargs) -> None:
        for slot in list(self._slots):
            slot(*args, **kwargs)


class FakeTimer:
    def __init__(self) -> None:
        self.timeout = FakeSignal()
        self.intervals: List[int] = []
        self.single_shot = False
        self.start_count = 0
        self.stop_count = 0
        self._active = False

    def setSingleShot(self, value: bool) -> None:
        self.single_shot = value

    def start(self, interval: int = 0) -> None:
        self.start_count += 1
        self.intervals.append(interval)
        self._active = True

    def stop(self) -> None:
        self.stop_count += 1
        self._active = False

    def isActive(self) -> bool:
        return self._active

    def fire(self) -> None:
        if not self._active:
            return
        self.timeout.emit()
        if self.single_shot:
            self._active = False


class FakeEngine:
    def __init__(self) -> None:
        self.state = PlaybackState.PLAYING
        self.play_mode = PlayMode.SEQUENTIAL
        self._next_item: PlaylistItem | None = None

    def get_next_item(self) -> PlaylistItem | None:
        return self._next_item


def make_cloud_item(cloud_file_id: str) -> PlaylistItem:
    return PlaylistItem(
        source=TrackSource.QUARK,
        cloud_file_id=cloud_file_id,
        title="Cloud",
        artist="Artist",
        needs_download=True,
    )


def make_service(monkeypatch):
    timers: List[FakeTimer] = []

    def timer_factory():
        timer = FakeTimer()
        timers.append(timer)
        return timer

    monkeypatch.setattr("services.playback.playback_service.QTimer", timer_factory)

    service = PlaybackService.__new__(PlaybackService)
    service._engine = FakeEngine()
    service._pending_next_preload_cloud_file_id = None
    service._next_preload_timer = None
    service._preload_online_track_calls: List[str] = []
    service._preload_cloud_track_calls: List[str] = []

    def _preload_online(item: PlaylistItem) -> None:
        service._preload_online_track_calls.append(item.cloud_file_id)

    def _preload_cloud(item: PlaylistItem) -> None:
        service._preload_cloud_track_calls.append(item.cloud_file_id)

    service._preload_online_track = _preload_online
    service._preload_cloud_track = _preload_cloud

    return service, timers


def test_schedule_next_track_preload_starts_single_shot_10_second_timer(monkeypatch):
    service, timers = make_service(monkeypatch)
    service._engine._next_item = make_cloud_item("cloud-1")

    PlaybackService._schedule_next_track_preload(service)

    assert timers, "timer should be created"
    timer = timers[-1]
    assert timer.start_count == 1
    assert timer.intervals[-1] == FEATURE_DELAY_MS
    assert timer.single_shot
    assert service._pending_next_preload_cloud_file_id == "cloud-1"


def test_schedule_next_track_preload_reuses_existing_pending_target(monkeypatch):
    service, timers = make_service(monkeypatch)
    service._engine._next_item = make_cloud_item("cloud-2")

    PlaybackService._schedule_next_track_preload(service)
    PlaybackService._schedule_next_track_preload(service)

    assert timers[-1].start_count == 1


def test_schedule_next_track_preload_replaces_previous_target(monkeypatch):
    service, timers = make_service(monkeypatch)
    service._engine._next_item = make_cloud_item("cloud-3")
    PlaybackService._schedule_next_track_preload(service)

    first_timer = timers[-1]
    assert first_timer.isActive()

    service._engine._next_item = make_cloud_item("cloud-4")
    PlaybackService._schedule_next_track_preload(service)

    second_timer = timers[-1]
    assert first_timer.stop_count >= 1
    assert not first_timer.isActive()
    assert second_timer.start_count == 1
    assert service._pending_next_preload_cloud_file_id == "cloud-4"


def test_next_track_preload_timeout_skips_when_target_is_no_longer_next(monkeypatch):
    service, timers = make_service(monkeypatch)
    service._engine._next_item = make_cloud_item("cloud-5")
    PlaybackService._schedule_next_track_preload(service)

    timer = timers[-1]

    service._engine._next_item = make_cloud_item("cloud-6")
    timer.fire()

    assert not service._preload_cloud_track_calls


def test_next_track_preload_timeout_dispatches_current_target_once(monkeypatch):
    service, timers = make_service(monkeypatch)
    service._engine._next_item = make_cloud_item("cloud-7")
    PlaybackService._schedule_next_track_preload(service)

    timer = timers[-1]
    timer.fire()

    assert service._preload_cloud_track_calls == ["cloud-7"]
