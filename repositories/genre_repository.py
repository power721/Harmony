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
                    SELECT
                        g.name,
                        COALESCE(
                            (
                                SELECT t.cover_path
                                FROM tracks t
                                WHERE t.genre = g.name
                                  AND t.cover_path IS NOT NULL
                                  AND t.cover_path != ''
                                ORDER BY RANDOM()
                                LIMIT 1
                            ),
                            (
                                SELECT a.cover_path
                                FROM tracks t
                                JOIN albums a ON a.name = t.album
                                WHERE t.genre = g.name
                                  AND a.cover_path IS NOT NULL
                                  AND a.cover_path != ''
                                ORDER BY RANDOM()
                                LIMIT 1
                            ),
                            g.cover_path
                        ) AS cover_path,
                        g.song_count,
                        g.album_count,
                        g.total_duration
                    FROM genres g
                    ORDER BY g.song_count DESC
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

        # Fallback to direct query with aggregate cover lookup
        cursor.execute("""
            SELECT
                t.genre as name,
                (
                    SELECT t2.cover_path
                    FROM tracks t2
                    WHERE t2.genre = t.genre
                      AND t2.cover_path IS NOT NULL
                      AND t2.cover_path != ''
                    ORDER BY RANDOM()
                    LIMIT 1
                ) as track_cover_path,
                (
                    SELECT a.cover_path
                    FROM tracks t3
                    JOIN albums a ON a.name = t3.album
                    WHERE t3.genre = t.genre
                      AND a.cover_path IS NOT NULL
                      AND a.cover_path != ''
                    ORDER BY RANDOM()
                    LIMIT 1
                ) as album_cover_path,
                COUNT(*) as song_count,
                COUNT(DISTINCT t.album) as album_count,
                SUM(t.duration) as total_duration
            FROM tracks t
            WHERE t.genre IS NOT NULL AND t.genre != ''
            GROUP BY t.genre
            ORDER BY song_count DESC
        """)
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
        conn = self._get_connection()
        cursor = conn.cursor()

        # Try to use genres table first
        cursor.execute("SELECT 1 FROM genres LIMIT 1")
        if cursor.fetchone() is not None:
            cursor.execute("""
                SELECT
                    g.name,
                    COALESCE(
                        (
                            SELECT t.cover_path
                            FROM tracks t
                            WHERE t.genre = g.name
                              AND t.cover_path IS NOT NULL
                              AND t.cover_path != ''
                            ORDER BY RANDOM()
                            LIMIT 1
                        ),
                        (
                            SELECT a.cover_path
                            FROM tracks t
                            JOIN albums a ON a.name = t.album
                            WHERE t.genre = g.name
                              AND a.cover_path IS NOT NULL
                              AND a.cover_path != ''
                            ORDER BY RANDOM()
                            LIMIT 1
                        ),
                        g.cover_path
                    ) AS cover_path,
                    g.song_count,
                    g.album_count,
                    g.total_duration
                FROM genres g
                WHERE g.name = ?
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
                (
                    SELECT t2.cover_path
                    FROM tracks t2
                    WHERE t2.genre = t.genre
                      AND t2.cover_path IS NOT NULL
                      AND t2.cover_path != ''
                    ORDER BY RANDOM()
                    LIMIT 1
                ) as track_cover_path,
                (
                    SELECT a.cover_path
                    FROM tracks t3
                    JOIN albums a ON a.name = t3.album
                    WHERE t3.genre = t.genre
                      AND a.cover_path IS NOT NULL
                      AND a.cover_path != ''
                    ORDER BY RANDOM()
                    LIMIT 1
                ) as album_cover_path,
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
                    ORDER BY RANDOM()
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
