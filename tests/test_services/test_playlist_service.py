"""
Tests for PlaylistService.
"""

import pytest
from unittest.mock import Mock

from domain.playlist import Playlist
from domain.playlist_folder import PlaylistTree
from services.library.playlist_service import PlaylistService


@pytest.fixture
def playlist_repo():
    """Create a mock playlist repository."""
    return Mock()


@pytest.fixture
def track_repo():
    """Create a mock track repository."""
    return Mock()


@pytest.fixture
def event_bus():
    """Create a mock event bus with structure signal."""
    bus = Mock()
    bus.playlist_structure_changed = Mock()
    return bus


@pytest.fixture
def playlist_service(playlist_repo, track_repo, event_bus):
    """Create PlaylistService with mocked dependencies."""
    return PlaylistService(playlist_repo, track_repo, event_bus)


def test_create_folder_emits_structure_changed(playlist_service, event_bus):
    """Creating a folder should emit a structure-changed event."""
    playlist_service._playlist_repo.get_folder_by_name.return_value = None
    playlist_service._playlist_repo.create_folder.return_value = 9

    folder_id = playlist_service.create_folder("Running")

    assert folder_id == 9
    event_bus.playlist_structure_changed.emit.assert_called_once_with()


def test_get_playlist_tree_passes_repository_result_through(playlist_service):
    """Tree reads should be delegated to the repository."""
    tree = PlaylistTree(root_playlists=[Playlist(id=1, name="Root")], folders=[])
    playlist_service._playlist_repo.get_playlist_tree.return_value = tree

    assert playlist_service.get_playlist_tree() is tree


def test_move_playlist_to_folder_rejects_missing_folder(playlist_service):
    """Moving into a missing folder should raise a validation error."""
    playlist_service._playlist_repo.get_folder.return_value = None

    with pytest.raises(ValueError, match="folder does not exist"):
        playlist_service.move_playlist_to_folder(5, 999)
