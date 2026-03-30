"""
Tests for MetadataService.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from services.metadata.metadata_service import MetadataService
from mutagen.mp3 import HeaderNotFoundError


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

    @patch("services.metadata.metadata_service.mutagen.File")
    @patch("services.metadata.metadata_service.MP3", side_effect=HeaderNotFoundError("can't sync to MPEG frame"))
    def test_extract_metadata_mp3_fallback_to_content_detection(self, mock_mp3, mock_mutagen_file):
        """Test that .mp3 file with wrong format falls back to content detection."""
        mock_audio = MagicMock()
        mock_audio.info.length = 200.0
        mock_mutagen_file.return_value = mock_audio

        with patch("services.metadata.metadata_service.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.suffix.lower.return_value = ".mp3"
            mock_path.return_value.stem = "song"

            result = MetadataService.extract_metadata("misnamed.mp3")

            assert result["duration"] == 200.0
            assert result["title"] == "song"
            mock_mutagen_file.assert_called_once_with("misnamed.mp3")

    # ===== Save Metadata Method Tests =====

    def test_save_mp3_metadata_with_existing_tags(self):
        """Test _save_mp3_metadata when audio already has tags."""
        mock_audio = MagicMock()
        mock_tags = {}
        mock_audio.tags = mock_tags

        MetadataService._save_mp3_metadata(mock_audio, "Title", "Artist", "Album")

        # Verify tags were set on the dict
        assert "TIT2" in mock_tags
        assert "TPE1" in mock_tags
        assert "TALB" in mock_tags

    def test_save_mp3_metadata_creates_tags_when_none(self):
        """Test _save_mp3_metadata creates tags when audio.tags is None."""
        mock_audio = MagicMock()
        mock_audio.tags = None
        new_tags = {}
        mock_audio.add_tags.return_value = None

        MetadataService._save_mp3_metadata(mock_audio, "Title", "Artist", "Album")

        mock_audio.add_tags.assert_called_once()

    def test_save_mp3_metadata_none_values_ignored(self):
        """Test _save_mp3_metadata skips fields that are None."""
        mock_audio = MagicMock()
        mock_tags = {}
        mock_audio.tags = mock_tags

        MetadataService._save_mp3_metadata(mock_audio, title="Title", artist=None, album=None)

        # Only TIT2 should be set
        assert "TIT2" in mock_tags
        assert "TPE1" not in mock_tags
        assert "TALB" not in mock_tags

    def test_save_flac_metadata(self):
        """Test _save_flac_metadata sets vorbis comments."""
        mock_audio = {}

        MetadataService._save_flac_metadata(mock_audio, "Title", "Artist", "Album")

        assert mock_audio["title"] == ["Title"]
        assert mock_audio["artist"] == ["Artist"]
        assert mock_audio["album"] == ["Album"]

    def test_save_flac_metadata_partial(self):
        """Test _save_flac_metadata with only title set."""
        mock_audio = {}

        MetadataService._save_flac_metadata(mock_audio, title="Title", artist=None, album=None)

        assert mock_audio["title"] == ["Title"]
        assert "artist" not in mock_audio
        assert "album" not in mock_audio

    def test_save_ogg_metadata(self):
        """Test _save_ogg_metadata sets vorbis comments."""
        mock_audio = {}

        MetadataService._save_ogg_metadata(mock_audio, "Title", "Artist", "Album")

        assert mock_audio["title"] == ["Title"]
        assert mock_audio["artist"] == ["Artist"]
        assert mock_audio["album"] == ["Album"]

    @patch("services.metadata.metadata_service.OggVorbis")
    def test_save_ogg_metadata_none_values(self, mock_ogg_class):
        """Test _save_ogg_metadata with all None values."""
        mock_audio = MagicMock()

        MetadataService._save_ogg_metadata(mock_audio, None, None, None)

        # No tags should be set when all values are None
        mock_audio.__setitem__.assert_not_called()

    def test_save_mp4_metadata(self):
        """Test _save_mp4_metadata sets MP4 atoms."""
        mock_audio = {}

        MetadataService._save_mp4_metadata(mock_audio, "Title", "Artist", "Album")

        assert mock_audio["\xa9nam"] == ["Title"]
        assert mock_audio["\xa9ART"] == ["Artist"]
        assert mock_audio["\xa9alb"] == ["Album"]

    def test_save_mp4_metadata_partial(self):
        """Test _save_mp4_metadata with only artist set."""
        mock_audio = {}

        MetadataService._save_mp4_metadata(mock_audio, title=None, artist="Artist", album=None)

        assert mock_audio["\xa9ART"] == ["Artist"]
        assert "\xa9nam" not in mock_audio
        assert "\xa9alb" not in mock_audio

    def test_save_wav_metadata_with_existing_tags(self):
        """Test _save_wav_metadata when audio already has ID3 tags."""
        mock_audio = MagicMock()
        mock_tags = {}
        mock_audio.tags = mock_tags

        MetadataService._save_wav_metadata(mock_audio, "Title", "Artist", "Album")

        # Verify tags were set
        assert "TIT2" in mock_tags
        assert "TPE1" in mock_tags
        assert "TALB" in mock_tags

    def test_save_wav_metadata_creates_tags_when_none(self):
        """Test _save_wav_metadata creates ID3 tags when audio.tags is None."""
        mock_audio = MagicMock()
        mock_audio.tags = None

        MetadataService._save_wav_metadata(mock_audio, "Title", "Artist", "Album")

        mock_audio.add_tags.assert_called_once()

    @patch("services.metadata.metadata_service.WAVE")
    def test_save_wav_metadata_none_values(self, mock_wave_class):
        """Test _save_wav_metadata with all None values."""
        mock_audio = MagicMock()
        mock_audio.tags = MagicMock()

        MetadataService._save_wav_metadata(mock_audio, None, None, None)

        # No tags should be set when all values are None
        mock_audio.tags.__setitem__.assert_not_called()

    def test_save_generic_metadata(self):
        """Test _save_generic_metadata sets tags on generic audio."""
        mock_audio = {}

        MetadataService._save_generic_metadata(mock_audio, "Title", "Artist", "Album")

        assert mock_audio["title"] == ["Title"]
        assert mock_audio["artist"] == ["Artist"]
        assert mock_audio["album"] == ["Album"]

    def test_save_generic_metadata_none_values(self):
        """Test _save_generic_metadata with all None values."""
        mock_audio = MagicMock()

        MetadataService._save_generic_metadata(mock_audio, None, None, None)

        mock_audio.__setitem__.assert_not_called()

    # ===== save_metadata integration tests =====

    @patch("services.metadata.metadata_service.MP4")
    def test_save_metadata_mp4_success(self, mock_mp4_class):
        """Test save_metadata for MP4 file."""
        mock_audio = MagicMock()
        mock_mp4_class.return_value = mock_audio

        with patch("services.metadata.metadata_service.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.suffix.lower.return_value = ".m4a"

            result = MetadataService.save_metadata("test.m4a", title="Title", artist="Artist")

            assert result is True
            mock_audio.save.assert_called_once()

    @patch("services.metadata.metadata_service.OggVorbis")
    def test_save_metadata_ogg_success(self, mock_ogg_class):
        """Test save_metadata for OGG file."""
        mock_audio = MagicMock()
        mock_ogg_class.return_value = mock_audio

        with patch("services.metadata.metadata_service.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.suffix.lower.return_value = ".ogg"

            result = MetadataService.save_metadata("test.ogg", title="Title")

            assert result is True
            mock_audio.save.assert_called_once()

    @patch("services.metadata.metadata_service.FLAC")
    def test_save_metadata_flac_success(self, mock_flac_class):
        """Test save_metadata for FLAC file."""
        mock_audio = MagicMock()
        mock_flac_class.return_value = mock_audio

        with patch("services.metadata.metadata_service.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.suffix.lower.return_value = ".flac"

            result = MetadataService.save_metadata("test.flac", title="Title", album="Album")

            assert result is True
            mock_audio.save.assert_called_once()

    @patch("services.metadata.metadata_service.WAVE")
    def test_save_metadata_wav_success(self, mock_wave_class):
        """Test save_metadata for WAV file."""
        mock_audio = MagicMock()
        mock_wave_class.return_value = mock_audio

        with patch("services.metadata.metadata_service.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.suffix.lower.return_value = ".wav"

            result = MetadataService.save_metadata("test.wav", title="Title")

            assert result is True
            mock_audio.save.assert_called_once()

    @patch("services.metadata.metadata_service.mutagen")
    @patch("services.metadata.metadata_service.Path")
    def test_save_metadata_generic_format(self, mock_path, mock_mutagen):
        """Test save_metadata falls back to generic for unknown format."""
        mock_audio = MagicMock()
        mock_mutagen.File.return_value = mock_audio

        mock_path.return_value.exists.return_value = True
        mock_path.return_value.suffix.lower.return_value = ".wma"

        result = MetadataService.save_metadata("test.wma", title="Title", artist="Artist")

        assert result is True
        mock_audio.save.assert_called_once()

    @patch("services.metadata.metadata_service.mutagen")
    @patch("services.metadata.metadata_service.Path")
    def test_save_metadata_generic_unsupported_returns_false(self, mock_path, mock_mutagen):
        """Test save_metadata returns False when mutagen.File returns None."""
        mock_mutagen.File.return_value = None

        mock_path.return_value.exists.return_value = True
        mock_path.return_value.suffix.lower.return_value = ".wma"

        result = MetadataService.save_metadata("test.wma", title="Title")

        assert result is False

    @patch("services.metadata.metadata_service.MP3")
    def test_save_metadata_exception_returns_false(self, mock_mp3_class):
        """Test save_metadata returns False when exception occurs."""
        mock_mp3_class.side_effect = Exception("File error")

        with patch("services.metadata.metadata_service.Path") as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.suffix.lower.return_value = ".mp3"

            result = MetadataService.save_metadata("test.mp3", title="Title")

            assert result is False

    @patch("services.metadata.metadata_service.WAVE")
    @patch("services.metadata.metadata_service.Path")
    def test_extract_metadata_wav_with_id3_tags(self, mock_path, mock_wave_class):
        """Test extract_metadata from WAV file with ID3 tags."""
        mock_audio = MagicMock()
        mock_audio.info.length = 300.0

        mock_tags = {
            "TIT2": MagicMock(__str__=lambda self: "WAV Title"),
            "TPE1": MagicMock(__str__=lambda self: "WAV Artist"),
            "TALB": MagicMock(__str__=lambda self: "WAV Album"),
        }
        mock_audio.tags = mock_tags

        mock_wave_class.return_value = mock_audio

        mock_path.return_value.exists.return_value = True
        mock_path.return_value.suffix.lower.return_value = ".wav"
        mock_path.return_value.stem = "wavsong"

        result = MetadataService.extract_metadata("test.wav")

        assert result["title"] == "WAV Title"
        assert result["artist"] == "WAV Artist"
        assert result["album"] == "WAV Album"
        assert result["duration"] == 300.0

    @patch("services.metadata.metadata_service.WAVE")
    @patch("services.metadata.metadata_service.Path")
    def test_extract_metadata_wav_without_tags(self, mock_path, mock_wave_class):
        """Test extract_metadata from WAV file without ID3 tags."""
        mock_audio = MagicMock()
        mock_audio.info.length = 300.0
        mock_audio.tags = None

        mock_wave_class.return_value = mock_audio

        mock_path.return_value.exists.return_value = True
        mock_path.return_value.suffix.lower.return_value = ".wav"
        mock_path.return_value.stem = "wavsong"

        result = MetadataService.extract_metadata("test.wav")

        assert result["title"] == "wavsong"  # Falls back to filename
        assert result["duration"] == 300.0
