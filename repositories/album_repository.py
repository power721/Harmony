"""
SQLite implementation of AlbumRepository.
"""

from typing import List, Optional, TYPE_CHECKING

from domain.album import Album
from repositories.base_repository import BaseRepository

if TYPE_CHECKING:
    from infrastructure.database import DatabaseManager


class SqliteAlbumRepository(BaseRepository):
    """SQLite implementation of AlbumRepository."""

    def __init__(self, db_path: str = "Harmony.db", db_manager: "DatabaseManager" = None):
        super().__init__(db_path, db_manager)

    def get_all(self, use_cache: bool = True) -> List[Album]:
        """
        Get all albums.

        Args:
            use_cache: If True, use cache table for faster loading

        Returns:
            List of Album objects with aggregated info
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Try to use albums table first
        if use_cache:
            cursor.execute("SELECT 1 FROM albums LIMIT 1")
            if cursor.fetchone() is not None:
                cursor.execute("""
                    SELECT name, artist, cover_path, song_count, total_duration
                    FROM albums
                    ORDER BY song_count DESC
                """)
                rows = cursor.fetchall()
                return [
                    Album(
                        name=row["name"] or "",
                        artist=row["artist"] or "",
                        cover_path=row["cover_path"],
                        song_count=row["song_count"] or 0,
                        duration=row["total_duration"] or 0.0,
                    )
                    for row in rows
                ]

        # Fallback to direct query (slower)
        cursor.execute("""
            SELECT
                album as name,
                artist,
                cover_path,
                COUNT(*) as song_count,
                SUM(duration) as total_duration
            FROM tracks
            WHERE album IS NOT NULL AND album != ''
            GROUP BY album, artist
            ORDER BY song_count DESC
        """)
        rows = cursor.fetchall()

        return [
            Album(
                name=row["name"] or "",
                artist=row["artist"] or "",
                cover_path=row["cover_path"],
                song_count=row["song_count"] or 0,
                duration=row["total_duration"] or 0.0,
            )
            for row in rows
        ]

    def get_by_name(self, album_name: str, artist: str = None) -> Optional[Album]:
        """
        Get a specific album by name and optionally artist.

        Args:
            album_name: Album name
            artist: Artist name (optional, but recommended for unique identification)

        Returns:
            Album object or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Try to use albums table first
        cursor.execute("SELECT 1 FROM albums LIMIT 1")
        if cursor.fetchone() is not None:
            if artist:
                cursor.execute("""
                    SELECT name, artist, cover_path, song_count, total_duration
                    FROM albums
                    WHERE name = ? AND artist = ?
                """, (album_name, artist))
            else:
                cursor.execute("""
                    SELECT name, artist, cover_path, song_count, total_duration
                    FROM albums
                    WHERE name = ?
                """, (album_name,))
            row = cursor.fetchone()
            if row:
                return Album(
                    name=row["name"] or "",
                    artist=row["artist"] or "",
                    cover_path=row["cover_path"],
                    song_count=row["song_count"] or 0,
                    duration=row["total_duration"] or 0.0,
                )
            return None

        # Fallback to direct query
        if artist:
            cursor.execute("""
                SELECT
                    album as name,
                    artist,
                    COUNT(*) as song_count,
                    SUM(duration) as total_duration
                FROM tracks
                WHERE album = ? AND artist = ?
                GROUP BY album, artist
            """, (album_name, artist))
        else:
            cursor.execute("""
                SELECT
                    album as name,
                    artist,
                    COUNT(*) as song_count,
                    SUM(duration) as total_duration
                FROM tracks
                WHERE album = ?
                GROUP BY album, artist
            """, (album_name,))
        row = cursor.fetchone()
        if not row:
            return None

        # Get cover from first track of album
        if artist:
            cursor.execute("""
                SELECT cover_path FROM tracks
                WHERE album = ? AND artist = ? AND cover_path IS NOT NULL
                LIMIT 1
            """, (album_name, artist))
        else:
            cursor.execute("""
                SELECT cover_path FROM tracks
                WHERE album = ? AND cover_path IS NOT NULL
                LIMIT 1
            """, (album_name,))
        cover_row = cursor.fetchone()
        cover_path = cover_row["cover_path"] if cover_row else None

        return Album(
            name=row["name"] or "",
            artist=row["artist"] or "",
            cover_path=cover_path,
            song_count=row["song_count"] or 0,
            duration=row["total_duration"] or 0.0,
        )

    def is_empty(self) -> bool:
        """Check if albums table is empty."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM albums")
        result = cursor.fetchone()
        return result["count"] == 0 if result else True

    def refresh(self) -> bool:
        """
        Refresh the albums table from tracks table.
        Updates cover_path from tracks table for each album.

        Returns:
            True if successful
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Clear albums table
        cursor.execute("DELETE FROM albums")

        # Rebuild from tracks with aggregate cover lookup
        cursor.execute("""
            INSERT INTO albums (name, artist, cover_path, song_count, total_duration)
            SELECT
                album as name,
                artist,
                MAX(CASE WHEN cover_path IS NOT NULL THEN cover_path END) as cover_path,
                COUNT(*) as song_count,
                SUM(duration) as total_duration
            FROM tracks
            WHERE album IS NOT NULL AND album != ''
            GROUP BY album, artist
        """)

        conn.commit()
        return True

    def update_cover_path(self, album_name: str, artist: str, cover_path: str) -> bool:
        """
        Update cover path for an album.

        Args:
            album_name: Album name
            artist: Artist name
            cover_path: Path to cover image

        Returns:
            True if updated successfully
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE albums
            SET cover_path = ?, updated_at = CURRENT_TIMESTAMP
            WHERE name = ? AND artist = ?
        """, (cover_path, album_name, artist))
        conn.commit()
        return cursor.rowcount > 0

    def get_albums_without_cover(self) -> List[Album]:
        """
        Get all albums that don't have a cover.

        Returns:
            List of Album objects without valid cover_path
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Query albums table for albums without covers
        cursor.execute("""
            SELECT name, artist, cover_path, song_count, total_duration
            FROM albums
            WHERE cover_path IS NULL OR cover_path = ''
            ORDER BY song_count DESC
        """)
        rows = cursor.fetchall()

        return [
            Album(
                name=row["name"] or "",
                artist=row["artist"] or "",
                cover_path=row["cover_path"],
                song_count=row["song_count"] or 0,
                duration=row["total_duration"] or 0.0,
            )
            for row in rows
        ]
