"""
Playlist utility functions for the music player.
"""
import logging
from typing import List, TYPE_CHECKING

from PySide6.QtWidgets import QMessageBox, QDialog

from system.i18n import t

if TYPE_CHECKING:
    from services.library.library_service import LibraryService
    from infrastructure.database import DatabaseManager

logger = logging.getLogger(__name__)


def add_tracks_to_playlist(
    parent,
    library_service: "LibraryService",
    db_manager: "DatabaseManager",
    track_ids: List[int],
    log_prefix: str = ""
) -> bool:
    """
    Add tracks to a playlist with dialog selection.

    This function handles:
    - Showing playlist selection dialog
    - Adding tracks to selected playlist
    - Showing appropriate success/error messages

    Args:
        parent: Parent widget for dialogs
        library_service: LibraryService instance
        db_manager: DatabaseManager instance
        track_ids: List of track IDs to add
        log_prefix: Prefix for log messages

    Returns:
        True if any tracks were added, False otherwise
    """
    from ui.dialogs.add_to_playlist_dialog import AddToPlaylistDialog

    if not track_ids:
        return False

    dialog = AddToPlaylistDialog(library_service, parent)

    # Check if there are playlists
    if not dialog.has_playlists():
        dialog.deleteLater()
        reply = QMessageBox.question(
            parent,
            t("no_playlists"),
            t("no_playlists_message"),
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            if hasattr(parent, "window()") and parent.window():
                parent.window()._nav_playlists.click()
        return False

    # If only one playlist, add directly without showing dialog
    if dialog.has_single_playlist():
        playlist = dialog.get_single_playlist()
        dialog.deleteLater()
        if playlist:
            added_count, duplicate_count = _add_tracks_to_playlist_internal(
                db_manager, playlist.id, track_ids
            )
            _show_result_message(parent, added_count, duplicate_count, playlist.name)
            if log_prefix and added_count > 0:
                logger.info(f"{log_prefix} Added {added_count} tracks to playlist '{playlist.name}'")
            return added_count > 0
        return False

    # Show dialog for user to select playlist
    dialog.set_track_ids(track_ids)

    if dialog.exec() == QDialog.Accepted:
        playlist = dialog.get_selected_playlist()
        dialog.deleteLater()
        if playlist:
            added_count, duplicate_count = _add_tracks_to_playlist_internal(
                db_manager, playlist.id, track_ids
            )
            _show_result_message(parent, added_count, duplicate_count, playlist.name)
            if log_prefix and added_count > 0:
                logger.info(f"{log_prefix} Added {added_count} tracks to playlist '{playlist.name}'")
            return added_count > 0
    else:
        dialog.deleteLater()

    return False


def _add_tracks_to_playlist_internal(
    db_manager: "DatabaseManager",
    playlist_id: int,
    track_ids: List[int]
) -> tuple:
    """
    Internal function to add tracks to a playlist.

    Args:
        db_manager: DatabaseManager instance
        playlist_id: Target playlist ID
        track_ids: List of track IDs to add

    Returns:
        Tuple of (added_count, duplicate_count)
    """
    added_count = 0
    duplicate_count = 0

    for track_id in track_ids:
        if db_manager.add_track_to_playlist(playlist_id, track_id):
            added_count += 1
        else:
            duplicate_count += 1

    return added_count, duplicate_count


def _show_result_message(parent, added_count: int, duplicate_count: int, playlist_name: str):
    """
    Show appropriate result message to user.

    Args:
        parent: Parent widget for dialogs
        added_count: Number of tracks added
        duplicate_count: Number of duplicate tracks
        playlist_name: Name of the playlist
    """
    if duplicate_count == 0:
        msg = t("added_tracks_to_playlist").format(count=added_count, name=playlist_name)
        QMessageBox.information(parent, t("success"), msg)
    elif added_count == 0:
        msg = t("all_tracks_duplicate").format(count=duplicate_count, name=playlist_name)
        QMessageBox.warning(parent, t("duplicate"), msg)
    else:
        msg = t("added_skipped_duplicates").format(added=added_count, duplicates=duplicate_count)
        QMessageBox.information(parent, t("partially_added"), msg)
