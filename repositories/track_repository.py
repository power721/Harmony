"""
SQLite implementation of TrackRepository.
"""

import logging
import re
import sqlite3
from typing import Dict, List, Optional, TYPE_CHECKING

from domain.track import Track, TrackId, TrackSource
from repositories.base_repository import BaseRepository
from utils.normalization import normalize_online_provider_id

logger = logging.getLogger(__name__)

_FTS_BOOLEAN_OPERATORS = re.compile(r"\b(?:AND|OR|NOT)\b", re.IGNORECASE)
_FTS_FIELD_SPECIFIERS = re.compile(r"\b(?:title|artist|album)\s*:", re.IGNORECASE)
_FTS_UNSAFE_CHARACTERS = re.compile(r"[^\w\s.-]+", re.UNICODE)

if TYPE_CHECKING:
    from domain.album import Album
    from domain.artist import Artist
    from infrastructure.database import DatabaseManager


class SqliteTrackRepository(BaseRepository):
    """SQLite implementation of TrackRepository."""

    DEFAULT_PAGE_SIZE = 500

    def __init__(self, db_path: str = "Harmony.db", db_manager: "DatabaseManager" = None):
        super().__init__(db_path, db_manager)

    @staticmethod
    def _infer_online_provider_id(source_value: str | None, path: str | None, provider_id: str | None):
        normalized = normalize_online_provider_id(provider_id)
        if normalized:
            return normalized
        if str(source_value or "").strip().upper() == "QQ":
            return "qqmusic"
        path_value = str(path or "").strip().lower()
        if path_value.startswith("online://qqmusic/"):
            return "qqmusic"
        return None

    @staticmethod
    def _build_safe_fts_query(query: str) -> Optional[str]:
        """Normalize user input into a literal-term FTS query."""
        cleaned = _FTS_FIELD_SPECIFIERS.sub(" ", query)
        cleaned = _FTS_BOOLEAN_OPERATORS.sub(" ", cleaned)
        cleaned = cleaned.replace("*", " ")
        cleaned = _FTS_UNSAFE_CHARACTERS.sub(" ", cleaned)
        terms = [term for term in cleaned.split() if term]
        if not terms:
            return None
        return " ".join(f'"{term}"' for term in terms)

    def get_by_id(self, track_id: TrackId) -> Optional[Track]:
        """Get a track by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tracks WHERE id = ?", (track_id,))
        row = cursor.fetchone()
        return self._track_from_row(row)

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
        track_map = {track.id: track for track in self._tracks_from_rows(rows)}
        return [track_map[tid] for tid in track_ids if tid in track_map]

    def get_by_path(self, path: str) -> Optional[Track]:
        """Get a track by file path."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tracks WHERE path = ?", (path,))
        row = cursor.fetchone()
        return self._track_from_row(row)

    def get_by_paths(self, paths: List[str]) -> Dict[str, Track]:
        """Get multiple tracks by paths in batch. Returns dict mapping path -> Track."""
        if not paths:
            return {}
        conn = self._get_connection()
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(paths))
        cursor.execute(f"SELECT * FROM tracks WHERE path IN ({placeholders})", paths)
        rows = cursor.fetchall()
        return {track.path: track for track in self._tracks_from_rows(rows)}

    def get_index_for_paths(self, paths: List[str]) -> Dict[str, Dict[str, Optional[float]]]:
        """Get path fingerprint index for incremental scan comparisons."""
        if not paths:
            return {}

        conn = self._get_connection()
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(paths))
        try:
            cursor.execute(
                f"SELECT path, file_size, file_mtime FROM tracks WHERE path IN ({placeholders})",
                paths,
            )
            rows = cursor.fetchall()
            return {
                row["path"]: {"size": row["file_size"], "mtime": row["file_mtime"]}
                for row in rows
            }
        except sqlite3.OperationalError:
            # Fallback for legacy schema without file fingerprint columns.
            tracks = self.get_by_paths(paths)
            return {
                path: {"size": track.file_size, "mtime": track.file_mtime}
                for path, track in tracks.items()
            }

    def get_by_cloud_file_ids(self, cloud_file_ids: List[str]) -> Dict[str, Track]:
        """Get multiple tracks by cloud file IDs in batch. Returns dict mapping cloud_file_id -> Track."""
        if not cloud_file_ids:
            return {}
        conn = self._get_connection()
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(cloud_file_ids))
        cursor.execute(f"SELECT * FROM tracks WHERE cloud_file_id IN ({placeholders})", cloud_file_ids)
        rows = cursor.fetchall()
        tracks = self._tracks_from_rows(rows)
        return {track.cloud_file_id: track for track in tracks if track.cloud_file_id}

    def get_by_non_online_cloud_file_ids(self, cloud_file_ids: List[str]) -> Dict[str, Track]:
        """Get non-online tracks by cloud file IDs, keyed by cloud_file_id."""
        if not cloud_file_ids:
            return {}
        conn = self._get_connection()
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(cloud_file_ids))
        cursor.execute(
            f"""
            SELECT *
            FROM tracks
            WHERE cloud_file_id IN ({placeholders})
              AND UPPER(COALESCE(source, '')) NOT IN ('ONLINE', 'QQ')
            """,
            cloud_file_ids,
        )
        rows = cursor.fetchall()
        tracks = self._tracks_from_rows(rows)
        return {track.cloud_file_id: track for track in tracks if track.cloud_file_id}

    def get_by_online_track_keys(
        self,
        online_keys: List[tuple[str | None, str]],
    ) -> Dict[tuple[str | None, str], Track]:
        """Get online tracks by (provider_id, cloud_file_id)."""
        result: Dict[tuple[str | None, str], Track] = {}
        if not online_keys:
            return result

        seen: set[tuple[str | None, str]] = set()
        for provider_id, cloud_file_id in online_keys:
            normalized_provider_id = normalize_online_provider_id(provider_id)
            key = (normalized_provider_id, cloud_file_id)
            if not cloud_file_id or key in seen:
                continue
            seen.add(key)
            track = self.get_by_cloud_file_id(
                cloud_file_id,
                provider_id=normalized_provider_id,
            )
            if track is not None:
                result[key] = track
        return result

    @staticmethod
    def _normalize_source_value(source: Optional[TrackSource | str]) -> Optional[str]:
        """Normalize an optional source enum/string to the stored DB value."""
        if source is None:
            return None
        if isinstance(source, TrackSource):
            return source.value
        return str(source)

    def get_all(
            self,
            limit: int = DEFAULT_PAGE_SIZE,
            offset: int = 0,
            source: Optional[TrackSource | str] = None,
    ) -> List[Track]:
        """Get tracks ordered by newest first, with optional pagination and source filtering."""
        conn = self._get_connection()
        cursor = conn.cursor()
        source_value = self._normalize_source_value(source)

        query = "SELECT * FROM tracks"
        params: list = []
        if source_value:
            query += " WHERE source = ?"
            params.append(source_value)
        query += " ORDER BY id DESC"

        if limit > 0:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()
        return self._tracks_from_rows(rows)

    def get_track_count(self, source: Optional[TrackSource | str] = None) -> int:
        """Get total track count, optionally filtered by source."""
        conn = self._get_connection()
        cursor = conn.cursor()
        source_value = self._normalize_source_value(source)
        if source_value:
            cursor.execute("SELECT COUNT(*) FROM tracks WHERE source = ?", (source_value,))
        else:
            cursor.execute("SELECT COUNT(*) FROM tracks")
        return cursor.fetchone()[0]

    def get_track_position(self, track_id: TrackId, source: Optional[TrackSource | str] = None) -> Optional[int]:
        """Get the zero-based position of a track in the default DESC id ordering."""
        conn = self._get_connection()
        cursor = conn.cursor()
        source_value = self._normalize_source_value(source)

        exists_sql = "SELECT 1 FROM tracks WHERE id = ?"
        exists_params: list = [track_id]
        count_sql = "SELECT COUNT(*) FROM tracks WHERE id > ?"
        count_params: list = [track_id]

        if source_value:
            exists_sql += " AND source = ?"
            exists_params.append(source_value)
            count_sql += " AND source = ?"
            count_params.append(source_value)

        cursor.execute(exists_sql, exists_params)
        if cursor.fetchone() is None:
            return None

        cursor.execute(count_sql, count_params)
        return cursor.fetchone()[0]

    def search(
            self,
            query: str,
            limit: int = 100,
            offset: int = 0,
            source: Optional[TrackSource | str] = None,
    ) -> List[Track]:
        """Search tracks by query using FTS5 or LIKE fallback, with optional source filtering."""
        conn = self._get_connection()
        cursor = conn.cursor()
        source_value = self._normalize_source_value(source)
        safe_query = self._build_safe_fts_query(query)
        if safe_query is None:
            return []

        # Try FTS5 search first
        try:
            sql = """
                SELECT t.*
                FROM tracks t
                JOIN tracks_fts fts ON t.id = fts.rowid
                WHERE tracks_fts MATCH ?
            """
            params: list = [safe_query]
            if source_value:
                sql += " AND t.source = ?"
                params.append(source_value)
            sql += " ORDER BY t.id DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            return self._tracks_from_rows(rows)
        except sqlite3.OperationalError:
            # Fallback to LIKE search
            like_query = f"%{query}%"
            sql = """
                SELECT *
                FROM tracks
                WHERE (title LIKE ? OR artist LIKE ? OR album LIKE ?)
            """
            params = [like_query, like_query, like_query]
            if source_value:
                sql += " AND source = ?"
                params.append(source_value)
            sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            return self._tracks_from_rows(rows)

    def get_search_count(self, query: str, source: Optional[TrackSource | str] = None) -> int:
        """Count search matches using FTS5 when available, falling back to LIKE."""
        conn = self._get_connection()
        cursor = conn.cursor()
        source_value = self._normalize_source_value(source)
        safe_query = self._build_safe_fts_query(query)
        if safe_query is None:
            return 0

        try:
            sql = """
                SELECT COUNT(*)
                FROM tracks t
                JOIN tracks_fts fts ON t.id = fts.rowid
                WHERE tracks_fts MATCH ?
            """
            params: list = [safe_query]
            if source_value:
                sql += " AND t.source = ?"
                params.append(source_value)
            cursor.execute(sql, params)
            return cursor.fetchone()[0]
        except sqlite3.OperationalError:
            like_query = f"%{query}%"
            sql = """
                SELECT COUNT(*)
                FROM tracks
                WHERE (title LIKE ? OR artist LIKE ? OR album LIKE ?)
            """
            params = [like_query, like_query, like_query]
            if source_value:
                sql += " AND source = ?"
                params.append(source_value)
            cursor.execute(sql, params)
            return cursor.fetchone()[0]

    def add(self, track: Track) -> TrackId:
        """Add a new track and return its ID."""
        from services.metadata import split_artists_aware, normalize_artist_name

        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # Load known artists for space-separated name splitting
            cursor.execute("SELECT normalized_name FROM artists")
            known_artists = {row[0] for row in cursor.fetchall() if row[0]}

            cursor.execute("""
                           INSERT INTO tracks (path, title, artist, album, genre, duration, cover_path, cloud_file_id, source, online_provider_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                           """, (
                               track.path, track.title, track.artist, track.album,
                               track.genre, track.duration, track.cover_path,
                               track.cloud_file_id,
                               track.source.value if hasattr(track, 'source') and track.source else 'Local',
                               normalize_online_provider_id(track.online_provider_id),
                           ))
            track_id = cursor.lastrowid

            # Create artist entries and junction records
            if track.artist:
                artist_names = split_artists_aware(track.artist, known_artists)
                for position, artist_name in enumerate(artist_names):
                    normalized = normalize_artist_name(artist_name)
                    # Insert or get artist
                    cursor.execute("""
                        INSERT INTO artists (name, normalized_name) VALUES (?, ?)
                        ON CONFLICT(name) DO UPDATE SET normalized_name = ?
                    """, (artist_name, normalized, normalized))
                    # Get artist ID
                    cursor.execute("SELECT id FROM artists WHERE name = ?", (artist_name,))
                    artist_row = cursor.fetchone()
                    if artist_row:
                        artist_id = artist_row[0]
                        # Create junction record
                        cursor.execute("""
                            INSERT OR IGNORE INTO track_artists (track_id, artist_id, position)
                            VALUES (?, ?, ?)
                        """, (track_id, artist_id, position))

            conn.commit()
            return track_id
        except sqlite3.IntegrityError:
            # Track already exists
            return 0

    def batch_add(self, tracks: List[Track]) -> int:
        """Add multiple tracks in a single transaction. Returns number added."""
        if not tracks:
            return 0

        from services.metadata import split_artists_aware, normalize_artist_name

        conn = self._get_connection()
        cursor = conn.cursor()
        added_count = 0

        try:
            # Load known artists once for all tracks
            cursor.execute("SELECT normalized_name FROM artists")
            known_artists = {row[0] for row in cursor.fetchall() if row[0]}
            pending_track_artists: list[tuple[int, list[str]]] = []
            artist_names_to_upsert: set[str] = set()

            for track in tracks:
                try:
                    cursor.execute("""
                        INSERT INTO tracks (path, title, artist, album, genre, duration, cover_path, cloud_file_id, source, online_provider_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        track.path, track.title, track.artist, track.album,
                        track.genre, track.duration, track.cover_path,
                        track.cloud_file_id,
                        track.source.value if hasattr(track, 'source') and track.source else 'Local',
                        normalize_online_provider_id(track.online_provider_id),
                    ))
                    track_id = cursor.lastrowid

                    if track.artist:
                        artist_names = split_artists_aware(track.artist, known_artists)
                        if artist_names:
                            pending_track_artists.append((track_id, artist_names))
                            artist_names_to_upsert.update(artist_names)

                    added_count += 1
                except sqlite3.IntegrityError:
                    pass  # Track already exists

            if artist_names_to_upsert:
                artist_rows = [
                    (artist_name, normalize_artist_name(artist_name), normalize_artist_name(artist_name))
                    for artist_name in sorted(artist_names_to_upsert)
                ]
                cursor.executemany(
                    """
                        INSERT INTO artists (name, normalized_name) VALUES (?, ?)
                        ON CONFLICT(name) DO UPDATE SET normalized_name = ?
                    """,
                    artist_rows,
                )

                placeholders = ",".join("?" for _ in artist_names_to_upsert)
                cursor.execute(
                    f"SELECT id, name FROM artists WHERE name IN ({placeholders})",
                    sorted(artist_names_to_upsert),
                )
                artist_id_map = {row["name"]: row["id"] for row in cursor.fetchall()}

                track_artist_rows = []
                for track_id, artist_names in pending_track_artists:
                    for position, artist_name in enumerate(artist_names):
                        artist_id = artist_id_map.get(artist_name)
                        if artist_id:
                            track_artist_rows.append((track_id, artist_id, position))

                if track_artist_rows:
                    cursor.executemany(
                        """
                            INSERT OR IGNORE INTO track_artists (track_id, artist_id, position)
                            VALUES (?, ?, ?)
                        """,
                        track_artist_rows,
                    )

            conn.commit()
        except Exception:
            conn.rollback()
            raise

        return added_count

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
                           genre         = ?,
                           duration      = ?,
                           cover_path    = ?,
                           cloud_file_id = ?,
                           source        = ?,
                           online_provider_id = ?
                       WHERE id = ?
                       """, (
                           track.path, track.title, track.artist, track.album,
                           track.genre, track.duration, track.cover_path,
                           track.cloud_file_id,
                           track.source.value if hasattr(track, 'source') and track.source else 'Local',
                           normalize_online_provider_id(track.online_provider_id),
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

    def delete_batch(self, track_ids: List[TrackId]) -> int:
        """
        Delete multiple tracks by ID in a single transaction.

        Args:
            track_ids: List of track IDs to delete

        Returns:
            Number of tracks deleted
        """
        if not track_ids:
            return 0

        conn = self._get_connection()
        cursor = conn.cursor()

        # Use IN clause for batch deletion
        placeholders = ','.join('?' * len(track_ids))
        cursor.execute(f"DELETE FROM tracks WHERE id IN ({placeholders})", track_ids)
        deleted_count = cursor.rowcount
        conn.commit()

        return deleted_count

    def get_by_cloud_file_id(
        self,
        cloud_file_id: str,
        provider_id: str | None = None,
    ) -> Optional[Track]:
        """Get a track by cloud file ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        if provider_id:
            cursor.execute(
                "SELECT * FROM tracks WHERE cloud_file_id = ? AND online_provider_id = ?",
                (cloud_file_id, provider_id),
            )
            row = cursor.fetchone()
            if row:
                return self._track_from_row(row)
            cursor.execute(
                """
                SELECT * FROM tracks
                WHERE cloud_file_id = ?
                  AND (online_provider_id IS NULL OR TRIM(online_provider_id) = '' OR LOWER(online_provider_id) = 'online')
                ORDER BY CASE
                    WHEN UPPER(COALESCE(source, '')) = 'QQ' THEN 0
                    WHEN LOWER(COALESCE(path, '')) LIKE ? THEN 1
                    ELSE 2
                END,
                id DESC
                LIMIT 1
                """,
                (cloud_file_id, f"online://{str(provider_id).strip().lower()}/%"),
            )
        else:
            cursor.execute("SELECT * FROM tracks WHERE cloud_file_id = ?", (cloud_file_id,))
        row = cursor.fetchone()
        return self._track_from_row(row)

    def _row_to_track(self, row: sqlite3.Row) -> Track:
        """Convert a database row to a Track object."""
        from domain.track import TrackSource
        # Get source value from row, default to Local if not present
        source_value = row["source"] if "source" in row.keys() else "Local"
        source = TrackSource.from_value(source_value)
        online_provider_id = self._infer_online_provider_id(
            source_value,
            row["path"] if "path" in row.keys() else "",
            row["online_provider_id"] if "online_provider_id" in row.keys() else None,
        )

        return Track(
            id=row["id"],
            path=row["path"],
            title=row["title"] or "",
            artist=row["artist"] or "",
            album=row["album"] or "",
            genre=row["genre"],
            duration=row["duration"] or 0.0,
            cover_path=row["cover_path"],
            cloud_file_id=row["cloud_file_id"],
            source=source,
            online_provider_id=online_provider_id,
            file_size=row["file_size"] if "file_size" in row.keys() else None,
            file_mtime=row["file_mtime"] if "file_mtime" in row.keys() else None,
        )

    def _track_from_row(self, row: sqlite3.Row | None) -> Optional[Track]:
        """Hydrate a single row after applying any needed legacy repairs."""
        if row is None:
            return None
        return self._tracks_from_rows([row])[0]

    def _tracks_from_rows(self, rows: List[sqlite3.Row]) -> List[Track]:
        """Hydrate rows after applying batched legacy online-provider repairs."""
        if not rows:
            return []
        self._repair_legacy_online_rows(rows)
        return [self._row_to_track(row) for row in rows]

    def _repair_legacy_online_rows(self, rows: List[sqlite3.Row]) -> None:
        """Normalize legacy online provider placeholders with one UPDATE per batch."""
        from domain.track import TrackSource

        repairs: list[tuple[int, str | None]] = []
        for row in rows:
            if "online_provider_id" not in row.keys():
                continue
            source_value = row["source"] if "source" in row.keys() else "Local"
            inferred_provider_id = self._infer_online_provider_id(
                source_value,
                row["path"] if "path" in row.keys() else "",
                row["online_provider_id"],
            )
            if (
                inferred_provider_id != row["online_provider_id"]
                or str(source_value or "").strip().upper() == "QQ"
            ):
                repairs.append((row["id"], inferred_provider_id))

        if not repairs:
            return

        placeholders = ",".join("?" * len(repairs))
        source_cases = " ".join("WHEN ? THEN ?" for _ in repairs)
        provider_cases = " ".join("WHEN ? THEN ?" for _ in repairs)
        params: list[object] = []

        for track_id, _provider_id in repairs:
            params.extend([track_id, TrackSource.ONLINE.value])
        for track_id, provider_id in repairs:
            params.extend([track_id, provider_id])
        params.extend(track_id for track_id, _provider_id in repairs)

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"""
            UPDATE tracks
            SET source = CASE id {source_cases} ELSE source END,
                online_provider_id = CASE id {provider_cases} ELSE online_provider_id END
            WHERE id IN ({placeholders})
            """,
            params,
        )
        conn.commit()

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

        return [Album(
                name=row["name"] or "",
                artist=row["artist"] or "",
                cover_path=row["cover_path"],
                song_count=row["song_count"] or 0,
                duration=row["total_duration"] or 0.0,
            ) for row in rows]

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

    def get_artist_by_name(self, artist_name: str) -> Optional['Artist']:
        """
        Get a specific artist by name.

        Uses normalized name for case-insensitive matching.

        Args:
            artist_name: Artist name

        Returns:
            Artist object or None if not found
        """
        from domain.artist import Artist
        from services.metadata import normalize_artist_name

        conn = self._get_connection()
        cursor = conn.cursor()

        # Try to use artists table first with normalized name
        cursor.execute("SELECT 1 FROM artists LIMIT 1")
        if cursor.fetchone() is not None:
            normalized = normalize_artist_name(artist_name)
            cursor.execute("""
                SELECT id, name, cover_path, song_count, album_count
                FROM artists
                WHERE COALESCE(normalized_name, LOWER(name)) = ?
            """, (normalized,))
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

        Uses track_artists junction table for multi-artist support.
        Falls back to direct artist string match if junction table is empty.

        Args:
            artist_name: Artist name

        Returns:
            List of Track objects by the artist
        """
        from services.metadata import normalize_artist_name

        conn = self._get_connection()
        cursor = conn.cursor()

        # First try using junction table with normalized name
        normalized = normalize_artist_name(artist_name)
        cursor.execute("""
            SELECT t.* FROM tracks t
            JOIN track_artists ta ON t.id = ta.track_id
            JOIN artists a ON ta.artist_id = a.id
            WHERE a.normalized_name = ?
            ORDER BY t.album, t.id
        """, (normalized,))
        rows = cursor.fetchall()

        # If no results from junction table, fall back to combined name match
        if not rows:
            prefix = f"{artist_name}, %"
            suffix = f"%, {artist_name}"
            middle = f"%, {artist_name}, %"
            cursor.execute("""
                SELECT * FROM tracks
                WHERE artist = ? OR artist LIKE ? OR artist LIKE ? OR artist LIKE ?
                ORDER BY album, id
            """, (artist_name, prefix, suffix, middle))
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

        # Query from albums table, handling combined artist names (e.g. "A, B")
        prefix = f"{artist_name}, %"
        suffix = f"%, {artist_name}"
        middle = f"%, {artist_name}, %"
        cursor.execute("""
            SELECT name, artist, cover_path, song_count, total_duration
            FROM albums
            WHERE artist = ? OR artist LIKE ? OR artist LIKE ? OR artist LIKE ?
            ORDER BY song_count DESC
        """, (artist_name, prefix, suffix, middle))
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

    def update_fields(
        self, track_id: TrackId, title: str = None, artist: str = None,
        album: str = None, cloud_file_id: str = None
    ) -> bool:
        """
        Update specific track fields.

        Args:
            track_id: Track ID to update
            title: New title (optional)
            artist: New artist (optional)
            album: New album (optional)
            cloud_file_id: New cloud file ID (optional)

        Returns:
            True if updated successfully
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        updates = []
        params = []

        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if artist is not None:
            updates.append("artist = ?")
            params.append(artist)
        if album is not None:
            updates.append("album = ?")
            params.append(album)
        if cloud_file_id is not None:
            updates.append("cloud_file_id = ?")
            params.append(cloud_file_id)

        if not updates:
            return False

        params.append(track_id)

        cursor.execute(
            f"UPDATE tracks SET {', '.join(updates)} WHERE id = ?",
            params
        )
        conn.commit()
        return cursor.rowcount > 0

    def get_playlist_tracks(self, playlist_id: int) -> List[Track]:
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
        return [self._row_to_track(row) for row in rows]

    def add_to_playlist(self, playlist_id: int, track_id: TrackId) -> bool:
        """Add a track to a playlist."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO playlist_items (playlist_id, track_id, position)
                SELECT ?, ?, COALESCE(MAX(position), -1) + 1
                FROM playlist_items
                WHERE playlist_id = ?
            """, (playlist_id, track_id, playlist_id))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.IntegrityError:
            return False

    # ===== Multi-Artist Operations =====

    def sync_track_artists(self, track_id: TrackId, artist_string: str) -> bool:
        """
        Sync track_artists junction records for a track.

        Args:
            track_id: Track ID
            artist_string: Artist string to parse

        Returns:
            True if successful
        """
        from services.metadata import split_artists_aware, normalize_artist_name

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Load known artists for space-separated name splitting
            cursor.execute("SELECT normalized_name FROM artists")
            known_artists = {row[0] for row in cursor.fetchall() if row[0]}

            # Clear existing junction records for this track
            cursor.execute("DELETE FROM track_artists WHERE track_id = ?", (track_id,))

            # Create new junction records
            if artist_string:
                artist_names = split_artists_aware(artist_string, known_artists)
                for position, artist_name in enumerate(artist_names):
                    normalized = normalize_artist_name(artist_name)
                    # Insert or get artist
                    cursor.execute("""
                        INSERT INTO artists (name, normalized_name) VALUES (?, ?)
                        ON CONFLICT(name) DO UPDATE SET normalized_name = ?
                    """, (artist_name, normalized, normalized))
                    # Get artist ID
                    cursor.execute("SELECT id FROM artists WHERE name = ?", (artist_name,))
                    artist_row = cursor.fetchone()
                    if artist_row:
                        artist_id = artist_row[0]
                        cursor.execute("""
                            INSERT OR IGNORE INTO track_artists (track_id, artist_id, position)
                            VALUES (?, ?, ?)
                        """, (track_id, artist_id, position))

            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error syncing track artists: {e}")
            return False

    def rebuild_track_artists(self) -> int:
        """
        Rebuild the track_artists junction table for all tracks.

        This is needed when the artists table has been rebuilt (e.g. after a migration)
        and the junction table's artist_id references are stale.

        Returns:
            Number of tracks processed
        """
        from services.metadata import split_artists_aware, normalize_artist_name
        conn = self._get_connection()
        cursor = conn.cursor()

        # Get all tracks with their artist strings
        cursor.execute("SELECT id, artist FROM tracks WHERE artist IS NOT NULL AND artist != ''")
        tracks = cursor.fetchall()

        # Clear existing junction records
        cursor.execute("DELETE FROM track_artists")

        # Load known artists for space-separated name splitting
        cursor.execute("SELECT normalized_name FROM artists")
        known_artists = {row[0] for row in cursor.fetchall() if row[0]}

        # Collect artist data and track-artist relationships
        artist_upserts = []
        track_artist_inserts = []

        for track in tracks:
            track_id = track["id"]
            artist_string = track["artist"]
            if not artist_string:
                continue

            artist_names = split_artists_aware(artist_string, known_artists)
            for position, artist_name in enumerate(artist_names):
                normalized = normalize_artist_name(artist_name)
                artist_upserts.append((artist_name, normalized, normalized))

        # Batch upsert artists
        cursor.executemany(
            """
            INSERT INTO artists (name, normalized_name) VALUES (?, ?)
            ON CONFLICT(name) DO UPDATE SET normalized_name = ?
            """,
            artist_upserts,
        )

        # Build artist name -> ID map
        cursor.execute("SELECT id, name FROM artists")
        artist_id_map = {row["name"]: row["id"] for row in cursor.fetchall()}

        # Collect track-artist relationships
        for track in tracks:
            track_id = track["id"]
            artist_string = track["artist"]
            if not artist_string:
                continue

            artist_names = split_artists_aware(artist_string, known_artists)
            for position, artist_name in enumerate(artist_names):
                artist_id = artist_id_map.get(artist_name)
                if artist_id:
                    track_artist_inserts.append((track_id, artist_id, position))

        # Batch insert track-artist relationships
        cursor.executemany(
            """
            INSERT OR IGNORE INTO track_artists (track_id, artist_id, position)
            VALUES (?, ?, ?)
            """,
            track_artist_inserts,
        )

        count = len(tracks)

        conn.commit()
        logger.info(f"Rebuilt track_artists junction table for {count} tracks")
        return count

    def update_artist_stats(self) -> int:
        """
        Update song_count and album_count for all artists.

        Uses track_artists junction table for accurate counts.

        Returns:
            Number of artists updated
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Update artist stats using junction table
        cursor.execute("""
            UPDATE artists SET
                song_count = (
                    SELECT COUNT(DISTINCT ta.track_id)
                    FROM track_artists ta
                    WHERE ta.artist_id = artists.id
                ),
                album_count = (
                    SELECT COUNT(DISTINCT t.album)
                    FROM track_artists ta
                    JOIN tracks t ON ta.track_id = t.id
                    WHERE ta.artist_id = artists.id AND t.album IS NOT NULL AND t.album != ''
                )
        """)

        conn.commit()
        return cursor.rowcount

    def get_track_artist_names(self, track_id: TrackId) -> List[str]:
        """
        Get list of artist names for a track.

        Args:
            track_id: Track ID

        Returns:
            List of artist names in order
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT a.name FROM artists a
            JOIN track_artists ta ON a.id = ta.artist_id
            WHERE ta.track_id = ?
            ORDER BY ta.position
        """, (track_id,))

        return [row[0] for row in cursor.fetchall()]
