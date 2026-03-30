"""
SQLite implementation of GenreRepository.
"""

from typing import List, Optional, TYPE_CHECKING

from domain.genre import Genre
from domain.track import Track
from repositories.base_repository import BaseRepository

if TYPE_CHECKING:
    from infrastructure.database import DatabaseManager


class SqliteGenreRepository(BaseRepository):
    """SQLite implementation of GenreRepository."""

    def __init__(self, db_path: str = "Harmony.db", db_manager: "DatabaseManager" = None):
        super().__init__(db_path, db_manager)

    def get_all(self, use_cache: bool = True) -> List[Genre]:
        """
        Get all genres.

        Args:
            use_cache: If True, use cache table for faster loading

        Returns:
            List of Genre objects with aggregated info, ordered by song_count DESC
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Try to use genres table first
        if use_cache:
            cursor.execute("SELECT 1 FROM genres LIMIT 1")
            if cursor.fetchone() is not None:
                cursor.execute("""
                    SELECT name, cover_path, song_count, album_count, total_duration
                    FROM genres
                    ORDER BY song_count DESC
                """)
                rows = cursor.fetchall()
                return [
                    Genre(
                        name=row["name"] or "",
                        cover_path=row["cover_path"],
                        song_count=row["song_count"] or 0,
                        album_count=row["album_count"] or 0,
                        duration=row["total_duration"] or 0.0,
                    )
                    for row in rows
                ]

        # Fallback to direct query (slower)
        cursor.execute("""
            SELECT
                genre as name,
                COUNT(*) as song_count,
                COUNT(DISTINCT album) as album_count,
                SUM(duration) as total_duration
            FROM tracks
            WHERE genre IS NOT NULL AND genre != ''
            GROUP BY genre
            ORDER BY song_count DESC
        """)
        rows = cursor.fetchall()

        genres = []
        for row in rows:
            genres.append(Genre(
                name=row["name"] or "",
                cover_path=None,
                song_count=row["song_count"] or 0,
                album_count=row["album_count"] or 0,
                duration=row["total_duration"] or 0.0,
            ))
        return genres

    def get_by_name(self, name: str) -> Optional[Genre]:
        """
        Get a specific genre by name.

        Args:
            name: Genre name

        Returns:
            Genre object or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Try to use genres table first
        cursor.execute("SELECT 1 FROM genres LIMIT 1")
        if cursor.fetchone() is not None:
            cursor.execute("""
                SELECT name, cover_path, song_count, album_count, total_duration
                FROM genres
                WHERE name = ?
            """, (name,))
            row = cursor.fetchone()
            if row:
                return Genre(
                    name=row["name"] or "",
                    cover_path=row["cover_path"],
                    song_count=row["song_count"] or 0,
                    album_count=row["album_count"] or 0,
                    duration=row["total_duration"] or 0.0,
                )
            return None

        # Fallback to direct query
        cursor.execute("""
            SELECT
                genre as name,
                COUNT(*) as song_count,
                COUNT(DISTINCT album) as album_count,
                SUM(duration) as total_duration
            FROM tracks
            WHERE genre = ?
            GROUP BY genre
        """, (name,))
        row = cursor.fetchone()
        if not row:
            return None

        return Genre(
            name=row["name"] or "",
            cover_path=None,
            song_count=row["song_count"] or 0,
            album_count=row["album_count"] or 0,
            duration=row["total_duration"] or 0.0,
        )

    def get_tracks(self, name: str) -> List[Track]:
        """
        Get all tracks in a genre.

        Args:
            name: Genre name

        Returns:
            List of Track objects in the genre
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM tracks
            WHERE genre = ?
            ORDER BY id
        """, (name,))

        rows = cursor.fetchall()
        # Need to use the same _row_to_track pattern as track_repository
        from repositories.track_repository import SqliteTrackRepository
        repo = SqliteTrackRepository(db_path=self.db_path, db_manager=self._db_manager)
        return [repo._row_to_track(row) for row in rows]

    def refresh(self) -> bool:
        """
        Refresh the genres table from tracks table.

        Returns:
            True if successful
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Clear genres table
        cursor.execute("DELETE FROM genres")

        # Rebuild from tracks
        cursor.execute("""
            INSERT INTO genres (name, cover_path, song_count, album_count, total_duration)
            SELECT
                genre as name,
                NULL as cover_path,
                COUNT(*) as song_count,
                COUNT(DISTINCT album) as album_count,
                SUM(duration) as total_duration
            FROM tracks
            WHERE genre IS NOT NULL AND genre != ''
            GROUP BY genre
        """)

        conn.commit()
        return True
