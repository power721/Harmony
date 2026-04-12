"""
Playlist tree widget for folders and playlists.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QTreeWidget,
    QTreeWidgetItem,
    QTreeWidgetItemIterator,
)

from domain.playlist_folder import PlaylistTree


class PlaylistTreeWidget(QTreeWidget):
    """Tree widget that renders playlist folders and root playlists."""

    FOLDER_PREFIX = "📁 "

    move_to_folder_requested = Signal(int, int)
    move_to_root_requested = Signal(int)
    reorder_root_requested = Signal(list)
    reorder_folder_requested = Signal(int, list)
    reorder_folders_requested = Signal(list)

    NODE_KIND_ROLE = Qt.ItemDataRole.UserRole
    NODE_ID_ROLE = Qt.ItemDataRole.UserRole + 1

    FOLDER_NODE = "folder"
    PLAYLIST_NODE = "playlist"
    ROOT_NODE = "root"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setRootIsDecorated(False)
        self.setItemsExpandable(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragEnabled(True)
        self.viewport().setAcceptDrops(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._dragged_kind: str | None = None
        self._dragged_id: int | None = None
        self._dragged_parent_id: int | None = None

    def populate(self, tree: PlaylistTree) -> None:
        """Populate the tree from a playlist tree model."""
        self.clear()

        for group in tree.folders:
            folder_item = QTreeWidgetItem([self._format_folder_label(group.folder.name)])
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

    @classmethod
    def _format_folder_label(cls, name: str) -> str:
        """Return the display label for a folder node."""
        return f"{cls.FOLDER_PREFIX}{name}"

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
        item = self.find_playlist_item(playlist_id)
        if item is None:
            return False
        parent = item.parent()
        if parent is not None:
            parent.setExpanded(True)
        self.setCurrentItem(item)
        return True

    def find_playlist_item(self, playlist_id: int) -> QTreeWidgetItem | None:
        """Return the tree item for a playlist id."""
        iterator = QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            if (
                item.data(0, self.NODE_KIND_ROLE) == self.PLAYLIST_NODE
                and item.data(0, self.NODE_ID_ROLE) == playlist_id
            ):
                return item
            iterator += 1
        return None

    def startDrag(self, supported_actions):
        """Capture drag metadata before the built-in move runs."""
        item = self.currentItem()
        if item is not None:
            self._dragged_kind = item.data(0, self.NODE_KIND_ROLE)
            self._dragged_id = item.data(0, self.NODE_ID_ROLE)
            parent = item.parent()
            self._dragged_parent_id = (
                parent.data(0, self.NODE_ID_ROLE) if parent is not None else None
            )
        super().startDrag(supported_actions)

    def dropEvent(self, event: QDropEvent):
        """Translate tree moves into higher-level playlist/folder actions."""
        target_item = self.itemAt(event.position().toPoint())
        target_kind = self.ROOT_NODE if target_item is None else target_item.data(
            0, self.NODE_KIND_ROLE
        )
        target_id = None if target_item is None else target_item.data(0, self.NODE_ID_ROLE)

        super().dropEvent(event)

        if self._dragged_kind == self.PLAYLIST_NODE and self._dragged_id is not None:
            playlist_item = self.find_playlist_item(self._dragged_id)
            if playlist_item is None:
                return

            parent = playlist_item.parent()
            if parent is None:
                if self._dragged_parent_id is not None:
                    self.move_to_root_requested.emit(self._dragged_id)
                self.reorder_root_requested.emit(self._root_playlist_ids())
            else:
                folder_id = parent.data(0, self.NODE_ID_ROLE)
                if folder_id is None:
                    return
                if folder_id != self._dragged_parent_id:
                    self._emit_drop_action(self._dragged_id, target_kind, target_id)
                self.reorder_folder_requested.emit(folder_id, self._folder_playlist_ids(folder_id))

        if self._dragged_kind == self.FOLDER_NODE:
            self._emit_folder_reorder(self._folder_ids())

        self._dragged_kind = None
        self._dragged_id = None
        self._dragged_parent_id = None

    def _emit_drop_action(
        self, dragged_playlist_id: int, target_kind: str, target_id: int | None
    ) -> None:
        """Emit the appropriate move action after a drop."""
        if target_kind == self.FOLDER_NODE and target_id is not None:
            self.move_to_folder_requested.emit(dragged_playlist_id, target_id)
        elif target_kind == self.ROOT_NODE:
            self.move_to_root_requested.emit(dragged_playlist_id)

    def _emit_folder_reorder(self, folder_ids: list[int]) -> None:
        """Emit top-level folder reordering."""
        self.reorder_folders_requested.emit(folder_ids)

    def _root_playlist_ids(self) -> list[int]:
        """Return root playlist ids in visual order."""
        ids: list[int] = []
        for index in range(self.topLevelItemCount()):
            item = self.topLevelItem(index)
            if item.data(0, self.NODE_KIND_ROLE) == self.PLAYLIST_NODE:
                item_id = item.data(0, self.NODE_ID_ROLE)
                if item_id is not None:
                    ids.append(item_id)
        return ids

    def _folder_ids(self) -> list[int]:
        """Return folder ids in visual order."""
        ids: list[int] = []
        for index in range(self.topLevelItemCount()):
            item = self.topLevelItem(index)
            if item.data(0, self.NODE_KIND_ROLE) == self.FOLDER_NODE:
                item_id = item.data(0, self.NODE_ID_ROLE)
                if item_id is not None:
                    ids.append(item_id)
        return ids

    def _folder_playlist_ids(self, folder_id: int) -> list[int]:
        """Return child playlist ids for the given folder."""
        for index in range(self.topLevelItemCount()):
            item = self.topLevelItem(index)
            if item.data(0, self.NODE_KIND_ROLE) != self.FOLDER_NODE:
                continue
            if item.data(0, self.NODE_ID_ROLE) != folder_id:
                continue
            ids: list[int] = []
            for child_index in range(item.childCount()):
                child = item.child(child_index)
                child_id = child.data(0, self.NODE_ID_ROLE)
                if child_id is not None:
                    ids.append(child_id)
            return ids
        return []
