"""
SQLite implementation of TrackRepository.
"""

import sqlite3
from typing import List, Optional, TYPE_CHECKING

from domain.track import Track, TrackId
from repositories.base_repository import BaseRepository

if TYPE_CHECKING:
    from infrastructure.database import DatabaseManager


class SqliteTrackRepository(BaseRepository):
    """SQLite implementation of TrackRepository."""

    def __init__(self, db_path: str = "Harmony.db", db_manager: "DatabaseManager" = None):
        super().__init__(db_path, db_manager)

    def get_by_id(self, track_id: TrackId) -> Optional[Track]:
        """Get a track by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tracks WHERE id = ?", (track_id,))
        row = cursor.fetchone()
        if row:
            return self._row_to_track(row)
        return None

    def get_by_ids(self, track_ids: List[TrackId]) -> List[Track]:
        """Get multiple tracks by IDs in batch."""
        if not track_ids:
            return []
        conn = self._get_connection()
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(track_ids))
        cursor.execute(f"SELECT * FROM tracks WHERE id IN ({placeholders})", track_ids)
        rows = cursor.fetchall()
        # Return tracks in the order of input IDs
        track_map = {row["id"]: self._row_to_track(row) for row in rows}
        return [track_map[tid] for tid in track_ids if tid in track_map]

    def get_by_path(self, path: str) -> Optional[Track]:
        """Get a track by file path."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tracks WHERE path = ?", (path,))
        row = cursor.fetchone()
        if row:
            return self._row_to_track(row)
        return None

    def get_all(self) -> List[Track]:
        """Get all tracks."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tracks ORDER BY id DESC")
        rows = cursor.fetchall()
        return [self._row_to_track(row) for row in rows]

    def search(self, query: str, limit: int = 100) -> List[Track]:
        """Search tracks by query using FTS5 or LIKE fallback."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Try FTS5 search first
        try:
            cursor.execute("""
                           SELECT t.*
                           FROM tracks t
                                    JOIN tracks_fts fts ON t.id = fts.rowid
                           WHERE tracks_fts MATCH ?
                           ORDER BY t.id DESC LIMIT ?
                           """, (query, limit))
            rows = cursor.fetchall()
            return [self._row_to_track(row) for row in rows]
        except sqlite3.OperationalError:
            # Fallback to LIKE search
            like_query = f"%{query}%"
            cursor.execute("""
                           SELECT *
                           FROM tracks
                           WHERE title LIKE ?
                              OR artist LIKE ?
                              OR album LIKE ?
                           ORDER BY id DESC LIMIT ?
                           """, (like_query, like_query, like_query, limit))
            rows = cursor.fetchall()
            return [self._row_to_track(row) for row in rows]

    def add(self, track: Track) -> TrackId:
        """Add a new track and return its ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                           INSERT INTO tracks (path, title, artist, album, duration, cover_path, cloud_file_id, source)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                           """, (
                               track.path, track.title, track.artist, track.album,
                               track.duration, track.cover_path, track.cloud_file_id,
                               track.source.value if hasattr(track, 'source') and track.source else 'Local'
                           ))
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Track already exists
            return 0

    def update(self, track: Track) -> bool:
        """Update an existing track."""
        if not track.id:
            return False
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
                       UPDATE tracks
                       SET path          = ?,
                           title         = ?,
                           artist        = ?,
                           album         = ?,
                           duration      = ?,
                           cover_path    = ?,
                           cloud_file_id = ?,
                           source        = ?
                       WHERE id = ?
                       """, (
                           track.path, track.title, track.artist, track.album,
                           track.duration, track.cover_path, track.cloud_file_id,
                           track.source.value if hasattr(track, 'source') and track.source else 'Local',
                           track.id
                       ))
        conn.commit()
        return cursor.rowcount > 0

    def delete(self, track_id: TrackId) -> bool:
        """Delete a track by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tracks WHERE id = ?", (track_id,))
        conn.commit()
        return cursor.rowcount > 0

    def get_by_cloud_file_id(self, cloud_file_id: str) -> Optional[Track]:
        """Get a track by cloud file ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tracks WHERE cloud_file_id = ?", (cloud_file_id,))
        row = cursor.fetchone()
        if row:
            return self._row_to_track(row)
        return None

    def _row_to_track(self, row: sqlite3.Row) -> Track:
        """Convert a database row to a Track object."""
        from domain.track import TrackSource
        # Get source value from row, default to Local if not present
        source_value = row["source"] if "source" in row.keys() else "Local"
        try:
            source = TrackSource(source_value) if source_value else TrackSource.LOCAL
        except ValueError:
            source = TrackSource.LOCAL  # Fallback for invalid values

        return Track(
            id=row["id"],
            path=row["path"],
            title=row["title"] or "",
            artist=row["artist"] or "",
            album=row["album"] or "",
            duration=row["duration"] or 0.0,
            cover_path=row["cover_path"],
            cloud_file_id=row["cloud_file_id"],
            source=source,
        )

    # ===== Album Operations =====

    def get_albums(self, use_cache: bool = True) -> List['Album']:
        """
        Get all albums aggregated from tracks.

        Args:
            use_cache: If True, use cache table for faster loading

        Returns:
            List of Album objects with aggregated info
        """
        from domain.album import Album

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

        albums = []
        for row in rows:
            albums.append(Album(
                name=row["name"] or "",
                artist=row["artist"] or "",
                cover_path=row["cover_path"],
                song_count=row["song_count"] or 0,
                duration=row["total_duration"] or 0.0,
            ))
        return albums

    def get_album_tracks(self, album_name: str, artist: str = None) -> List[Track]:
        """
        Get all tracks for a specific album.

        Args:
            album_name: Album name
            artist: Optional artist filter

        Returns:
            List of Track objects in the album
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        if artist:
            cursor.execute("""
                SELECT * FROM tracks
                WHERE album = ? AND artist = ?
                ORDER BY id
            """, (album_name, artist))
        else:
            cursor.execute("""
                SELECT * FROM tracks
                WHERE album = ?
                ORDER BY id
            """, (album_name,))

        rows = cursor.fetchall()
        return [self._row_to_track(row) for row in rows]

    # ===== Artist Operations =====

    def get_artists(self, use_cache: bool = True) -> List['Artist']:
        """
        Get all artists aggregated from tracks.

        Args:
            use_cache: If True, use cache table for faster loading

        Returns:
            List of Artist objects with aggregated info, sorted by song count descending
        """
        from domain.artist import Artist

        conn = self._get_connection()
        cursor = conn.cursor()

        # Try to use artists table first
        if use_cache:
            cursor.execute("SELECT 1 FROM artists LIMIT 1")
            if cursor.fetchone() is not None:
                cursor.execute("""
                    SELECT name, cover_path, song_count, album_count
                    FROM artists
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

        # Fallback to direct query with subquery for cover (single query, no N+1)
        cursor.execute("""
            SELECT
                t.artist as name,
                COUNT(*) as song_count,
                COUNT(DISTINCT t.album) as album_count,
                (SELECT cover_path FROM tracks t2
                 WHERE t2.artist = t.artist AND t2.cover_path IS NOT NULL
                 LIMIT 1) as cover_path
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

    def get_artist_by_name(self, artist_name: str) -> Optional['Artist']:
        """
        Get a specific artist by name.

        Args:
            artist_name: Artist name

        Returns:
            Artist object or None if not found
        """
        from domain.artist import Artist

        conn = self._get_connection()
        cursor = conn.cursor()

        # Try to use artists table first
        cursor.execute("SELECT 1 FROM artists LIMIT 1")
        if cursor.fetchone() is not None:
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
            return None

        # Fallback to direct query
        cursor.execute("""
            SELECT
                artist as name,
                COUNT(*) as song_count,
                COUNT(DISTINCT album) as album_count
            FROM tracks
            WHERE artist = ?
            GROUP BY artist
        """, (artist_name,))
        row = cursor.fetchone()
        if not row:
            return None

        # Get cover from first track of artist
        cursor.execute("""
            SELECT cover_path FROM tracks
            WHERE artist = ? AND cover_path IS NOT NULL
            LIMIT 1
        """, (artist_name,))
        cover_row = cursor.fetchone()
        cover_path = cover_row["cover_path"] if cover_row else None

        return Artist(
            name=row["name"] or "",
            cover_path=cover_path,
            song_count=row["song_count"] or 0,
            album_count=row["album_count"] or 0,
        )

    def get_artist_tracks(self, artist_name: str) -> List[Track]:
        """
        Get all tracks for a specific artist.

        Args:
            artist_name: Artist name

        Returns:
            List of Track objects by the artist
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM tracks
            WHERE artist = ?
            ORDER BY album, id
        """, (artist_name,))
        rows = cursor.fetchall()
        return [self._row_to_track(row) for row in rows]

    def get_artist_albums(self, artist_name: str) -> List['Album']:
        """
        Get all albums for a specific artist.

        Args:
            artist_name: Artist name

        Returns:
            List of Album objects by the artist, sorted by song count descending
        """
        from domain.album import Album

        conn = self._get_connection()
        cursor = conn.cursor()

        # Query from albums table for better performance
        cursor.execute("""
            SELECT name, artist, cover_path, song_count, total_duration
            FROM albums
            WHERE artist = ?
            ORDER BY song_count DESC
        """, (artist_name,))
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

    def get_album_by_name(self, album_name: str, artist: str = None) -> Optional['Album']:
        """
        Get a specific album by name and optionally artist.

        Args:
            album_name: Album name
            artist: Artist name (optional, but recommended for unique identification)

        Returns:
            Album object or None if not found
        """
        from domain.album import Album

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

    def update_path(self, track_id: TrackId, path: str) -> bool:
        """Update a track's file path."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE tracks SET path = ? WHERE id = ?", (path, track_id))
        conn.commit()
        return cursor.rowcount > 0

    def update_cover_path(self, track_id: TrackId, cover_path: str) -> bool:
        """Update a track's cover path."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE tracks SET cover_path = ? WHERE id = ?", (cover_path, track_id))
        conn.commit()
        return cursor.rowcount > 0
