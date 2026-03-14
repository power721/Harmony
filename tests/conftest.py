"""
Pytest configuration and shared fixtures.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    # Cleanup
    if temp_path.exists():
        shutil.rmtree(temp_path)


@pytest.fixture
def sample_track_data():
    """Sample track data for testing."""
    return {
        "id": 1,
        "path": "/music/test.mp3",
        "title": "Test Song",
        "artist": "Test Artist",
        "album": "Test Album",
        "duration": 180.5,
        "cover_path": "/covers/test.jpg",
    }


@pytest.fixture
def sample_cloud_file_data():
    """Sample cloud file data for testing."""
    return {
        "id": 1,
        "account_id": 1,
        "file_id": "quark_12345",
        "parent_id": "folder_67890",
        "name": "cloud_song.mp3",
        "file_type": "audio",
        "size": 5242880,
        "mime_type": "audio/mpeg",
        "duration": 240.0,
    }


@pytest.fixture
def sample_playlist_data():
    """Sample playlist data for testing."""
    return {
        "id": 1,
        "name": "My Playlist",
        "created_at": datetime.now(),
    }
