"""
Reusable context menu classes for track views.
"""

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QMenu

from domain.track import TrackSource
from plugins.builtin.qqmusic.lib.context_menus import OnlineTrackContextMenu
from system.i18n import t


class LocalTrackContextMenu(QObject):
    """Context menu for local tracks. Emits signals for each action."""

    play = Signal(list)
    insert_to_queue = Signal(list)
    add_to_queue = Signal(list)
    add_to_playlist = Signal(list)
    favorite_toggled = Signal(list, bool)  # (tracks, all_favorited)
    edit_info = Signal(object)
    download_cover = Signal(object)
    open_file_location = Signal(object)
    remove_from_library = Signal(list)
    delete_file = Signal(list)
    redownload = Signal(object)  # Track (QQ Music re-download)

    def build_menu(self, tracks: list, favorite_ids: set, parent_widget=None):
        """Build and return the context menu (without showing)."""
        if not tracks:
            return None

        menu = QMenu(parent_widget)

        all_favorited = all(
            getattr(track, 'id', None) and track.id in favorite_ids
            for track in tracks
        )

        a = menu.addAction(t("play"))
        a.triggered.connect(lambda: self.play.emit(tracks))

        a = menu.addAction(t("insert_to_queue"))
        a.triggered.connect(lambda: self.insert_to_queue.emit(tracks))

        a = menu.addAction(t("add_to_queue"))
        a.triggered.connect(lambda: self.add_to_queue.emit(tracks))

        menu.addSeparator()

        a = menu.addAction(t("add_to_playlist"))
        a.triggered.connect(lambda: self.add_to_playlist.emit(tracks))

        if all_favorited:
            a = menu.addAction(t("remove_from_favorites"))
        else:
            a = menu.addAction(t("add_to_favorites"))
        a.triggered.connect(lambda: self.favorite_toggled.emit(tracks, all_favorited))

        menu.addSeparator()

        if len(tracks) == 1:
            a = menu.addAction(t("edit_media_info"))
            a.triggered.connect(lambda: self.edit_info.emit(tracks[0]))

            a = menu.addAction(t("download_cover_manual"))
            a.triggered.connect(lambda: self.download_cover.emit(tracks[0]))

            # Re-download for QQ Music
            if tracks[0].source == TrackSource.QQ:
                a = menu.addAction(t("redownload"))
                a.triggered.connect(lambda: self.redownload.emit(tracks[0]))

        if len(tracks) == 1 and tracks[0].path:
            a = menu.addAction(t("open_file_location"))
            a.triggered.connect(lambda: self.open_file_location.emit(tracks[0]))

        menu.addSeparator()

        a = menu.addAction(t("remove_from_library"))
        a.triggered.connect(lambda: self.remove_from_library.emit(tracks))

        if len(tracks) == 1 and tracks[0].path:
            a = menu.addAction(t("delete_file"))
            a.triggered.connect(lambda: self.delete_file.emit(tracks))

        return menu

    def show_menu(self, tracks: list, favorite_ids: set, parent_widget=None):
        """Build and show the context menu."""
        menu = self.build_menu(tracks, favorite_ids, parent_widget)
        if menu:
            menu.exec_(QCursor.pos())


class PlaylistTrackContextMenu(LocalTrackContextMenu):
    """Context menu for playlist tracks. Extends local track menu with remove from playlist."""

    remove_from_playlist = Signal(list)

    def show_menu(self, tracks: list, favorite_ids: set, parent_widget=None):
        menu = self.build_menu(tracks, favorite_ids, parent_widget)
        if not menu:
            return

        menu.addSeparator()

        a = menu.addAction(t("remove_from_playlist"))
        a.triggered.connect(lambda: self.remove_from_playlist.emit(tracks))

        menu.exec_(QCursor.pos())
