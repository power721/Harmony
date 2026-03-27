#!/usr/bin/env python3
"""Fix cover paths for all artists and albums by checking local cache files.

For each artist, computes the expected cover cache path using the same
md5 key rule as CoverService, checks if the file exists, and updates
the database if a cover is found.

Also handles album covers: for each album, computes cache key as
md5("artist:album".lower()) and checks cache directory.
"""

import hashlib
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "Harmony.db"
CACHE_DIR = Path.home() / ".cache" / "Harmony" / "covers"
EXTENSIONS = [".jpg", ".jpeg", ".png"]


def album_cache_key(artist: str, album: str) -> str:
    """Generate cover cache key (matches CoverService._get_cache_key)."""
    key = f"{artist}:{album}".lower()
    return hashlib.md5(key.encode()).hexdigest()


def artist_cache_key(artist_name: str) -> str:
    """Generate artist cover cache key."""
    key = f"{artist_name}:".lower()
    return hashlib.md5(key.encode()).hexdigest()


def find_cover_file(cache_key: str) -> Path | None:
    """Find cover file by cache key."""
    for ext in EXTENSIONS:
        p = CACHE_DIR / f"{cache_key}{ext}"
        if p.exists():
            return p
    return None


def fix_artists(cursor) -> int:
    """Fix artist cover paths."""
    cursor.execute("SELECT id, name, cover_path FROM artists ORDER BY name")
    artists = cursor.fetchall()

    updated = 0
    already_ok = 0
    not_found = 0

    for artist in artists:
        name = artist["name"]
        current = artist["cover_path"]

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
            print(f"  [ARTIST UPDATED] {name} -> {cover_file.name}")
        else:
            not_found += 1

    print(f"  Artists: {updated} updated, {already_ok} already OK, {not_found} no cover")
    return updated


def fix_albums(cursor) -> int:
    """Fix album cover paths."""
    cursor.execute("SELECT id, name, artist, cover_path FROM albums ORDER BY artist, name")
    albums = cursor.fetchall()

    updated = 0
    already_ok = 0
    not_found = 0

    for album in albums:
        name = album["name"]
        artist = album["artist"]
        current = album["cover_path"]

        if current and Path(current).exists():
            already_ok += 1
            continue

        cache_key = album_cache_key(artist, name)
        cover_file = find_cover_file(cache_key)

        if cover_file:
            cursor.execute(
                "UPDATE albums SET cover_path = ? WHERE id = ?",
                (str(cover_file), album["id"]),
            )
            updated += 1
            print(f"  [ALBUM UPDATED] {artist} - {name} -> {cover_file.name}")
        else:
            not_found += 1

    print(f"  Albums:  {updated} updated, {already_ok} already OK, {not_found} no cover")
    return updated


def main():
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        return
    if not CACHE_DIR.exists():
        print(f"Cache dir not found: {CACHE_DIR}")
        return

    print(f"Database: {DB_PATH}")
    print(f"Cache:    {CACHE_DIR}")
    print()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("=== Fixing Artist Covers ===")
    artist_updated = fix_artists(cursor)

    print()
    print("=== Fixing Album Covers ===")
    album_updated = fix_albums(cursor)

    conn.commit()
    conn.close()

    print()
    print(f"Done: {artist_updated} artists + {album_updated} albums updated")


if __name__ == "__main__":
    main()
