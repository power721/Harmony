"""
Tests for PlaylistTreeWidget behavior.
"""

import os
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication

from domain.playlist import Playlist
from domain.playlist_folder import PlaylistFolder, PlaylistFolderGroup, PlaylistTree
from ui.widgets.playlist_tree_widget import PlaylistTreeWidget

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_tree_widget_emits_move_to_folder_for_root_playlist_drop(qapp):
    widget = PlaylistTreeWidget()
    handler = Mock()
    widget.move_to_folder_requested.connect(handler)

    folder = PlaylistFolder(id=10, name="Gym", position=0)
    tree = PlaylistTree(
        root_playlists=[Playlist(id=1, name="Inbox", position=0)],
        folders=[PlaylistFolderGroup(folder=folder, playlists=[])],
    )
    widget.populate(tree)

    widget._emit_drop_action(dragged_playlist_id=1, target_kind="folder", target_id=10)

    handler.assert_called_once_with(1, 10)


def test_tree_widget_emits_reorder_folders_for_top_level_folder_drop(qapp):
    widget = PlaylistTreeWidget()
    handler = Mock()
    widget.reorder_folders_requested.connect(handler)

    widget._emit_folder_reorder([20, 10])

    handler.assert_called_once_with([20, 10])
