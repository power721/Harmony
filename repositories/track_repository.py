"""
SQLite implementation of TrackRepository.
"""

import sqlite3
import threading
from typing import List, Optional

from domain.track import Track, TrackId


class SqliteTrackRepository:
    """SQLite implementation of TrackRepository."""

    def __init__(self, db_path: str = "music_player.db"):
        self.db_path = db_path
        self.local = threading.local()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self.local, "conn"):
            self.local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.local.conn.row_factory = sqlite3.Row
        return self.local.conn

    def get_by_id(self, track_id: TrackId) -> Optional[Track]:
        """Get a track by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tracks WHERE id = ?", (track_id,))
        row = cursor.fetchone()
        if row:
            return self._row_to_track(row)
        return None

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
                           INSERT INTO tracks (path, title, artist, album, duration, cover_path, cloud_file_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?)
                           """, (
                               track.path, track.title, track.artist, track.album,
                               track.duration, track.cover_path, track.cloud_file_id
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
                       SET title         = ?,
                           artist        = ?,
                           album         = ?,
                           duration      = ?,
                           cover_path    = ?,
                           cloud_file_id = ?
                       WHERE id = ?
                       """, (
                           track.title, track.artist, track.album, track.duration,
                           track.cover_path, track.cloud_file_id, track.id
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
        return Track(
            id=row["id"],
            path=row["path"],
            title=row["title"] or "",
            artist=row["artist"] or "",
            album=row["album"] or "",
            duration=row["duration"] or 0.0,
            cover_path=row["cover_path"],
            cloud_file_id=row["cloud_file_id"],
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
            cursor.execute("SELECT COUNT(*) as count FROM albums")
            if cursor.fetchone()["count"] > 0:
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
            cursor.execute("SELECT COUNT(*) as count FROM artists")
            if cursor.fetchone()["count"] > 0:
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

        # Fallback to direct query (slower)
        cursor.execute("""
            SELECT
                artist as name,
                COUNT(*) as song_count,
                COUNT(DISTINCT album) as album_count
            FROM tracks
            WHERE artist IS NOT NULL AND artist != ''
            GROUP BY artist
            ORDER BY song_count DESC
        """)
        rows = cursor.fetchall()

        artists = []
        for row in rows:
            # Get cover from first track of artist
            cursor.execute("""
                SELECT cover_path FROM tracks
                WHERE artist = ? AND cover_path IS NOT NULL
                LIMIT 1
            """, (row["name"],))
            cover_row = cursor.fetchone()
            cover_path = cover_row["cover_path"] if cover_row else None

            artists.append(Artist(
                name=row["name"] or "",
                cover_path=cover_path,
                song_count=row["song_count"] or 0,
                album_count=row["album_count"] or 0,
            ))
        return artists

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
        cursor.execute("SELECT COUNT(*) as count FROM artists")
        if cursor.fetchone()["count"] > 0:
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
            List of Album objects by the artist
        """
        from domain.album import Album

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                album as name,
                artist,
                cover_path,
                COUNT(*) as song_count,
                SUM(duration) as total_duration
            FROM tracks
            WHERE artist = ? AND album IS NOT NULL AND album != ''
            GROUP BY album
            ORDER BY album
        """, (artist_name,))
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
