"""
QQ Music specific context menus that now live with the plugin implementation.
"""

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QMenu

from .i18n import t
from .runtime_bridge import get_qss


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


class OnlineTrackContextMenu(QObject):
    """Context menu for QQ online tracks. Emits signals for each action."""

    play = Signal(list)
    insert_to_queue = Signal(list)
    add_to_queue = Signal(list)
    add_to_playlist = Signal(list)
    favorite_toggled = Signal(list, bool)
    qq_fav_toggled = Signal(list, bool)
    download = Signal(list)

    def show_menu(self, tracks: list, favorite_mids: set | None = None, parent_widget=None):
        if not tracks:
            return

        menu = QMenu(parent_widget)
        menu.setStyleSheet(get_qss(_CONTEXT_MENU_STYLE))

        action = menu.addAction(t("play"))
        action.triggered.connect(lambda: self.play.emit(tracks))

        action = menu.addAction(t("insert_to_queue"))
        action.triggered.connect(lambda: self.insert_to_queue.emit(tracks))

        action = menu.addAction(t("add_to_queue"))
        action.triggered.connect(lambda: self.add_to_queue.emit(tracks))

        menu.addSeparator()

        all_favorited = False
        if favorite_mids:
            all_favorited = all(
                getattr(track, "mid", None) and track.mid in favorite_mids
                for track in tracks
            )

        action = menu.addAction(
            t("remove_from_favorites") if all_favorited else t("add_to_favorites")
        )
        action.triggered.connect(lambda: self.favorite_toggled.emit(tracks, all_favorited))

        action = menu.addAction(
            t("remove_from_qq_favorites") if all_favorited else t("add_to_qq_favorites")
        )
        action.triggered.connect(lambda: self.qq_fav_toggled.emit(tracks, all_favorited))

        action = menu.addAction(t("add_to_playlist"))
        action.triggered.connect(lambda: self.add_to_playlist.emit(tracks))

        menu.addSeparator()

        action = menu.addAction(t("download"))
        action.triggered.connect(lambda: self.download.emit(tracks))

        menu.exec_(QCursor.pos())
