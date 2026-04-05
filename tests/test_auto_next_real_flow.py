"""
Test to simulate actual auto-next playback flow.
"""

import pytest
import tempfile
import os
from pathlib import Path

# Create temporary audio files for testing
@pytest.fixture
def temp_audio_files():
    """Create temporary audio files for testing."""
    temp_dir = tempfile.mkdtemp()
    files = []

    # Create 3 dummy audio files (just empty files with .mp3 extension)
    for i in range(3):
        file_path = os.path.join(temp_dir, f"track_{i}.mp3")
        Path(file_path).touch()
        files.append(file_path)

    yield files

    # Cleanup
    for file_path in files:
        if os.path.exists(file_path):
            os.remove(file_path)
    os.rmdir(temp_dir)


class TestAutoNextRealFlow:
    """Test auto-next with realistic playback flow."""

    def test_auto_next_flow_with_real_files(self, temp_audio_files):
        """
        Test the complete auto-next flow from track start to end.

        This simulates:
        1. Load playlist with multiple tracks
        2. Start playing track 0
        3. Simulate end-of-media for track 0
        4. Verify track 1 starts playing
        """
        from app import Bootstrap
        from domain.track import Track
        from domain.playlist_item import PlaylistItem

        bootstrap = Bootstrap.instance()
        playback = bootstrap.playback_service
        engine = playback.engine

        # Create tracks in database
        track_repo = bootstrap.track_repo
        tracks = []
        for i, file_path in enumerate(temp_audio_files):
            track = Track(
                path=file_path,
                title=f"Track {i}",
                artist="Test Artist",
                album="Test Album",
                duration=180.0,
            )
            track_repo.add(track)
            tracks.append(track)

        # Create playlist items
        items = [PlaylistItem.from_track(track) for track in tracks]

        # Load playlist
        engine.load_playlist_items(items)

        # Start playing track 0
        engine.play_at(0)

        # Verify we're on track 0
        assert engine.current_index == 0

        # Verify _prevent_auto_next is False
        assert engine._prevent_auto_next == False

        # Simulate end-of-media event
        engine._on_end_of_media()

        # Verify we moved to track 1
        assert engine.current_index == 1, f"Expected index 1, got {engine.current_index}"

        print("✓ Auto-next works correctly!")

    def test_auto_next_in_sequential_mode(self, temp_audio_files):
        """Test auto-next specifically in SEQUENTIAL mode."""
        from app import Bootstrap
        from domain.track import Track
        from domain.playlist_item import PlaylistItem
        from domain.playback import PlayMode

        bootstrap = Bootstrap.instance()
        playback = bootstrap.playback_service
        engine = playback.engine

        # Create tracks
        track_repo = bootstrap.track_repo
        tracks = []
        for i, file_path in enumerate(temp_audio_files):
            track = Track(
                path=file_path,
                title=f"Track {i}",
                artist="Test",
                album="Test",
                duration=180.0,
            )
            track_repo.add(track)
            tracks.append(track)

        # Load playlist
        items = [PlaylistItem.from_track(track) for track in tracks]
        engine.load_playlist_items(items)

        # Set to SEQUENTIAL mode
        engine.set_play_mode(PlayMode.SEQUENTIAL)

        # Start playing
        engine.play_at(0)

        # Simulate end of track 0
        engine._on_end_of_media()
        assert engine.current_index == 1

        # Simulate end of track 1
        engine._on_end_of_media()
        assert engine.current_index == 2

        # Simulate end of track 2 (last track)
        engine._on_end_of_media()
        # Should stay at last track in SEQUENTIAL mode
        assert engine.current_index == 2

        print("✓ SEQUENTIAL mode auto-next works!")
