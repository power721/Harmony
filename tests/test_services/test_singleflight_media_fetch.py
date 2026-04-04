"""Tests for deduplicating concurrent media fetches across windows."""

from __future__ import annotations

import threading
import time
from unittest.mock import Mock, patch

from services.lyrics.lyrics_service import LyricsService
from services.metadata.cover_service import CoverService


def test_get_lyrics_by_qqmusic_mid_deduplicates_concurrent_requests():
    started = threading.Event()
    release = threading.Event()
    call_count = 0
    count_lock = threading.Lock()
    results: list[str] = []

    def fake_download(song_mid: str) -> str:
        nonlocal call_count
        with count_lock:
            call_count += 1
        started.set()
        release.wait(timeout=1)
        return f"lyrics:{song_mid}"

    def worker():
        results.append(LyricsService.get_lyrics_by_qqmusic_mid("mid_123"))

    with patch("services.lyrics.lyrics_service.download_qqmusic_lyrics", side_effect=fake_download):
        threads = [threading.Thread(target=worker) for _ in range(2)]
        threads[0].start()
        assert started.wait(timeout=1)
        threads[1].start()
        time.sleep(0.05)
        release.set()
        for thread in threads:
            thread.join(timeout=2)

    assert results == ["lyrics:mid_123", "lyrics:mid_123"]
    assert call_count == 1


def test_get_online_cover_deduplicates_concurrent_requests():
    started = threading.Event()
    release = threading.Event()
    http_client = Mock()
    fetch_count = 0
    count_lock = threading.Lock()
    results: list[str] = []

    def fake_get_content(url: str, timeout: int = 5) -> bytes:
        nonlocal fetch_count
        with count_lock:
            fetch_count += 1
        started.set()
        release.wait(timeout=1)
        return b"cover-bytes"

    http_client.get_content.side_effect = fake_get_content
    service = CoverService(http_client=http_client)

    def worker():
        results.append(
            service.get_online_cover(
                song_mid="song_mid_123",
                artist="Artist",
                title="Title",
            )
        )

    with patch("services.lyrics.qqmusic_lyrics.get_qqmusic_cover_url", return_value="https://example.com/cover.jpg"), \
            patch.object(service, "_get_cached_cover", return_value=None), \
            patch.object(service, "_save_cover_to_cache", return_value="/tmp/cover.jpg"):
        threads = [threading.Thread(target=worker) for _ in range(2)]
        threads[0].start()
        assert started.wait(timeout=1)
        threads[1].start()
        time.sleep(0.05)
        release.set()
        for thread in threads:
            thread.join(timeout=2)

    assert results == ["/tmp/cover.jpg", "/tmp/cover.jpg"]
    assert fetch_count == 1


def test_get_online_track_lyrics_deduplicates_fetch_and_save():
    started = threading.Event()
    release = threading.Event()
    save_count = 0
    save_lock = threading.Lock()
    results: list[str] = []

    def fake_fetch(song_mid: str) -> str:
        started.set()
        release.wait(timeout=1)
        return f"lyrics:{song_mid}"

    def fake_save(track_path: str, lyrics: str) -> bool:
        nonlocal save_count
        with save_lock:
            save_count += 1
        return True

    def worker():
        results.append(LyricsService.get_online_track_lyrics("mid_456", "/tmp/song.ogg"))

    with patch.object(LyricsService, "_get_local_lyrics", return_value=""), \
            patch.object(LyricsService, "get_lyrics_by_qqmusic_mid", side_effect=fake_fetch), \
            patch.object(LyricsService, "save_lyrics", side_effect=fake_save):
        threads = [threading.Thread(target=worker) for _ in range(2)]
        threads[0].start()
        assert started.wait(timeout=1)
        threads[1].start()
        time.sleep(0.05)
        release.set()
        for thread in threads:
            thread.join(timeout=2)

    assert results == ["lyrics:mid_456", "lyrics:mid_456"]
    assert save_count == 1
