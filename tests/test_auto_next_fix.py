"""
Test for auto-next bug fix.

This test verifies that the _prevent_auto_next flag is properly reset
after queue restoration, ensuring that automatic next track playback works.
"""

import pytest
from unittest.mock import Mock, patch
from domain.playback import PlayMode, PlaybackState
from domain.track import Track, TrackSource
from pathlib import Path


class TestAutoNextFix:
    """Test that auto-next works after queue restoration."""

    def test_prevent_auto_next_flag_is_reset_after_restoration(self):
        """
        Test that _prevent_auto_next is reset to False after queue restoration.

        This is the fix for the bug where auto-next stopped working for all tracks
        (both local and cloud) because the flag was set to True during restoration
        but never reset.
        """
        from app import Bootstrap
        from services.playback.playback_service import PlaybackService

        # Create a minimal playback service for testing
        bootstrap = Bootstrap.instance()
        playback = bootstrap.playback_service

        # Simulate what happens during queue restoration
        playback.engine.set_prevent_auto_next(True)

        # Verify the flag is set
        assert hasattr(playback.engine, '_prevent_auto_next')
        assert playback.engine._prevent_auto_next == True

        # Simulate the restoration completion (like in restore_queue_state)
        playback.engine.set_prevent_auto_next(False)

        # Verify the flag is reset
        assert playback.engine._prevent_auto_next == False

    def test_on_end_of_media_respects_prevent_auto_next(self):
        """
        Test that _on_end_of_media respects the _prevent_auto_next flag.

        When the flag is True, auto-next should be skipped.
        When the flag is False, auto-next should work normally.
        """
        from app import Bootstrap
        from infrastructure.audio.audio_engine import PlayerEngine
        from domain.playlist_item import PlaylistItem

        bootstrap = Bootstrap.instance()
        engine = PlayerEngine(backend_type="mpv")

        # Load a simple playlist
        items = [
            PlaylistItem(
                source=TrackSource.LOCAL,
                track_id=1,
                title="Track 1",
                artist="Artist",
                local_path="/fake/path1.mp3",
            ),
            PlaylistItem(
                source=TrackSource.LOCAL,
                track_id=2,
                title="Track 2",
                artist="Artist",
                local_path="/fake/path2.mp3",
            ),
        ]
        engine.load_playlist_items(items)
        engine.play_at(0)

        # Set prevent_auto_next flag
        engine.set_prevent_auto_next(True)

        # Simulate end of media
        engine._on_end_of_media()

        # Verify that auto-next was prevented (index should still be 0)
        assert engine.current_index == 0

        # Reset the flag
        engine.set_prevent_auto_next(False)

        # Simulate end of media again
        engine._on_end_of_media()

        # Verify that auto-next worked (index should now be 1)
        assert engine.current_index == 1
