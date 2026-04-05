#!/usr/bin/env python3
"""Migrate existing tracks to multi-artist support.

This script:
1. Parses existing track.artist strings
2. Creates artist entries with normalized names
3. Creates track_artists junction records
"""

import sqlite3
from pathlib import Path

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.metadata.artist_parser import split_artists, normalize_artist_name

DB_PATH = Path(__file__).parent.parent / "Harmony.db"


def migrate():
    """Run multi-artist migration."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Check if track_artists table exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='track_artists'
    """)
    if not cursor.fetchone():
        print("ERROR: track_artists table not found. Run database migration first.")
        conn.close()
        return

    # Check if already migrated
    cursor.execute("SELECT COUNT(*) FROM track_artists")
    existing = cursor.fetchone()[0]
    if existing > 0:
        print(f"Already migrated ({existing} junction records exist)")
        response = input("Re-migrate? This will clear existing junction records. [y/N]: ")
        if response.lower() != 'y':
            print("Aborted")
            conn.close()
            return
        cursor.execute("DELETE FROM track_artists")
        conn.commit()
        print("Cleared existing junction records")

    # Get all tracks with artist info
    cursor.execute("""
        SELECT id, artist FROM tracks
        WHERE artist IS NOT NULL AND artist != ''
    """)
    tracks = cursor.fetchall()
    print(f"Found {len(tracks)} tracks with artist info")

    # Process each track
    artist_cache = {}  # normalized_name -> artist_id
    junction_count = 0

    for track in tracks:
        track_id = track['id']
        artist_string = track['artist']

        # Split artists
        artist_names = split_artists(artist_string)
        if not artist_names:
            continue

        for position, artist_name in enumerate(artist_names):
            normalized = normalize_artist_name(artist_name)

            # Check cache first
            if normalized in artist_cache:
                artist_id = artist_cache[normalized]
            else:
                # Check if artist exists (by normalized name)
                cursor.execute(
                    "SELECT id, name FROM artists WHERE normalized_name = ?",
                    (normalized,)
                )
                row = cursor.fetchone()

                if row:
                    artist_id = row[0]
                else:
                    # Check if artist with same name (case-sensitive) exists
                    cursor.execute(
                        "SELECT id FROM artists WHERE name = ?",
                        (artist_name,)
                    )
                    existing = cursor.fetchone()
                    if existing:
                        artist_id = existing[0]
                        # Update normalized_name
                        cursor.execute(
                            "UPDATE artists SET normalized_name = ? WHERE id = ?",
                            (normalized, artist_id)
                        )
                    else:
                        # Create new artist
                        try:
                            cursor.execute(
                                "INSERT INTO artists (name, normalized_name) VALUES (?, ?)",
                                (artist_name, normalized)
                            )
                            artist_id = cursor.lastrowid
                        except sqlite3.IntegrityError:
                            # Another artist with same name but different case
                            # Get the existing one
                            cursor.execute(
                                "SELECT id FROM artists WHERE normalized_name = ?",
                                (normalized,)
                            )
                            artist_id = cursor.fetchone()[0]

                artist_cache[normalized] = artist_id

            # Create junction record
            cursor.execute("""
                INSERT OR IGNORE INTO track_artists (track_id, artist_id, position)
                VALUES (?, ?, ?)
            """, (track_id, artist_id, position))
            junction_count += 1

    conn.commit()
    print(f"Created {junction_count} junction records")

    # Update artist stats
    print("Updating artist statistics...")
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
    print(f"Updated {cursor.rowcount} artists")

    # Verify
    cursor.execute("SELECT COUNT(*) FROM artists")
    artist_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM track_artists")
    junction_count = cursor.fetchone()[0]

    print("\nMigration complete!")
    print(f"  Artists: {artist_count}")
    print(f"  Junction records: {junction_count}")

    conn.close()


if __name__ == "__main__":
    migrate()
