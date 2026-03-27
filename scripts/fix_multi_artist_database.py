"""
Fix multi-artist database issues.

This script:
1. Cleans up the artists table to remove concatenated multi-artist entries
2. Populates the track_artists junction table from existing track data
3. Updates artist statistics based on junction table
"""

import sqlite3
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.metadata import split_artists, normalize_artist_name


def fix_multi_artist_database(db_path: str = "Harmony.db"):
    """Fix multi-artist database issues."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("Step 1: Populating track_artists junction table...")

    # Get all tracks with artist data
    cursor.execute("""
        SELECT id, artist FROM tracks
        WHERE artist IS NOT NULL AND artist != ''
    """)
    tracks = cursor.fetchall()

    processed = 0
    created = 0

    for track in tracks:
        track_id = track["id"]
        artist_string = track["artist"]

        # Split artist string
        artist_names = split_artists(artist_string)

        if not artist_names:
            continue

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
                created += 1

        processed += 1
        if processed % 1000 == 0:
            print(f"  Processed {processed} tracks...")

    conn.commit()
    print(f"  Created {created} junction records for {processed} tracks")

    print("\nStep 2: Removing concatenated multi-artist entries...")

    # Find and remove artists that are actually concatenations of other artists
    cursor.execute("SELECT id, name FROM artists")
    all_artists = cursor.fetchall()

    removed_count = 0
    for artist in all_artists:
        artist_name = artist["name"]

        # Try to split the artist name
        parts = split_artists(artist_name)

        # If it splits into multiple parts and those parts exist as separate artists
        if len(parts) > 1:
            # Check if all parts exist as individual artists
            all_parts_exist = True
            for part in parts:
                cursor.execute("SELECT 1 FROM artists WHERE name = ?", (part,))
                if not cursor.fetchone():
                    all_parts_exist = False
                    break

            # If all parts exist as individual artists, this is a concatenation
            if all_parts_exist:
                # Delete junction records for this concatenated artist
                cursor.execute("DELETE FROM track_artists WHERE artist_id = ?", (artist["id"],))
                # Delete the concatenated artist entry
                cursor.execute("DELETE FROM artists WHERE id = ?", (artist["id"],))
                removed_count += 1

    conn.commit()
    print(f"  Removed {removed_count} concatenated artist entries")

    print("\nStep 3: Updating artist statistics...")

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
    print(f"  Updated {cursor.rowcount} artist statistics")

    # Remove artists with 0 songs
    cursor.execute("DELETE FROM artists WHERE song_count = 0")
    removed_empty = cursor.rowcount
    conn.commit()
    print(f"  Removed {removed_empty} artists with 0 songs")

    print("\nDone! Database has been fixed.")
    conn.close()


if __name__ == "__main__":
    fix_multi_artist_database()
