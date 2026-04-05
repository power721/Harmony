#!/usr/bin/env python3
"""Fix artist ID mismatch in track_artists junction table.

This script fixes the issue where track_artists.artist_id references
don't match the actual artist IDs in the artists table.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "Harmony.db"


def fix_artist_ids():
    """Fix artist ID mismatch."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("Analyzing database...")

    # Check ID ranges
    cursor.execute("SELECT MIN(id), MAX(id) FROM artists")
    artist_min, artist_max = cursor.fetchone()
    print(f"Artists table ID range: {artist_min} - {artist_max}")

    cursor.execute("SELECT MIN(artist_id), MAX(artist_id) FROM track_artists")
    ta_min, ta_max = cursor.fetchone()
    print(f"track_artists artist_id range: {ta_min} - {ta_max}")

    # Check for mismatch
    if ta_min >= artist_min and ta_max <= artist_max:
        print("\n✓ All track_artists.artist_id values are within artists table range")
        conn.close()
        return

    print("\n✗ ID mismatch detected! track_artists references non-existent artist IDs")

    # Find orphaned track_artists entries
    cursor.execute("""
        SELECT COUNT(*) FROM track_artists ta
        WHERE NOT EXISTS (SELECT 1 FROM artists a WHERE a.id = ta.artist_id)
    """)
    orphaned = cursor.fetchone()[0]
    print(f"  Orphaned track_artists entries: {orphaned}")

    if orphaned == 0:
        print("\nNo orphaned entries found. Database is consistent.")
        conn.close()
        return

    # Get user confirmation
    print(f"\nFound {orphaned} track_artists entries with invalid artist_ids")
    print("This usually happens when migration was run multiple times.")
    print("\nFixing automatically...")

    import sys
    if "--yes" not in sys.argv:
        print("\nFix options:")
        print("  1. Delete all track_artists entries and re-run migration (recommended)")
        print("  2. Cancel and manually investigate")

        try:
            response = input("\nChoose option [1/2]: ").strip()
        except EOFError:
            print("\nRunning in non-interactive mode. Use --yes to auto-fix.")
            conn.close()
            return

        if response != "1":
            print("Cancelled")
            conn.close()
            return

    # Delete orphaned track_artists entries
    print("\nDeleting orphaned track_artists entries...")
    cursor.execute("""
        DELETE FROM track_artists
        WHERE NOT EXISTS (SELECT 1 FROM artists a WHERE a.id = track_artists.artist_id)
    """)
    deleted = cursor.rowcount
    print(f"Deleted {deleted} orphaned entries")

    # Check how many valid entries remain
    cursor.execute("SELECT COUNT(*) FROM track_artists")
    remaining = cursor.fetchone()[0]
    print(f"Remaining valid entries: {remaining}")

    if remaining > 0:
        print("\n✓ Some valid track_artists entries remain")
        print("You may want to run the migration script to repopulate missing entries")

    # Delete artists with no tracks
    cursor.execute("""
        DELETE FROM artists
        WHERE id NOT IN (SELECT DISTINCT artist_id FROM track_artists)
    """)
    deleted_artists = cursor.rowcount
    if deleted_artists > 0:
        print(f"Deleted {deleted_artists} artists with no tracks")

    conn.commit()

    # Verify
    cursor.execute("SELECT COUNT(*) FROM track_artists")
    ta_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM artists")
    artist_count = cursor.fetchone()[0]

    print("\n✓ Fix complete!")
    print(f"  Artists: {artist_count}")
    print(f"  track_artists entries: {ta_count}")

    conn.close()


if __name__ == "__main__":
    fix_artist_ids()
