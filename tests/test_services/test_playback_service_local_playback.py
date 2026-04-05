"""PlaybackService local playback regression tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from domain.playlist_item import PlaylistItem
from domain.track import TrackSource
from services.playback.playback_service import PlaybackService


def test_play_local_track_uses_bounded_context_instead_of_full_library(tmp_path):
    """Single-track playback should not scan the entire library."""
    track_path = tmp_path / "track.mp3"
    track_path.write_text("stub")

    track = SimpleNamespace(id=42, path=str(track_path), source=TrackSource.LOCAL)
    item = PlaylistItem(
        source=TrackSource.LOCAL,
        track_id=42,
        local_path=str(track_path),
        title="Track 42",
    )

    service = PlaybackService.__new__(PlaybackService)
    service._track_repo = SimpleNamespace(
        get_by_id=Mock(return_value=track),
        get_track_position=Mock(return_value=120),
        get_all=Mock(return_value=[track]),
    )
    service._filter_and_convert_tracks = Mock(return_value=[item])
    service._iter_library_track_batches = Mock(side_effect=AssertionError("full scan not expected"))
    service._engine = SimpleNamespace(
        clear_playlist=Mock(),
        cleanup_temp_files=Mock(),
        load_playlist_items=Mock(),
        is_shuffle_mode=Mock(return_value=False),
        play_at=Mock(),
    )
    service._set_source = Mock()
    service.save_queue = Mock()
    service._config = SimpleNamespace(
        set_current_track_id=Mock(),
        set_playback_source=Mock(),
    )

    PlaybackService.play_local_track(service, 42)

    service._track_repo.get_track_position.assert_called_once_with(42)
    service._track_repo.get_all.assert_called_once()
    service._iter_library_track_batches.assert_not_called()
    service._engine.load_playlist_items.assert_called_once_with([item])
    service._engine.play_at.assert_called_once_with(0)


def test_play_local_tracks_clamps_negative_start_index_to_zero(tmp_path):
    """Batch local playback should never forward a negative start index to the engine."""
    first_path = tmp_path / "one.mp3"
    second_path = tmp_path / "two.mp3"
    first_path.write_text("one")
    second_path.write_text("two")

    tracks = [
        SimpleNamespace(id=1, path=str(first_path), source=TrackSource.LOCAL),
        SimpleNamespace(id=2, path=str(second_path), source=TrackSource.LOCAL),
    ]
    items = [
        PlaylistItem(source=TrackSource.LOCAL, track_id=1, local_path=str(first_path), title="One"),
        PlaylistItem(source=TrackSource.LOCAL, track_id=2, local_path=str(second_path), title="Two"),
    ]

    service = PlaybackService.__new__(PlaybackService)
    service._track_repo = SimpleNamespace(get_by_ids=Mock(return_value=tracks))
    service._filter_and_convert_tracks = Mock(return_value=items)
    service._engine = SimpleNamespace(
        clear_playlist=Mock(),
        load_playlist_items=Mock(),
        is_shuffle_mode=Mock(return_value=False),
        play_at=Mock(),
    )
    service._set_source = Mock()
    service.save_queue = Mock()
    service._config = SimpleNamespace(set_playback_source=Mock())

    PlaybackService.play_local_tracks(service, [1, 2], start_index=-5)

    service._engine.play_at.assert_called_once_with(0)
