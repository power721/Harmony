"""
Reusable context menu classes for track views.
"""

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QMenu

from system.i18n import t


_CONTEXT_MENU_STYLE = """
    QMenu {
        background-color: %background_alt%;
        color: %text%;
        border: 1px solid %border%;
    }
    QMenu::item {
        padding: 8px 20px;
    }
    QMenu::item:selected {
        background-color: %highlight%;
        color: %background%;
    }
    QMenu::item:disabled {
        color: %text_secondary%;
    }
"""


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

    def show_menu(self, tracks: list, favorite_ids: set, parent_widget=None):
        from system.theme import ThemeManager

        if not tracks:
            return

        menu = QMenu(parent_widget)
        menu.setStyleSheet(ThemeManager.instance().get_qss(_CONTEXT_MENU_STYLE))

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

        if len(tracks) == 1 and tracks[0].path:
            a = menu.addAction(t("open_file_location"))
            a.triggered.connect(lambda: self.open_file_location.emit(tracks[0]))

        menu.addSeparator()

        a = menu.addAction(t("remove_from_library"))
        a.triggered.connect(lambda: self.remove_from_library.emit(tracks))

        if len(tracks) == 1 and tracks[0].path:
            a = menu.addAction(t("delete_file"))
            a.triggered.connect(lambda: self.delete_file.emit(tracks))

        menu.exec_(QCursor.pos())


class OnlineTrackContextMenu(QObject):
    """Context menu for online tracks. Emits signals for each action."""

    play = Signal(list)
    insert_to_queue = Signal(list)
    add_to_queue = Signal(list)
    add_to_playlist = Signal(list)
    add_to_favorites = Signal(list)
    download = Signal(list)

    def show_menu(self, tracks: list, parent_widget=None):
        from system.theme import ThemeManager

        if not tracks:
            return

        menu = QMenu(parent_widget)
        menu.setStyleSheet(ThemeManager.instance().get_qss(_CONTEXT_MENU_STYLE))

        a = menu.addAction(t("play"))
        a.triggered.connect(lambda: self.play.emit(tracks))

        a = menu.addAction(t("insert_to_queue"))
        a.triggered.connect(lambda: self.insert_to_queue.emit(tracks))

        a = menu.addAction(t("add_to_queue"))
        a.triggered.connect(lambda: self.add_to_queue.emit(tracks))

        menu.addSeparator()

        a = menu.addAction(t("add_to_favorites"))
        a.triggered.connect(lambda: self.add_to_favorites.emit(tracks))

        a = menu.addAction(t("add_to_playlist"))
        a.triggered.connect(lambda: self.add_to_playlist.emit(tracks))

        menu.addSeparator()

        a = menu.addAction(t("download"))
        a.triggered.connect(lambda: self.download.emit(tracks))

        menu.exec_(QCursor.pos())
