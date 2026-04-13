"""
SQLite implementation of PlaylistRepository.
"""

import sqlite3
import time
from typing import List, Optional, TYPE_CHECKING

from domain.playlist import Playlist
from domain.playlist_folder import PlaylistFolder, PlaylistFolderGroup, PlaylistTree
from domain.track import Track, TrackId
from repositories.base_repository import BaseRepository

if TYPE_CHECKING:
    from infrastructure.database import DatabaseManager


class SqlitePlaylistRepository(BaseRepository):
    """SQLite implementation of PlaylistRepository."""

    def __init__(self, db_path: str = "Harmony.db", db_manager: "DatabaseManager | None" = None):
        super().__init__(db_path, db_manager)
        # Import here to avoid circular import
        from repositories.track_repository import SqliteTrackRepository
        self._track_repo = SqliteTrackRepository(db_path, db_manager)

    @staticmethod
    def _row_to_playlist(row) -> Playlist:
        """Map a sqlite row to a Playlist."""
        return Playlist(
            id=row["id"],
            name=row["name"],
            folder_id=row["folder_id"] if "folder_id" in row.keys() else None,
            position=row["position"] if "position" in row.keys() else 0,
        )

    @staticmethod
    def _row_to_folder(row) -> PlaylistFolder:
        """Map a sqlite row to a PlaylistFolder."""
        return PlaylistFolder(
            id=row["id"],
            name=row["name"],
            position=row["position"],
        )

    def get_by_id(self, playlist_id: int) -> Optional[Playlist]:
        """Get a playlist by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM playlists WHERE id = ?", (playlist_id,))
        row = cursor.fetchone()
        if row:
            return self._row_to_playlist(row)
        return None

    def get_all(self) -> List[Playlist]:
        """Get all playlists."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM playlists ORDER BY position, id")
        rows = cursor.fetchall()
        return [self._row_to_playlist(row) for row in rows]

    def get_tracks(self, playlist_id: int) -> List[Track]:
        """Get all tracks in a playlist."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
                       SELECT t.*
                       FROM tracks t
                                JOIN playlist_items pi ON t.id = pi.track_id
                       WHERE pi.playlist_id = ?
                       ORDER BY pi.position
                       """, (playlist_id,))
        rows = cursor.fetchall()
        return [self._track_repo._row_to_track(row) for row in rows]

    def add(self, playlist: Playlist) -> int:
        """Add a new playlist and return its ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO playlists (name, folder_id, position) VALUES (?, ?, ?)",
            (playlist.name, playlist.folder_id, playlist.position),
        )
        conn.commit()
        return self._require_lastrowid(cursor)

    def update(self, playlist: Playlist) -> bool:
        """Update an existing playlist."""
        if not playlist.id:
            return False
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE playlists SET name = ? WHERE id = ?", (playlist.name, playlist.id))
        conn.commit()
        return cursor.rowcount > 0

    def create_folder(self, name: str) -> int:
        """Create a playlist folder."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM playlist_folders")
        position = int(cursor.fetchone()[0])
        cursor.execute(
            "INSERT INTO playlist_folders (name, position) VALUES (?, ?)",
            (name, position),
        )
        conn.commit()
        return self._require_lastrowid(cursor)

    def get_folder(self, folder_id: int) -> Optional[PlaylistFolder]:
        """Get a folder by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM playlist_folders WHERE id = ?", (folder_id,))
        row = cursor.fetchone()
        return self._row_to_folder(row) if row else None

    def get_folder_by_name(self, name: str) -> Optional[PlaylistFolder]:
        """Get a folder by name using case-insensitive lookup."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM playlist_folders WHERE name = ? COLLATE NOCASE",
            (name,),
        )
        row = cursor.fetchone()
        return self._row_to_folder(row) if row else None

    def get_all_folders(self) -> list[PlaylistFolder]:
        """Get all folders ordered by position."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM playlist_folders ORDER BY position, id")
        return [self._row_to_folder(row) for row in cursor.fetchall()]

    def rename_folder(self, folder_id: int, name: str) -> bool:
        """Rename a folder."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE playlist_folders SET name = ? WHERE id = ?", (name, folder_id))
        conn.commit()
        return cursor.rowcount > 0

    def get_playlist(self, playlist_id: int) -> Optional[Playlist]:
        """Compatibility wrapper for playlist lookup."""
        return self.get_by_id(playlist_id)

    def get_playlist_tree(self) -> PlaylistTree:
        """Load folders and root playlists as a tree."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM playlist_folders ORDER BY position, id")
        folders = [PlaylistFolderGroup(folder=self._row_to_folder(row)) for row in cursor.fetchall()]
        folder_map = {group.folder.id: group for group in folders}

        cursor.execute(
            """
            SELECT * FROM playlists
            ORDER BY
                CASE WHEN folder_id IS NULL THEN 1 ELSE 0 END,
                COALESCE(folder_id, -1),
                position,
                id
            """
        )
        root_playlists: list[Playlist] = []
        for row in cursor.fetchall():
            playlist = self._row_to_playlist(row)
            if playlist.folder_id is None:
                root_playlists.append(playlist)
            elif playlist.folder_id in folder_map:
                folder_map[playlist.folder_id].playlists.append(playlist)

        return PlaylistTree(root_playlists=root_playlists, folders=folders)

    def _next_playlist_position(self, cursor, folder_id: int | None) -> int:
        """Return the next available position inside the target container."""
        if folder_id is None:
            cursor.execute(
                "SELECT COALESCE(MAX(position), -1) + 1 FROM playlists WHERE folder_id IS NULL"
            )
        else:
            cursor.execute(
                "SELECT COALESCE(MAX(position), -1) + 1 FROM playlists WHERE folder_id = ?",
                (folder_id,),
            )
        return int(cursor.fetchone()[0])

    def delete_folder(self, folder_id: int) -> bool:
        """Delete a folder and move contained playlists back to the root."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT id FROM playlists WHERE folder_id = ? ORDER BY position, id",
                (folder_id,),
            )
            playlist_ids = [row["id"] if hasattr(row, "keys") else row[0] for row in cursor.fetchall()]
            next_root_position = self._next_playlist_position(cursor, None)

            for offset, playlist_id in enumerate(playlist_ids):
                cursor.execute(
                    "UPDATE playlists SET folder_id = NULL, position = ? WHERE id = ?",
                    (next_root_position + offset, playlist_id),
                )

            cursor.execute("DELETE FROM playlist_folders WHERE id = ?", (folder_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
            return deleted
        except sqlite3.DatabaseError:
            conn.rollback()
            return False

    def move_playlist_to_folder(self, playlist_id: int, folder_id: int) -> bool:
        """Move a playlist into a folder."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            new_position = self._next_playlist_position(cursor, folder_id)
            cursor.execute(
                "UPDATE playlists SET folder_id = ?, position = ? WHERE id = ?",
                (folder_id, new_position, playlist_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.DatabaseError:
            conn.rollback()
            return False

    def move_playlist_to_root(self, playlist_id: int) -> bool:
        """Move a playlist back to the root container."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            new_position = self._next_playlist_position(cursor, None)
            cursor.execute(
                "UPDATE playlists SET folder_id = NULL, position = ? WHERE id = ?",
                (new_position, playlist_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.DatabaseError:
            conn.rollback()
            return False

    def reorder_root_playlists(self, playlist_ids: list[int]) -> bool:
        """Persist a root-playlist order."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            for position, playlist_id in enumerate(playlist_ids):
                cursor.execute(
                    "UPDATE playlists SET folder_id = NULL, position = ? WHERE id = ?",
                    (position, playlist_id),
                )
            conn.commit()
            return True
        except sqlite3.DatabaseError:
            conn.rollback()
            return False

    def reorder_folder_playlists(self, folder_id: int, playlist_ids: list[int]) -> bool:
        """Persist the order of playlists within a folder."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            for position, playlist_id in enumerate(playlist_ids):
                cursor.execute(
                    "UPDATE playlists SET folder_id = ?, position = ? WHERE id = ?",
                    (folder_id, position, playlist_id),
                )
            conn.commit()
            return True
        except sqlite3.DatabaseError:
            conn.rollback()
            return False

    def reorder_folders(self, folder_ids: list[int]) -> bool:
        """Persist top-level folder ordering."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            for position, folder_id in enumerate(folder_ids):
                cursor.execute(
                    "UPDATE playlist_folders SET position = ? WHERE id = ?",
                    (position, folder_id),
                )
            conn.commit()
            return True
        except sqlite3.DatabaseError:
            conn.rollback()
            return False

    def delete(self, playlist_id: int) -> bool:
        """Delete a playlist by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # Delete playlist items first
            cursor.execute("DELETE FROM playlist_items WHERE playlist_id = ?", (playlist_id,))
            # Delete playlist
            cursor.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.DatabaseError:
            conn.rollback()
            return False

    def add_track(self, playlist_id: int, track_id: TrackId) -> bool:
        """Add a track to a playlist.

        Returns True if track was added, False if it already exists.
        """
        max_retries = 3
        retry_delay = 0.1
        conn: sqlite3.Connection | None = None

        for attempt in range(max_retries):
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                # Use atomic INSERT with subquery to avoid race condition
                cursor.execute("""
                               INSERT OR IGNORE INTO playlist_items (playlist_id, track_id, position)
                               SELECT ?, ?, COALESCE(MAX(position), -1) + 1
                               FROM playlist_items
                               WHERE playlist_id = ?
                               """, (playlist_id, track_id, playlist_id))
                conn.commit()
                return cursor.rowcount > 0
            except sqlite3.OperationalError as e:
                if conn is not None:
                    conn.rollback()
                if "locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    return False
            except sqlite3.DatabaseError:
                if conn is not None:
                    conn.rollback()
                return False
        return False

    def remove_track(self, playlist_id: int, track_id: TrackId) -> bool:
        """Remove a track from a playlist."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
                       DELETE
                       FROM playlist_items
                       WHERE playlist_id = ?
                         AND track_id = ?
                       """, (playlist_id, track_id))
        conn.commit()
        return cursor.rowcount > 0
