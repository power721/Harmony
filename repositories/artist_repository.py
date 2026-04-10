"""
SQLite implementation of ArtistRepository.
"""

import sqlite3
from typing import List, Optional, TYPE_CHECKING

from domain.artist import Artist
from repositories.base_repository import BaseRepository

if TYPE_CHECKING:
    from infrastructure.database import DatabaseManager


class SqliteArtistRepository(BaseRepository):
    """SQLite implementation of ArtistRepository."""

    def __init__(self, db_path: str = "Harmony.db", db_manager: "DatabaseManager" = None):
        super().__init__(db_path, db_manager)

    def get_all(self, use_cache: bool = True) -> List[Artist]:
        """
        Get all artists.

        Args:
            use_cache: If True, use cache table for faster loading

        Returns:
            List of Artist objects with aggregated info, sorted by song count descending
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Try to use artists table first
        if use_cache and self._table_exists("artists"):
                cursor.execute("""
                    SELECT name, cover_path, song_count, album_count
                    FROM artists
                    ORDER BY song_count DESC
                """)
                rows = cursor.fetchall()
                if rows:
                    return [
                        Artist(
                            name=row["name"] or "",
                            cover_path=row["cover_path"],
                            song_count=row["song_count"] or 0,
                            album_count=row["album_count"] or 0,
                        )
                        for row in rows
                    ]

        # Fallback to direct query with aggregate cover lookup
        cursor.execute("""
            SELECT
                t.artist as name,
                COUNT(*) as song_count,
                COUNT(DISTINCT t.album) as album_count,
                MAX(CASE WHEN t.cover_path IS NOT NULL THEN t.cover_path END) as cover_path
            FROM tracks t
            WHERE t.artist IS NOT NULL AND t.artist != ''
            GROUP BY t.artist
            ORDER BY song_count DESC
        """)
        rows = cursor.fetchall()

        return [
            Artist(
                name=row["name"] or "",
                cover_path=row["cover_path"],
                song_count=row["song_count"] or 0,
                album_count=row["album_count"] or 0,
            )
            for row in rows
        ]

    def get_by_name(self, artist_name: str) -> Optional[Artist]:
        """
        Get a specific artist by name.

        Args:
            artist_name: Artist name

        Returns:
            Artist object or None if not found
        """
        artist_name = str(artist_name or "").strip()
        if not artist_name:
            return None

        conn = self._get_connection()
        cursor = conn.cursor()

        # Try to use artists table first
        if self._table_exists("artists"):
            cursor.execute("""
                SELECT name, cover_path, song_count, album_count
                FROM artists
                WHERE name = ?
            """, (artist_name,))
            row = cursor.fetchone()
            if row:
                return Artist(
                    name=row["name"] or "",
                    cover_path=row["cover_path"],
                    song_count=row["song_count"] or 0,
                    album_count=row["album_count"] or 0,
                )

        # Fallback to direct query
        cursor.execute("""
            SELECT
                artist as name,
                COUNT(*) as song_count,
                COUNT(DISTINCT album) as album_count,
                MAX(CASE WHEN cover_path IS NOT NULL AND cover_path != '' THEN cover_path END) as cover_path
            FROM tracks
            WHERE artist = ?
            GROUP BY artist
        """, (artist_name,))
        row = cursor.fetchone()
        if not row:
            return None

        return Artist(
            name=row["name"] or "",
            cover_path=row["cover_path"],
            song_count=row["song_count"] or 0,
            album_count=row["album_count"] or 0,
        )

    def is_empty(self) -> bool:
        """Check if artists table is empty."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM artists")
        result = cursor.fetchone()
        return result["count"] == 0 if result else True

    def refresh(self) -> bool:
        """
        Refresh the artists table.
        Uses tracks.artist as the source of truth, split into individual artists.
        Preserves existing cover_path for artists that already have one.

        Returns:
            True if successful
        """
        from services.metadata.artist_parser import split_artists, split_artists_aware, normalize_artist_name

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Load existing cover paths
            cursor.execute("""
                SELECT name, cover_path FROM artists
            """)
            existing_covers = {row["name"]: row["cover_path"] for row in cursor.fetchall()}

            # Single query to load all track-level artist strings with cover paths.
            # We must keep track granularity here so song_count remains accurate.
            cursor.execute("""
                SELECT artist, album, cover_path FROM tracks
                WHERE artist IS NOT NULL AND artist != ''
            """)
            rows = cursor.fetchall()

            # Phase 1: Build known artists set using only regex splitting.
            known_artists = set()
            for row in rows:
                for name in split_artists(row["artist"]):
                    known_artists.add(normalize_artist_name(name))

            # Phase 2: Split with known artists awareness
            artist_data = {}  # name -> {song_count, albums, cover_path}
            for row in rows:
                artist_string = row["artist"]
                track_cover = row["cover_path"]
                track_album = row["album"]
                for name in split_artists_aware(artist_string, known_artists):
                    if name not in artist_data:
                        artist_data[name] = {"songs": 0, "albums": set(), "cover": None}
                    artist_data[name]["songs"] += 1
                    if track_album:
                        artist_data[name]["albums"].add(track_album)
                    if track_cover and not artist_data[name]["cover"]:
                        artist_data[name]["cover"] = track_cover

            # Upsert artists, preserving cover_path for existing ones
            for name, data in artist_data.items():
                cover = existing_covers.get(name) or data["cover"]
                cursor.execute("""
                    INSERT INTO artists (name, cover_path, song_count, album_count, normalized_name)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        cover_path = excluded.cover_path,
                        song_count = excluded.song_count,
                        album_count = excluded.album_count,
                        updated_at = CURRENT_TIMESTAMP
                """, (
                    name,
                    cover,
                    data["songs"],
                    len(data["albums"]),
                    name.lower(),
                ))

            # Delete artists that no longer have any tracks
            if artist_data:
                placeholders = ",".join("?" for _ in artist_data)
                cursor.execute(f"""
                    DELETE FROM artists WHERE name NOT IN ({placeholders})
                """, list(artist_data.keys()))

            conn.commit()
            return True
        except sqlite3.DatabaseError:
            conn.rollback()
            return False

    def refresh_artist(self, artist_name: str) -> bool:
        """Refresh a single artist cache row from junction/table state."""
        if not artist_name:
            return False

        from services.metadata.artist_parser import normalize_artist_name

        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT
                    a.name,
                    a.cover_path AS existing_cover,
                    COUNT(DISTINCT ta.track_id) AS song_count,
                    COUNT(DISTINCT CASE WHEN t.album IS NOT NULL AND t.album != '' THEN t.album END) AS album_count,
                    MAX(CASE WHEN t.cover_path IS NOT NULL AND t.cover_path != '' THEN t.cover_path END) AS track_cover
                FROM artists a
                LEFT JOIN track_artists ta ON ta.artist_id = a.id
                LEFT JOIN tracks t ON t.id = ta.track_id
                WHERE a.name = ?
                GROUP BY a.id, a.name, a.cover_path
                """,
                (artist_name,),
            )
            row = cursor.fetchone()
            if not row or not row["song_count"]:
                return False

            cursor.execute(
                """
                INSERT INTO artists (name, cover_path, song_count, album_count, normalized_name)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    cover_path = excluded.cover_path,
                    song_count = excluded.song_count,
                    album_count = excluded.album_count,
                    normalized_name = excluded.normalized_name,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    row["name"],
                    row["existing_cover"] or row["track_cover"],
                    row["song_count"] or 0,
                    row["album_count"] or 0,
                    normalize_artist_name(row["name"]),
                ),
            )
            conn.commit()
            return True
        except sqlite3.DatabaseError:
            conn.rollback()
            return False

    def delete_if_empty(self, artist_name: str) -> bool:
        """Delete a cached artist row when it no longer has linked tracks."""
        if not artist_name:
            return False

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 1
            FROM track_artists ta
            JOIN artists a ON a.id = ta.artist_id
            WHERE a.name = ?
            LIMIT 1
            """,
            (artist_name,),
        )
        if cursor.fetchone() is not None:
            return False

        cursor.execute("DELETE FROM artists WHERE name = ?", (artist_name,))
        conn.commit()
        return cursor.rowcount > 0

    def update_cover_path(self, artist_name: str, cover_path: str) -> bool:
        """
        Update cover path for an artist.

        Args:
            artist_name: Artist name
            cover_path: Path to cover image

        Returns:
            True if updated successfully
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE artists
            SET cover_path = ?, updated_at = CURRENT_TIMESTAMP
            WHERE name = ?
        """, (cover_path, artist_name))
        conn.commit()
        return cursor.rowcount > 0

    def rebuild_with_albums(self) -> int:
        """
        Rebuild artists and albums tables from tracks table.

        Returns:
            Total count of albums and artists created/updated
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Get existing cover paths
        cursor.execute("""
            SELECT name, artist, cover_path FROM albums
        """)
        existing_album_covers = {f"{row['name']}|{row['artist']}": row['cover_path'] for row in cursor.fetchall()}

        # Rebuild albums
        cursor.execute("DELETE FROM albums")
        cursor.execute("""
            INSERT INTO albums (name, artist, cover_path, song_count, total_duration)
            SELECT
                album as name,
                artist,
                NULL as cover_path,
                COUNT(*) as song_count,
                SUM(duration) as total_duration
            FROM tracks
            WHERE album IS NOT NULL AND album != ''
            GROUP BY album, artist
        """)
        albums_count = cursor.rowcount

        # Restore album cover paths
        if existing_album_covers:
            cursor.executemany(
                "UPDATE albums SET cover_path = ? WHERE name = ? AND artist = ?",
                [(cover, name.split("|", 1)[0], name.split("|", 1)[1]) for name, cover in existing_album_covers.items()]
            )

        # Rebuild artists from tracks directly (do not depend on track_artists staleness).
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM tracks
            WHERE artist IS NOT NULL AND artist != ''
        """)
        has_artist_tracks = (cursor.fetchone() or {"count": 0})["count"] > 0

        if has_artist_tracks:
            self.refresh()
        else:
            cursor.execute("DELETE FROM artists")

        cursor.execute("SELECT COUNT(*) as count FROM artists")
        artists_count = (cursor.fetchone() or {"count": 0})["count"]

        conn.commit()

        # Return count as integer for backward compatibility
        return albums_count + artists_count
