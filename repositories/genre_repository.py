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
                t.genre as name,
                (SELECT t2.cover_path FROM tracks t2
                 WHERE t2.genre = t.genre AND t2.cover_path IS NOT NULL
                 LIMIT 1) as cover_path,
                COUNT(*) as song_count,
                COUNT(DISTINCT t.album) as album_count,
                SUM(t.duration) as total_duration
            FROM tracks t
            WHERE t.genre IS NOT NULL AND t.genre != ''
            GROUP BY t.genre
            ORDER BY song_count DESC
        """)
        rows = cursor.fetchall()

        genres = []
        for row in rows:
            genres.append(Genre(
                name=row["name"] or "",
                cover_path=row["cover_path"],
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
                t.genre as name,
                (SELECT t2.cover_path FROM tracks t2
                 WHERE t2.genre = t.genre AND t2.cover_path IS NOT NULL
                 LIMIT 1) as cover_path,
                COUNT(*) as song_count,
                COUNT(DISTINCT t.album) as album_count,
                SUM(t.duration) as total_duration
            FROM tracks t
            WHERE t.genre = ?
            GROUP BY t.genre
        """, (name,))
        row = cursor.fetchone()
        if not row:
            return None

        return Genre(
            name=row["name"] or "",
            cover_path=row["cover_path"],
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

        # Rebuild from tracks with cover_path from first track
        cursor.execute("""
            INSERT INTO genres (name, cover_path, song_count, album_count, total_duration)
            SELECT
                genre as name,
                (SELECT cover_path FROM tracks t2
                 WHERE t2.genre = t.genre
                 AND t2.cover_path IS NOT NULL
                 LIMIT 1) as cover_path,
                COUNT(*) as song_count,
                COUNT(DISTINCT album) as album_count,
                SUM(duration) as total_duration
            FROM tracks t
            WHERE genre IS NOT NULL AND genre != ''
            GROUP BY genre
        """)

        conn.commit()
        return True

    def fix_covers(self) -> int:
        """
        Fix genre covers by finding tracks with covers for genres without covers.

        Returns:
            Number of genres fixed
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Get genres without covers that have tracks with covers
        cursor.execute("""
            SELECT g.name
            FROM genres g
            WHERE g.cover_path IS NULL
            AND EXISTS (
                SELECT 1 FROM tracks t
                WHERE t.genre = g.name AND t.cover_path IS NOT NULL
                LIMIT 1
            )
        """)
        genres = [row["name"] for row in cursor.fetchall()]

        fixed = 0
        for genre_name in genres:
            cursor.execute("""
                SELECT cover_path FROM tracks
                WHERE genre = ? AND cover_path IS NOT NULL
                LIMIT 1
            """, (genre_name,))
            row = cursor.fetchone()
            if row and row["cover_path"]:
                cursor.execute("""
                    UPDATE genres SET cover_path = ? WHERE name = ?
                """, (row["cover_path"], genre_name))
                fixed += 1

        conn.commit()
        return fixed
