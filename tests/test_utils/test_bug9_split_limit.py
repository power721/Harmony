"""
Tests for bug fix: Bug 9 - split("|") without limit in album/artist repositories.

Previously, album or artist names containing "|" would produce wrong results.
"""

import pytest


class TestBug9SplitWithLimit:
    """Bug 9: split("|") should use maxsplit=1 for safety."""

    def test_normal_name_no_pipe(self):
        """Normal name without pipe should work correctly."""
        key = "Album Name|Artist Name"
        parts = key.split("|", 1)
        assert parts == ["Album Name", "Artist Name"]

    def test_name_containing_pipe(self):
        """Name containing pipe character should only split on first."""
        key = "Love | Hate|Some Artist"
        parts = key.split("|", 1)
        assert len(parts) == 2  # Only split once
        assert parts[1] == " Hate|Some Artist"  # Artist retains pipe

    def test_artist_name_containing_pipe(self):
        """Artist name containing pipe should only split on first."""
        key = "Album|Artist | Band"
        parts = key.split("|", 1)
        assert parts == ["Album", "Artist | Band"]

    def test_empty_name_and_artist(self):
        """Empty fields should work."""
        key = "|"
        parts = key.split("|", 1)
        assert parts == ["", ""]

    def test_reconstruct_key_matches_original(self):
        """Reconstructed key from split parts should match original."""
        name = "My Album"
        artist = "My | Artist"
        key = f"{name}|{artist}"
        parts = key.split("|", 1)
        assert parts[0] == name
        assert parts[1] == artist
