"""
Tests for file_helpers utility functions.
"""

import pytest
from pathlib import Path
import tempfile
import os

from utils.file_helpers import (
    sanitize_filename,
    calculate_target_path,
    ensure_directory,
    get_lyrics_path,
)
from domain.track import Track


class TestSanitizeFilename:
    """Test sanitize_filename function."""

    def test_sanitize_empty_string(self):
        """Test sanitizing empty string."""
        assert sanitize_filename("") == "unnamed"

    def test_sanitize_none(self):
        """Test sanitizing None."""
        assert sanitize_filename(None) == "unnamed"

    def test_sanitize_normal_name(self):
        """Test sanitizing normal name."""
        assert sanitize_filename("My Song") == "My Song"

    def test_sanitize_removes_invalid_chars(self):
        """Test that invalid characters are removed."""
        assert sanitize_filename('Song<>:"|?*Title') == "SongTitle"

    def test_sanitize_replaces_slashes(self):
        """Test that slashes are replaced with &."""
        assert sanitize_filename("Artist/Song") == "Artist&Song"
        assert sanitize_filename("Artist\\Song") == "Artist&Song"

    def test_sanitize_removes_extra_spaces(self):
        """Test that extra spaces are cleaned."""
        assert sanitize_filename("Song   Title") == "Song Title"

    def test_sanitize_strips_dots(self):
        """Test that leading/trailing dots are stripped."""
        assert sanitize_filename("...Song Title...") == "Song Title"

    def test_sanitize_complex_case(self):
        """Test complex sanitization case."""
        result = sanitize_filename('  Artist/Song<>:"|?*Title...  ')
        assert result == "Artist&SongTitle"


class TestCalculateTargetPath:
    """Test calculate_target_path function."""

    def test_calculate_with_album_and_artist(self, temp_dir):
        """Test path calculation with album and artist."""
        track = Track(
            path="/music/song.mp3",
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
        )

        audio_path, lyrics_path = calculate_target_path(track, str(temp_dir))

        assert audio_path == temp_dir / "Test Artist" / "Test Album" / "Test Song.mp3"
        assert lyrics_path == temp_dir / "Test Artist" / "Test Album" / "Test Song.lrc"

    def test_calculate_with_artist_only(self, temp_dir):
        """Test path calculation with artist only."""
        track = Track(
            path="/music/song.mp3",
            title="Test Song",
            artist="Test Artist",
            album="",
        )

        audio_path, lyrics_path = calculate_target_path(track, str(temp_dir))

        assert audio_path == temp_dir / "Test Artist" / "Test Song.mp3"
        assert lyrics_path == temp_dir / "Test Artist" / "Test Song.lrc"

    def test_calculate_without_artist(self, temp_dir):
        """Test path calculation without artist."""
        track = Track(
            path="/music/song.mp3",
            title="Test Song",
            artist="",
            album="Test Album",
        )

        audio_path, lyrics_path = calculate_target_path(track, str(temp_dir))

        assert audio_path == temp_dir / "Test Song.mp3"
        assert lyrics_path == temp_dir / "Test Song.lrc"

    def test_calculate_uses_filename_when_no_title(self, temp_dir):
        """Test that filename is used when title is empty."""
        track = Track(
            path="/music/original_name.flac",
            title="",
            artist="Test Artist",
        )

        audio_path, lyrics_path = calculate_target_path(track, str(temp_dir))

        assert audio_path == temp_dir / "Test Artist" / "original_name.flac"
        assert lyrics_path == temp_dir / "Test Artist" / "original_name.lrc"

    def test_calculate_preserves_extension(self, temp_dir):
        """Test that original extension is preserved."""
        track = Track(
            path="/music/song.flac",
            title="Test Song",
            artist="Test Artist",
        )

        audio_path, _ = calculate_target_path(track, str(temp_dir))

        assert audio_path.suffix == ".flac"

    def test_calculate_sanitizes_names(self, temp_dir):
        """Test that artist/album/title are sanitized."""
        track = Track(
            path="/music/song.mp3",
            title='Song<>:"Title',
            artist='Artist/Name',
            album='Album|Name',
        )

        audio_path, _ = calculate_target_path(track, str(temp_dir))

        # Path should not contain invalid chars
        assert "<" not in str(audio_path)
        assert ">" not in str(audio_path)
        assert ":" not in str(audio_path)
        assert "|" not in str(audio_path)

    def test_calculate_raises_on_empty_path(self, temp_dir):
        """Test that ValueError is raised when track has no path."""
        track = Track(title="Test Song")

        with pytest.raises(ValueError, match="no local path"):
            calculate_target_path(track, str(temp_dir))

    def test_calculate_raises_on_whitespace_path(self, temp_dir):
        """Test that ValueError is raised when path is whitespace."""
        track = Track(path="   ", title="Test Song")

        with pytest.raises(ValueError, match="no local path"):
            calculate_target_path(track, str(temp_dir))


