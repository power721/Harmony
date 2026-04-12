"""
Playlist tree widget for folders and playlists.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator

from domain.playlist_folder import PlaylistTree


class PlaylistTreeWidget(QTreeWidget):
    """Tree widget that renders playlist folders and root playlists."""

    NODE_KIND_ROLE = Qt.ItemDataRole.UserRole
    NODE_ID_ROLE = Qt.ItemDataRole.UserRole + 1

    FOLDER_NODE = "folder"
    PLAYLIST_NODE = "playlist"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setRootIsDecorated(False)
        self.setItemsExpandable(True)

    def populate(self, tree: PlaylistTree) -> None:
        """Populate the tree from a playlist tree model."""
        self.clear()

        for group in tree.folders:
            folder_item = QTreeWidgetItem([group.folder.name])
            folder_item.setData(0, self.NODE_KIND_ROLE, self.FOLDER_NODE)
            folder_item.setData(0, self.NODE_ID_ROLE, group.folder.id)
            folder_item.setChildIndicatorPolicy(
                QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator
            )
            for playlist in group.playlists:
                child = QTreeWidgetItem([playlist.name])
                child.setData(0, self.NODE_KIND_ROLE, self.PLAYLIST_NODE)
                child.setData(0, self.NODE_ID_ROLE, playlist.id)
                folder_item.addChild(child)
            self.addTopLevelItem(folder_item)

        for playlist in tree.root_playlists:
            item = QTreeWidgetItem([playlist.name])
            item.setData(0, self.NODE_KIND_ROLE, self.PLAYLIST_NODE)
            item.setData(0, self.NODE_ID_ROLE, playlist.id)
            self.addTopLevelItem(item)

    def first_playlist_item(self) -> QTreeWidgetItem | None:
        """Return the first playlist item in tree order."""
        iterator = QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            if item.data(0, self.NODE_KIND_ROLE) == self.PLAYLIST_NODE:
                return item
            iterator += 1
        return None

    def restore_playlist_selection(self, playlist_id: int) -> bool:
        """Select a playlist item if it exists in the current tree."""
        iterator = QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            if (
                item.data(0, self.NODE_KIND_ROLE) == self.PLAYLIST_NODE
                and item.data(0, self.NODE_ID_ROLE) == playlist_id
            ):
                parent = item.parent()
                if parent is not None:
                    parent.setExpanded(True)
                self.setCurrentItem(item)
                return True
            iterator += 1
        return False
