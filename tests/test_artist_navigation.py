"""Test artist navigation from player controls."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.bootstrap import Bootstrap


def test_artist_navigation():
    """Test that get_artist_by_name works for various artists."""
    bootstrap = Bootstrap.instance()
    library = bootstrap.library_service

    # Test cases
    test_artists = [
        "A-Lin",
        "Taylor Swift",
        "周杰伦",
        "黄霄雲",
    ]

    print("Testing artist navigation...")
    print("-" * 50)

    all_passed = True
    for artist_name in test_artists:
        artist = library.get_artist_by_name(artist_name)
        if artist:
            print(f"✓ Found: {artist.name}")
            print(f"  Songs: {artist.song_count}")
            print(f"  Albums: {artist.album_count}")
        else:
            print(f"✗ NOT FOUND: {artist_name}")
            all_passed = False

    print("-" * 50)

    # Test multi-artist track parsing
    print("\nTesting multi-artist track...")
    from services.metadata import split_artists

    test_strings = [
        "A-Lin, 李佳薇, 汪苏泷",
        "Taylor Swift, Ed Sheeran",
        "周杰伦",
    ]

    for artist_string in test_strings:
        artists = split_artists(artist_string)
        print(f"Input: {artist_string}")
        print(f"  Parsed: {artists}")

        # Verify each artist exists
        for artist_name in artists:
            artist = library.get_artist_by_name(artist_name)
            status = "✓" if artist else "✗"
            found = "found" if artist else "NOT FOUND"
            print(f"    {status} {artist_name}: {found}")

    print("\n" + "=" * 50)
    if all_passed:
        print("✓ All tests passed!")
        return 0
    else:
        print("✗ Some tests failed")
        return 1


if __name__ == "__main__":
    exit(test_artist_navigation())