class TestEnsureDirectory:
    """Test ensure_directory function."""

    def test_ensure_existing_directory(self, temp_dir):
        """Test ensuring an existing directory."""
        result = ensure_directory(temp_dir)
        assert result is True
        assert temp_dir.exists()

    def test_ensure_creates_directory(self, temp_dir):
        """Test creating a new directory."""
        new_dir = temp_dir / "new_folder"
        result = ensure_directory(new_dir)

        assert result is True
        assert new_dir.exists()

    def test_ensure_creates_nested_directories(self, temp_dir):
        """Test creating nested directories."""
        nested_dir = temp_dir / "level1" / "level2" / "level3"
        result = ensure_directory(nested_dir)

        assert result is True
        assert nested_dir.exists()


class TestGetLyricsPath:
    """Test get_lyrics_path function."""

    def test_get_lyrics_path_lrc_exists(self, temp_dir):
        """Test finding existing .lrc file."""
        audio_path = temp_dir / "song.mp3"
        lrc_path = temp_dir / "song.lrc"
        lrc_path.write_text("lyrics")

        result = get_lyrics_path(str(audio_path))

        assert result == lrc_path

    def test_get_lyrics_path_yrc_exists(self, temp_dir):
        """Test finding existing .yrc file (higher priority)."""
        audio_path = temp_dir / "song.mp3"
        yrc_path = temp_dir / "song.yrc"
        lrc_path = temp_dir / "song.lrc"
        yrc_path.write_text("enhanced lyrics")
        lrc_path.write_text("lyrics")

        result = get_lyrics_path(str(audio_path))

        # Should return .yrc since it has higher priority
        assert result == yrc_path

    def test_get_lyrics_path_qrc_exists(self, temp_dir):
        """Test finding existing .qrc file (second priority)."""
        audio_path = temp_dir / "song.mp3"
        qrc_path = temp_dir / "song.qrc"
        lrc_path = temp_dir / "song.lrc"
        qrc_path.write_text("qrc lyrics")
        lrc_path.write_text("lyrics")

        result = get_lyrics_path(str(audio_path))

        # Should return .qrc since it has higher priority than .lrc
        assert result == qrc_path

    def test_get_lyrics_path_none_exists(self, temp_dir):
        """Test default to .lrc when no lyrics file exists."""
        audio_path = temp_dir / "song.mp3"

        result = get_lyrics_path(str(audio_path))

        assert result == temp_dir / "song.lrc"
        assert result.suffix == ".lrc"

    def test_get_lyrics_path_preserves_directory(self, temp_dir):
        """Test that the directory is preserved."""
        audio_path = temp_dir / "subdir" / "song.mp3"

        result = get_lyrics_path(str(audio_path))

        assert result.parent == temp_dir / "subdir"

    def test_get_lyrics_path_priority_order(self, temp_dir):
        """Test priority order: .yrc > .qrc > .lrc."""
        audio_path = temp_dir / "song.mp3"

        # Only .lrc exists
        lrc_path = temp_dir / "song.lrc"
        lrc_path.write_text("lrc")
        assert get_lyrics_path(str(audio_path)) == lrc_path

        # Add .qrc - should prefer it
        qrc_path = temp_dir / "song.qrc"
        qrc_path.write_text("qrc")
        assert get_lyrics_path(str(audio_path)) == qrc_path

        # Add .yrc - should prefer it most
        yrc_path = temp_dir / "song.yrc"
        yrc_path.write_text("yrc")
        assert get_lyrics_path(str(audio_path)) == yrc_path
