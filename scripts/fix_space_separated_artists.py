"""
Fix space-separated multi-artist entries in track_artists and artists tables.

Scans all tracks and uses known artists from the artists table to split
artist names that are separated by spaces (e.g., "周杰伦 袁咏琳").

Also ensures ALL tracks have track_artists junction records populated,
not just space-separated ones.
"""

import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.metadata.artist_parser import split_artists_aware, normalize_artist_name


def fix_space_separated_artists(db_path="Harmony.db"):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Load known artists
    cursor.execute("SELECT normalized_name FROM artists")
    known_artists = {row["normalized_name"] for row in cursor.fetchall() if row["normalized_name"]}

    # Get all tracks
    cursor.execute("SELECT id, artist FROM tracks WHERE artist IS NOT NULL AND artist != ''")
    tracks = cursor.fetchall()

    updated = 0
    for track in tracks:
        track_id = track["id"]
        artist_string = track["artist"]

        # Use split_artists_aware with known artists to split
        artist_names = split_artists_aware(artist_string, known_artists)

        # Check existing junction records
        cursor.execute(
            "SELECT artist_id FROM track_artists WHERE track_id = ?",
            (track_id,)
        )
        existing = {row["artist_id"] for row in cursor.fetchall()}

        # Build expected junction records
        expected_artists = []
        for position, artist_name in enumerate(artist_names):
            normalized = normalize_artist_name(artist_name)
            cursor.execute("""
                INSERT INTO artists (name, normalized_name) VALUES (?, ?)
                ON CONFLICT(name) DO UPDATE SET normalized_name = ?
            """, (artist_name, normalized, normalized))
            cursor.execute("SELECT id FROM artists WHERE name = ?", (artist_name,))
            artist_row = cursor.fetchone()
            if artist_row:
                expected_artists.append((artist_row["id"], position))

        expected_ids = {aid for aid, _ in expected_artists}

        # Only update if junction records differ
        if existing != expected_ids:
            cursor.execute("DELETE FROM track_artists WHERE track_id = ?", (track_id,))
            for artist_id, position in expected_artists:
                cursor.execute("""
                    INSERT OR IGNORE INTO track_artists (track_id, artist_id, position)
                    VALUES (?, ?, ?)
                """, (track_id, artist_id, position))
            if len(artist_names) > 1 or len(artist_names) == 1 and ' ' not in artist_string:
                # Only log if multi-artist or space-split happened
                split_result = split_artists_aware(artist_string)
                if split_result != artist_names or len(artist_names) > 1:
                    print(f"Track {track_id}: '{artist_string}' -> {artist_names}")
            updated += 1

    conn.commit()
    conn.close()
    print(f"\nDone. Updated {updated} tracks.")
    print("Run LibraryService.refresh() or artist_repo.refresh() to update counts.")


if __name__ == "__main__":
    fix_space_separated_artists()
