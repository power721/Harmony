"""
SQLite implementation of GenreRepository.
"""

import sqlite3
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

    @staticmethod
    def _genre_cover_ctes() -> str:
        """Common CTEs for first-cover lookups without correlated subqueries."""
        return """
            WITH track_cover AS (
                SELECT
                    genre,
                    cover_path,
                    ROW_NUMBER() OVER (PARTITION BY genre ORDER BY id) AS row_num
                FROM tracks
                WHERE genre IS NOT NULL
                  AND genre != ''
                  AND cover_path IS NOT NULL
                  AND cover_path != ''
            ),
            album_cover AS (
                SELECT
                    t.genre,
                    a.cover_path,
                    ROW_NUMBER() OVER (PARTITION BY t.genre ORDER BY t.id) AS row_num
                FROM tracks t
                JOIN albums a ON a.name = t.album
                WHERE t.genre IS NOT NULL
                  AND t.genre != ''
                  AND a.cover_path IS NOT NULL
                  AND a.cover_path != ''
            )
        """

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
        if use_cache and self._table_exists("genres"):
                cursor.execute(
                    self._genre_cover_ctes()
                    + """
                    SELECT
                        g.name,
                        COALESCE(tc.cover_path, ac.cover_path, g.cover_path) AS cover_path,
                        g.song_count,
                        g.album_count,
                        g.total_duration
                    FROM genres g
                    LEFT JOIN track_cover tc ON tc.genre = g.name AND tc.row_num = 1
                    LEFT JOIN album_cover ac ON ac.genre = g.name AND ac.row_num = 1
                    ORDER BY g.song_count DESC
                    """
                )
                rows = cursor.fetchall()
                if rows:
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

        # Fallback to direct query with aggregate cover lookup
        cursor.execute(
            self._genre_cover_ctes()
            + """
            , genre_stats AS (
                SELECT
                    genre AS name,
                    COUNT(*) AS song_count,
                    COUNT(DISTINCT album) AS album_count,
                    SUM(duration) AS total_duration
                FROM tracks
                WHERE genre IS NOT NULL AND genre != ''
                GROUP BY genre
            )
            SELECT
                gs.name,
                tc.cover_path AS track_cover_path,
                ac.cover_path AS album_cover_path,
                gs.song_count,
                gs.album_count,
                gs.total_duration
            FROM genre_stats gs
            LEFT JOIN track_cover tc ON tc.genre = gs.name AND tc.row_num = 1
            LEFT JOIN album_cover ac ON ac.genre = gs.name AND ac.row_num = 1
            ORDER BY gs.song_count DESC
            """
        )
        rows = cursor.fetchall()

        return [Genre(
                name=row["name"] or "",
                cover_path=row["track_cover_path"] or row["album_cover_path"],
                song_count=row["song_count"] or 0,
                album_count=row["album_count"] or 0,
                duration=row["total_duration"] or 0.0,
            ) for row in rows]

    def get_by_name(self, name: str) -> Optional[Genre]:
        """
        Get a specific genre by name.

        Args:
            name: Genre name

        Returns:
            Genre object or None if not found
        """
        name = str(name or "").strip()
        if not name:
            return None

        conn = self._get_connection()
        cursor = conn.cursor()

        # Try to use genres table first
        if self._table_exists("genres"):
            cursor.execute(
                self._genre_cover_ctes()
                + """
                SELECT
                    g.name,
                    COALESCE(tc.cover_path, ac.cover_path, g.cover_path) AS cover_path,
                    g.song_count,
                    g.album_count,
                    g.total_duration
                FROM genres g
                LEFT JOIN track_cover tc ON tc.genre = g.name AND tc.row_num = 1
                LEFT JOIN album_cover ac ON ac.genre = g.name AND ac.row_num = 1
                WHERE g.name = ?
                """,
                (name,),
            )
            row = cursor.fetchone()
            if row:
                return Genre(
                    name=row["name"] or "",
                    cover_path=row["cover_path"],
                    song_count=row["song_count"] or 0,
                    album_count=row["album_count"] or 0,
                    duration=row["total_duration"] or 0.0,
                )

        # Fallback to direct query
        cursor.execute(
            self._genre_cover_ctes()
            + """
            , genre_stats AS (
                SELECT
                    genre AS name,
                    COUNT(*) AS song_count,
                    COUNT(DISTINCT album) AS album_count,
                    SUM(duration) AS total_duration
                FROM tracks
                WHERE genre = ?
                GROUP BY genre
            )
            SELECT
                gs.name,
                tc.cover_path AS track_cover_path,
                ac.cover_path AS album_cover_path,
                gs.song_count,
                gs.album_count,
                gs.total_duration
            FROM genre_stats gs
            LEFT JOIN track_cover tc ON tc.genre = gs.name AND tc.row_num = 1
            LEFT JOIN album_cover ac ON ac.genre = gs.name AND ac.row_num = 1
            """,
            (name,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        return Genre(
            name=row["name"] or "",
            cover_path=row["track_cover_path"] or row["album_cover_path"],
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

        try:
            # Clear genres table
            cursor.execute("DELETE FROM genres")

            # Rebuild from tracks with aggregate cover lookup
            cursor.execute("""
                INSERT INTO genres (name, cover_path, song_count, album_count, total_duration)
                SELECT
                    genre as name,
                    (
                        SELECT t2.cover_path
                        FROM tracks t2
                        WHERE t2.genre = t.genre
                          AND t2.cover_path IS NOT NULL
                          AND t2.cover_path != ''
                        ORDER BY t2.id
                        LIMIT 1
                    ) as cover_path,
                    COUNT(*) as song_count,
                    COUNT(DISTINCT album) as album_count,
                    SUM(duration) as total_duration
                FROM tracks t
                WHERE genre IS NOT NULL AND genre != ''
                GROUP BY genre
            """)

            conn.commit()
            return True
        except sqlite3.DatabaseError:
            conn.rollback()
            return False

    def refresh_genre(self, genre_name: str) -> bool:
        """Refresh a single genre cache row from tracks."""
        if not genre_name:
            return False

        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT cover_path FROM genres WHERE name = ?", (genre_name,))
            existing = cursor.fetchone()
            existing_cover = existing["cover_path"] if existing else None

            cursor.execute(
                """
                SELECT
                    ? as name,
                    (
                        SELECT t2.cover_path
                        FROM tracks t2
                        WHERE t2.genre = ?
                          AND t2.cover_path IS NOT NULL
                          AND t2.cover_path != ''
                        ORDER BY t2.id
                        LIMIT 1
                    ) as cover_path,
                    COUNT(*) as song_count,
                    COUNT(DISTINCT album) as album_count,
                    SUM(duration) as total_duration
                FROM tracks
                WHERE genre = ?
                """,
                (genre_name, genre_name, genre_name),
            )
            row = cursor.fetchone()
            if not row or not row["song_count"]:
                return False

            cursor.execute("DELETE FROM genres WHERE name = ?", (genre_name,))
            cursor.execute(
                """
                INSERT INTO genres (name, cover_path, song_count, album_count, total_duration)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    row["name"],
                    row["cover_path"] or existing_cover,
                    row["song_count"] or 0,
                    row["album_count"] or 0,
                    row["total_duration"] or 0.0,
                ),
            )
            conn.commit()
            return True
        except sqlite3.DatabaseError:
            conn.rollback()
            return False

    def delete_if_empty(self, genre_name: str) -> bool:
        """Delete a cached genre row when no source tracks remain."""
        if not genre_name:
            return False

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM tracks WHERE genre = ? LIMIT 1", (genre_name,))
        if cursor.fetchone() is not None:
            return False

        cursor.execute("DELETE FROM genres WHERE name = ?", (genre_name,))
        conn.commit()
        return cursor.rowcount > 0

    def fix_covers(self) -> int:
        """
        Fix genre covers by finding tracks with covers for genres without covers.

        Returns:
            Number of genres fixed
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE genres SET cover_path = (
                SELECT cover_path FROM tracks
                WHERE genre = genres.name AND cover_path IS NOT NULL
                LIMIT 1
            )
            WHERE cover_path IS NULL
            AND EXISTS (
                SELECT 1 FROM tracks
                WHERE genre = genres.name AND cover_path IS NOT NULL
                LIMIT 1
            )
        """)
        fixed = cursor.rowcount

        conn.commit()
        return fixed

    def update_cover_path(self, genre_name: str, cover_path: str) -> bool:
        """
        Update cover path for a genre.

        Args:
            genre_name: Genre name
            cover_path: Cover path or URL

        Returns:
            True if a row was updated
        """
        if not genre_name or not cover_path:
            return False

        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE genres
                SET cover_path = ?, updated_at = CURRENT_TIMESTAMP
                WHERE name = ?
                """,
                (cover_path, genre_name),
            )
        except Exception as e:
            # Backward compatibility: older databases may not have genres.updated_at.
            if "no such column: updated_at" not in str(e):
                raise
            cursor.execute(
                """
                UPDATE genres
                SET cover_path = ?
                WHERE name = ?
                """,
                (cover_path, genre_name),
            )
        conn.commit()
        return cursor.rowcount > 0
