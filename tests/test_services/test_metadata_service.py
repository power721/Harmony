"""
Tests for MetadataService.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from services.metadata.metadata_service import MetadataService


class TestMetadataService:
    """Test MetadataService class."""

    def test_supported_formats(self):
        """Test SUPPORTED_FORMATS contains expected formats."""
        expected_formats = {".mp3", ".flac", ".ogg", ".oga", ".m4a", ".mp4", ".wma", ".wav"}
        assert MetadataService.SUPPORTED_FORMATS == expected_formats

    def test_is_supported_with_mp3(self):
        """Test is_supported with MP3 file."""
        assert MetadataService.is_supported("song.mp3") is True
        assert MetadataService.is_supported("song.MP3") is True

    def test_is_supported_with_flac(self):
        """Test is_supported with FLAC file."""
        assert MetadataService.is_supported("song.flac") is True
        assert MetadataService.is_supported("song.FLAC") is True

    def test_is_supported_unsupported_format(self):
        """Test is_supported with unsupported format."""
        assert MetadataService.is_supported("document.pdf") is False
        assert MetadataService.is_supported("image.jpg") is False

    def test_is_supported_case_insensitive(self):
        """Test is_supported is case insensitive."""
        assert MetadataService.is_supported("song.MP3") is True
        assert MetadataService.is_supported("song.FlAc") is True

    def test_extract_metadata_empty_path(self):
        """Test extract_metadata with empty path."""
        result = MetadataService.extract_metadata("")
        assert result["title"] == ""
        assert result["artist"] == ""
        assert result["album"] == ""
        assert result["duration"] == 0.0
        assert result["cover"] is None

    def test_extract_metadata_whitespace_path(self):
        """Test extract_metadata with whitespace path."""
        for path in [" ", "  ", ".", "/"]:
            result = MetadataService.extract_metadata(path)
            assert result["duration"] == 0.0

    @patch("services.metadata.metadata_service.Path")
    def test_extract_metadata_nonexistent_file(self, mock_path):
        """Test extract_metadata with non-existent file."""
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = False
        mock_path_instance.stem = "test"
        mock_path_instance.suffix.lower.return_value = ".mp3"
        mock_path.return_value = mock_path_instance

        result = MetadataService.extract_metadata("/nonexistent/file.mp3")
        # When file doesn't exist, returns empty metadata
        assert result["title"] == ""
        assert result["duration"] == 0.0

    @patch("services.metadata.metadata_service.MP3")
    def test_extract_metadata_mp3_success(self, mock_mp3_class):
        """Test extract_metadata from MP3 file successfully."""
        mock_audio = MagicMock()
        mock_audio.info.length = 180.5

        mock_tags = {
            "TIT2": MagicMock(__str__=lambda self: "Test Title"),
            "TPE1": MagicMock(__str__=lambda self: "Test Artist"),
            "TALB": MagicMock(__str__=lambda self: "Test Album"),
        }
        mock_audio.tags = mock_tags
        mock_mp3_class.return_value = mock_audio

        with patch("services.metadata.metadata_service.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.suffix.lower.return_value = ".mp3"
            mock_path.return_value.stem = "song"

            result = MetadataService.extract_metadata("test.mp3")

            assert result["title"] == "Test Title"
            assert result["artist"] == "Test Artist"
            assert result["album"] == "Test Album"
            assert result["duration"] == 180.5

    @patch("services.metadata.metadata_service.FLAC")
    def test_extract_metadata_flac_success(self, mock_flac_class):
        """Test extract_metadata from FLAC file successfully."""
        mock_audio = MagicMock()
        mock_audio.info.length = 240.0
        mock_audio.__contains__ = lambda self, key: key in ["title", "artist", "album"]
        mock_audio.__getitem__ = lambda self, key: ["Test Value"]

        mock_flac_class.return_value = mock_audio

        with patch("services.metadata.metadata_service.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.suffix.lower.return_value = ".flac"
            mock_path.return_value.stem = "song"

            result = MetadataService.extract_metadata("test.flac")

            assert result["title"] == "Test Value"
            assert result["artist"] == "Test Value"
            assert result["album"] == "Test Value"
            assert result["duration"] == 240.0

    @patch("services.metadata.metadata_service.MP3")
    def test_extract_metadata_fallback_to_filename(self, mock_mp3_class):
        """Test extract_metadata falls back to filename when no title."""
        mock_audio = MagicMock()
        mock_audio.info.length = 180.0
        mock_audio.tags = {}  # No tags

        mock_mp3_class.return_value = mock_audio

        with patch("services.metadata.metadata_service.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.suffix.lower.return_value = ".mp3"
            mock_path.return_value.stem = "mysong"

            result = MetadataService.extract_metadata("test.mp3")

            assert result["title"] == "mysong"

    @patch("services.metadata.metadata_service.MP3")
    @patch("builtins.open", new_callable=MagicMock)
    @patch("services.metadata.metadata_service.Path")
    def test_save_cover_success(self, mock_path_class, mock_open, mock_mp3_class):
        """Test save_cover successfully saves cover."""
        mock_audio = MagicMock()
        mock_audio.info.length = 180.0
        mock_tags = {"APIC:": MagicMock(data=b"fake cover data")}
        mock_audio.tags = mock_tags
        mock_audio.__contains__ = lambda self, key: key.startswith("APIC")
        mock_audio.__iter__ = lambda self: iter(["APIC:"])

        mock_mp3_class.return_value = mock_audio

        with patch.object(MetadataService, "extract_metadata") as mock_extract:
            mock_extract.return_value = {"cover": b"fake cover data"}

            mock_path = MagicMock()
            mock_path.parent.mkdir = MagicMock()
            mock_path_class.return_value = mock_path

            result = MetadataService.save_cover("test.mp3", "/output/cover.jpg")

            assert result is True

    @patch.object(MetadataService, "extract_metadata")
    def test_save_cover_no_cover_data(self, mock_extract):
        """Test save_cover when file has no cover."""
        mock_extract.return_value = {"cover": None}

        result = MetadataService.save_cover("test.mp3", "/output/cover.jpg")

        assert result is False

    @patch("services.metadata.metadata_service.MP3")
    def test_save_metadata_mp3(self, mock_mp3_class):
        """Test save_metadata for MP3 file."""
        mock_audio = MagicMock()
        mock_tags = {}
        mock_audio.tags = mock_tags

        mock_mp3_class.return_value = mock_audio

        with patch("services.metadata.metadata_service.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.suffix.lower.return_value = ".mp3"

            result = MetadataService.save_metadata(
                "test.mp3", title="New Title", artist="New Artist"
            )

            assert result is True
            mock_audio.save.assert_called_once()

    @patch("services.metadata.metadata_service.Path")
    def test_save_metadata_nonexistent_file(self, mock_path):
        """Test save_metadata with non-existent file."""
        mock_path.return_value.exists.return_value = False

        result = MetadataService.save_metadata("nonexistent.mp3", title="Title")

        assert result is False

    @patch("services.metadata.metadata_service.OggVorbis")
    def test_extract_metadata_ogg(self, mock_ogg_class):
        """Test extract_metadata from OGG file."""
        mock_audio = MagicMock()
        mock_audio.info.length = 200.0
        mock_audio.__contains__ = lambda self, key: True
        mock_audio.__getitem__ = lambda self, key: ["Ogg Value"]

        mock_ogg_class.return_value = mock_audio

        with patch("services.metadata.metadata_service.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.suffix.lower.return_value = ".ogg"
            mock_path.return_value.stem = "song"

            result = MetadataService.extract_metadata("test.ogg")

            assert result["title"] == "Ogg Value"
            assert result["duration"] == 200.0

    @patch("services.metadata.metadata_service.MP4")
    def test_extract_metadata_m4a(self, mock_mp4_class):
        """Test extract_metadata from M4A file."""
        mock_audio = MagicMock()
        mock_audio.info.length = 150.0
        mock_audio.__contains__ = lambda self, key: True
        mock_audio.__getitem__ = lambda self, key: ["M4A Value"]

        mock_mp4_class.return_value = mock_audio

        with patch("services.metadata.metadata_service.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.suffix.lower.return_value = ".m4a"
            mock_path.return_value.stem = "song"

            result = MetadataService.extract_metadata("test.m4a")

            assert result["title"] == "M4A Value"
            assert result["duration"] == 150.0
