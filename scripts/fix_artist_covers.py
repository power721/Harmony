#!/usr/bin/env python3
"""Fix artist cover paths by checking local cache files.

For each artist, computes the expected cover cache path using the same
md5 key rule as CoverService, checks if the file exists, and updates
the database if a cover is found.
"""

import hashlib
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "Harmony.db"
CACHE_DIR = Path.home() / ".cache" / "Harmony" / "covers"
EXTENSIONS = [".jpg", ".jpeg", ".png"]


def artist_cache_key(artist_name: str) -> str:
    """Generate cover cache key (matches CoverService._get_cache_key)."""
    key = f"{artist_name}:".lower()
    return hashlib.md5(key.encode()).hexdigest()


def find_cover_file(cache_key: str) -> Path | None:
    """Find cover file by cache key."""
    for ext in EXTENSIONS:
        p = CACHE_DIR / f"{cache_key}{ext}"
        if p.exists():
            return p
    return None


def main():
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        return
    if not CACHE_DIR.exists():
        print(f"Cache dir not found: {CACHE_DIR}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT id, name, cover_path FROM artists ORDER BY name")
    artists = cursor.fetchall()

    updated = 0
    already_ok = 0
    not_found = 0

    for artist in artists:
        name = artist["name"]
        current = artist["cover_path"]

        # Skip if already has a valid cover path
        if current and Path(current).exists():
            already_ok += 1
            continue

        cache_key = artist_cache_key(name)
        cover_file = find_cover_file(cache_key)

        if cover_file:
            cursor.execute(
                "UPDATE artists SET cover_path = ? WHERE id = ?",
                (str(cover_file), artist["id"]),
            )
            updated += 1
            print(f"  [UPDATED] {name} -> {cover_file.name}")
        else:
            not_found += 1

    conn.commit()
    conn.close()

    print(f"\nDone: {updated} updated, {already_ok} already OK, {not_found} no cover")


if __name__ == "__main__":
    main()
