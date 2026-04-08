"""
SQLite implementation of FavoriteRepository.
"""

from typing import List, TYPE_CHECKING

from domain.track import Track, TrackId
from repositories.base_repository import BaseRepository

if TYPE_CHECKING:
    from infrastructure.database import DatabaseManager


class SqliteFavoriteRepository(BaseRepository):
    """SQLite implementation of FavoriteRepository."""

    def __init__(self, db_path: str = "Harmony.db", db_manager: "DatabaseManager" = None):
        super().__init__(db_path, db_manager)
        # Import here to avoid circular import
        from repositories.track_repository import SqliteTrackRepository
        self._track_repo = SqliteTrackRepository(db_path, db_manager)

    @staticmethod
    def _normalize_online_provider_id(value: str | None) -> str | None:
        normalized = str(value or "").strip()
        if not normalized or normalized.lower() == "online":
            return None
        return normalized

    def is_favorite(
        self,
        track_id: TrackId = None,
        cloud_file_id: str = None,
        online_provider_id: str | None = None,
    ) -> bool:
        """
        Check if a track or cloud file is favorited.

        Args:
            track_id: Local track ID
            cloud_file_id: Cloud file ID

        Returns:
            True if favorited, False otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        if track_id is not None:
            cursor.execute(
                "SELECT 1 FROM favorites WHERE track_id = ? LIMIT 1",
                (track_id,)
            )
        elif cloud_file_id is not None:
            normalized_provider_id = self._normalize_online_provider_id(online_provider_id)
            if normalized_provider_id is None:
                cursor.execute(
                    "SELECT 1 FROM favorites WHERE cloud_file_id = ? AND online_provider_id IS NULL LIMIT 1",
                    (cloud_file_id,),
                )
            else:
                cursor.execute(
                    "SELECT 1 FROM favorites WHERE cloud_file_id = ? AND online_provider_id = ? LIMIT 1",
                    (cloud_file_id, normalized_provider_id),
                )
        else:
            return False

        return cursor.fetchone() is not None

    def get_all_favorite_track_ids(self) -> set:
        """
        Get all favorite local track IDs as a set for O(1) lookup.

        Returns:
            Set of track IDs that are favorited
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT track_id FROM favorites WHERE track_id IS NOT NULL")
        return {row["track_id"] for row in cursor.fetchall()}

    def add_favorite(
        self,
        track_id: TrackId = None,
        cloud_file_id: str = None,
        cloud_account_id: int = None,
        online_provider_id: str | None = None,
    ) -> bool:
        """
        Add a track or cloud file to favorites.

        Args:
            track_id: Local track ID
            cloud_file_id: Cloud file ID
            cloud_account_id: Cloud account ID (for cloud files)

        Returns:
            True if added successfully, False if already exists
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Use INSERT OR IGNORE with partial unique indexes for atomic dedup
        if track_id is None and cloud_file_id is None:
            return False

        normalized_provider_id = self._normalize_online_provider_id(online_provider_id)
        cursor.execute(
            """
            INSERT OR IGNORE INTO favorites
            (track_id, cloud_file_id, online_provider_id, cloud_account_id)
            VALUES (?, ?, ?, ?)
            """,
            (track_id, cloud_file_id, normalized_provider_id, cloud_account_id)
        )
        if cursor.rowcount == 0:
            return False  # Already exists
        conn.commit()
        return True

    def remove_favorite(
        self,
        track_id: TrackId = None,
        cloud_file_id: str = None,
        online_provider_id: str | None = None,
    ) -> bool:
        """
        Remove a track or cloud file from favorites.

        Args:
            track_id: Local track ID
            cloud_file_id: Cloud file ID

        Returns:
            True if removed, False if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        if track_id is not None:
            cursor.execute(
                "DELETE FROM favorites WHERE track_id = ?",
                (track_id,)
            )
        elif cloud_file_id is not None:
            normalized_provider_id = self._normalize_online_provider_id(online_provider_id)
            if normalized_provider_id is None:
                cursor.execute(
                    "DELETE FROM favorites WHERE cloud_file_id = ? AND online_provider_id IS NULL",
                    (cloud_file_id,),
                )
            else:
                cursor.execute(
                    "DELETE FROM favorites WHERE cloud_file_id = ? AND online_provider_id = ?",
                    (cloud_file_id, normalized_provider_id),
                )
        else:
            return False

        conn.commit()
        return cursor.rowcount > 0

    def get_favorites(self) -> List[Track]:
        """
        Get all favorite tracks (local tracks and downloaded cloud files).

        Returns:
            List of Track objects
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.*
            FROM favorites f
            JOIN tracks t ON f.track_id = t.id
            ORDER BY f.id DESC
        """)
        rows = cursor.fetchall()
        return [self._track_repo._row_to_track(row) for row in rows]

    def get_favorites_with_cloud(self) -> List[dict]:
        """
        Get all favorites including local tracks and undownloaded cloud files.

        Returns:
            List of dicts with track/cloud file info
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                f.id as fav_id,
                f.track_id,
                f.cloud_file_id,
                f.online_provider_id,
                f.cloud_account_id,
                t.id,
                t.path,
                t.title,
                t.artist,
                t.album,
                t.genre,
                t.duration,
                t.source,
                t.cover_path
            FROM favorites f
            LEFT JOIN tracks t ON f.track_id = t.id
            ORDER BY f.id DESC
        """)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
