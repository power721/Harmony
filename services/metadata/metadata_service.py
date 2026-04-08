"""
Metadata extraction service for audio files using mutagen.
"""
import logging
from pathlib import Path
from typing import Dict, Any, Callable

import mutagen
from mutagen.flac import FLAC
from mutagen.id3 import ID3NoHeaderError
from mutagen.mp3 import MP3, HeaderNotFoundError
from mutagen.mp4 import MP4
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis
from mutagen.wave import WAVE

# Configure logging
logger = logging.getLogger(__name__)


class MetadataService:
    """Service for extracting metadata from audio files."""

    # Supported audio formats
    SUPPORTED_FORMATS = {
        ".mp3",
        ".flac",
        ".ogg",
        ".oga",
        ".opus",
        ".m4a",
        ".mp4",
        ".wma",
        ".wav",
    }

    _HEADER_READ_SIZE = 128
    _MP3_HEADER_PREFIXES = (b"ID3", b"\xFF\xF2", b"\xFF\xF3", b"\xFF\xFA", b"\xFF\xFB")

    @classmethod
    def is_supported(cls, file_path: str) -> bool:
        """
        Check if a file format is supported.

        Args:
            file_path: Path to the audio file

        Returns:
            True if format is supported
        """
        return Path(file_path).suffix.lower() in cls.SUPPORTED_FORMATS

    @classmethod
    def extract_metadata(cls, file_path: str) -> Dict[str, Any]:
        """
        Extract metadata from an audio file.

        Args:
            file_path: Path to the audio file

        Returns:
            Dictionary containing metadata (title, artist, album, duration, cover)
        """
        metadata = {
            "title": "",
            "artist": "",
            "album": "",
            "genre": "",
            "duration": 0.0,
            "cover": None,
        }

        # Skip invalid paths
        if not file_path or file_path.strip() in ('', '.', '/'):
            return metadata

        path = None
        try:
            path = Path(file_path)
            if not path.exists():
                return metadata

            suffix = path.suffix.lower()
            format_key, audio = cls._load_audio_file(file_path, suffix)
            metadata.update(cls._parse_loaded_audio(format_key, audio))

        except Exception as e:
            logger.error(f"Error extracting metadata from {file_path}: {e}", exc_info=True)

        # Fallback to filename if no title
        if not metadata["title"] and path is not None:
            metadata["title"] = path.stem

        # Default artist if none found
        if not metadata["artist"]:
            metadata["artist"] = ""

        return metadata

    @classmethod
    def _load_audio_file(cls, file_path: str, suffix: str) -> tuple[str | None, Any]:
        """Load an audio file using extension first, then content sniffing if needed."""
        suffix_key, suffix_loader = cls._get_loader_for_suffix(suffix)
        header = cls._read_file_header(file_path)
        header_key, header_loader = cls._get_loader_for_header(header)

        if suffix_loader is not None:
            try:
                return suffix_key, suffix_loader(file_path)
            except (mutagen.MutagenError, HeaderNotFoundError):
                if header_loader is not None and header_loader is not suffix_loader:
                    logger.warning(
                        "Extension %s doesn't match content for %s, falling back to detected %s loader",
                        suffix,
                        file_path,
                        header_key,
                    )
                    return header_key, header_loader(file_path)

                audio = cls._load_generic_audio(file_path)
                if audio is not None:
                    return "generic", audio
                raise

        if header_loader is not None:
            return header_key, header_loader(file_path)

        audio = cls._load_generic_audio(file_path)
        if audio is not None:
            return "generic", audio

        return None, None

    @classmethod
    def _load_generic_audio(cls, file_path: str):
        """Load audio with mutagen's generic file detection."""
        try:
            return mutagen.File(file_path)
        except mutagen.MutagenError:
            return None

    @classmethod
    def _read_file_header(cls, file_path: str) -> bytes:
        """Read the leading bytes needed for container sniffing."""
        try:
            with open(file_path, "rb") as file_obj:
                return file_obj.read(cls._HEADER_READ_SIZE)
        except OSError:
            return b""

    @classmethod
    def _get_loader_for_suffix(cls, suffix: str) -> tuple[str | None, Callable[[str], Any] | None]:
        """Return the preferred loader for a known extension."""
        suffix_loaders = {
            ".mp3": ("mp3", MP3),
            ".flac": ("flac", FLAC),
            ".ogg": ("ogg", OggVorbis),
            ".oga": ("ogg", OggVorbis),
            ".opus": ("opus", OggOpus),
            ".m4a": ("mp4", MP4),
            ".mp4": ("mp4", MP4),
            ".wav": ("wav", WAVE),
        }
        return suffix_loaders.get(suffix, (None, None))

    @classmethod
    def _get_loader_for_header(cls, header: bytes) -> tuple[str | None, Callable[[str], Any] | None]:
        """Return the loader suggested by the file header bytes."""
        if header.startswith(b"OggS"):
            if b"\x01vorbis" in header:
                return "ogg", OggVorbis
            if b"OpusHead" in header:
                return "opus", OggOpus

        if header.startswith(b"fLaC"):
            return "flac", FLAC

        if header.startswith(b"RIFF") and header[8:12] == b"WAVE":
            return "wav", WAVE

        if b"ftyp" in header:
            return "mp4", MP4

        if any(header.startswith(prefix) for prefix in cls._MP3_HEADER_PREFIXES):
            return "mp3", MP3

        return None, None

    @classmethod
    def _parse_loaded_audio(cls, format_key: str | None, audio) -> Dict[str, Any]:
        """Parse metadata from a loaded audio object based on its detected format."""
        if audio is None:
            return {}
        if format_key == "mp3":
            return cls._parse_mp3(audio)
        if format_key == "flac":
            return cls._parse_flac(audio)
        if format_key in {"ogg", "opus"}:
            return cls._parse_ogg(audio)
        if format_key == "mp4":
            return cls._parse_mp4(audio)
        if format_key == "wav":
            return cls._parse_wav(audio)

        info = getattr(audio, "info", None)
        duration = getattr(info, "length", 0.0)
        return {"duration": duration}

    @classmethod
    def _parse_mp3(cls, audio: MP3) -> Dict[str, Any]:
        """Parse metadata from MP3 file."""
        metadata = {"duration": audio.info.length}

        # Try to get ID3 tags
        try:
            tags = audio.tags

            if tags:
                # Title
                if "TIT2" in tags:
                    metadata["title"] = str(tags["TIT2"])

                # Artist
                if "TPE1" in tags:
                    metadata["artist"] = str(tags["TPE1"])

                # Album
                if "TALB" in tags:
                    metadata["album"] = str(tags["TALB"])

                # Genre
                if "TCON" in tags:
                    metadata["genre"] = str(tags["TCON"])

                # Extract cover art from APIC frame
                if "APIC:" in tags:
                    for key in tags:
                        if key.startswith("APIC"):
                            apic = tags[key]
                            metadata["cover"] = apic.data
                            break

        except (ID3NoHeaderError, AttributeError):
            pass

        return metadata

    @classmethod
    def _parse_flac(cls, audio: FLAC) -> Dict[str, Any]:
        """Parse metadata from FLAC file."""
        metadata = {"duration": audio.info.length}

        # Title
        if "title" in audio:
            metadata["title"] = audio["title"][0]

        # Artist
        if "artist" in audio:
            metadata["artist"] = audio["artist"][0]

        # Album
        if "album" in audio:
            metadata["album"] = audio["album"][0]

        # Genre
        if "genre" in audio:
            metadata["genre"] = audio["genre"][0]

        # Extract cover art
        if audio.pictures:
            metadata["cover"] = audio.pictures[0].data

        return metadata

    @classmethod
    def _parse_ogg(cls, audio: OggVorbis) -> Dict[str, Any]:
        """Parse metadata from OGG Vorbis file."""
        metadata = {"duration": audio.info.length}

        # Title
        if "title" in audio:
            metadata["title"] = audio["title"][0]

        # Artist
        if "artist" in audio:
            metadata["artist"] = audio["artist"][0]

        # Album
        if "album" in audio:
            metadata["album"] = audio["album"][0]

        # Genre
        if "genre" in audio:
            metadata["genre"] = audio["genre"][0]

        return metadata

    @classmethod
    def _parse_mp4(cls, audio: MP4) -> Dict[str, Any]:
        """Parse metadata from M4A/MP4 file."""
        metadata = {"duration": audio.info.length}

        # MP4 tags use different keys
        # Title
        if "\xa9nam" in audio:
            metadata["title"] = audio["\xa9nam"][0]

        # Artist
        if "\xa9ART" in audio:
            metadata["artist"] = audio["\xa9ART"][0]

        # Album
        if "\xa9alb" in audio:
            metadata["album"] = audio["\xa9alb"][0]

        # Genre (check both standard and iTunes-specific tags)
        if "\xa9gen" in audio:
            metadata["genre"] = audio["\xa9gen"][0]
        elif "----:com.apple.iTunes:genre" in audio:
            genre_data = audio["----:com.apple.iTunes:genre"][0]
            # iTunes genre tags may be bytes
            if isinstance(genre_data, bytes):
                genre_data = genre_data.decode("utf-8", errors="replace")
            metadata["genre"] = genre_data

        # Cover art
        if "covr" in audio:
            metadata["cover"] = audio["covr"][0]

        return metadata

    @classmethod
    def _parse_wav(cls, audio: WAVE) -> Dict[str, Any]:
        """Parse metadata from WAV file."""
        metadata = {"duration": audio.info.length}

        # WAV files can have ID3 tags
        try:
            if audio.tags:
                # Title
                if "TIT2" in audio.tags:
                    metadata["title"] = str(audio.tags["TIT2"])

                # Artist
                if "TPE1" in audio.tags:
                    metadata["artist"] = str(audio.tags["TPE1"])

                # Album
                if "TALB" in audio.tags:
                    metadata["album"] = str(audio.tags["TALB"])

                # Genre
                if "TCON" in audio.tags:
                    metadata["genre"] = str(audio.tags["TCON"])

                # Extract cover art from APIC frame
                if "APIC:" in audio.tags:
                    for key in audio.tags:
                        if key.startswith("APIC"):
                            apic = audio.tags[key]
                            metadata["cover"] = apic.data
                            break
        except (ID3NoHeaderError, AttributeError):
            pass

        return metadata

    @classmethod
    def save_cover(cls, file_path: str, output_path: str) -> bool:
        """
        Extract and save cover art from an audio file.

        Args:
            file_path: Path to the audio file
            output_path: Path where cover image will be saved

        Returns:
            True if cover was saved successfully
        """
        metadata = cls.extract_metadata(file_path)

        if metadata.get("cover"):
            try:
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(metadata["cover"])
                return True
            except Exception as e:
                logger.error(f"Error saving cover to {output_path}: {e}", exc_info=True)

        return False

    @classmethod
    def save_metadata(
            cls, file_path: str, title: str = None, artist: str = None, album: str = None,
            genre: str = None
    ) -> bool:
        """
        Save metadata to an audio file.

        Args:
            file_path: Path to the audio file
            title: Title to set
            artist: Artist to set
            album: Album to set
            genre: Genre to set

        Returns:
            True if metadata was saved successfully
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return False

            suffix = path.suffix.lower()
            format_key, audio = cls._load_audio_file(file_path, suffix)
            cls._save_loaded_audio_metadata(format_key, audio, title, artist, album, genre)

            if audio:
                audio.save()
                return True

        except Exception as e:
            logger.error(f"Error saving metadata to {file_path}: {e}", exc_info=True)

        return False

    @classmethod
    def _save_loaded_audio_metadata(
        cls, format_key: str | None, audio, title: str, artist: str, album: str, genre: str = None
    ) -> None:
        """Save metadata using the detected file format handler."""
        if audio is None:
            return
        if format_key == "mp3":
            cls._save_mp3_metadata(audio, title, artist, album, genre)
        elif format_key == "flac":
            cls._save_flac_metadata(audio, title, artist, album, genre)
        elif format_key in {"ogg", "opus"}:
            cls._save_ogg_metadata(audio, title, artist, album, genre)
        elif format_key == "mp4":
            cls._save_mp4_metadata(audio, title, artist, album, genre)
        elif format_key == "wav":
            cls._save_wav_metadata(audio, title, artist, album, genre)
        else:
            cls._save_generic_metadata(audio, title, artist, album, genre)

    @classmethod
    def detect_file_extension(cls, file_path: str) -> str | None:
        """Detect the preferred file extension from the audio container header."""
        header = cls._read_file_header(file_path)
        format_key, _ = cls._get_loader_for_header(header)
        if format_key == "mp3":
            return ".mp3"
        if format_key == "flac":
            return ".flac"
        if format_key == "ogg":
            return ".ogg"
        if format_key == "opus":
            return ".opus"
        if format_key == "mp4":
            return ".m4a"
        if format_key == "wav":
            return ".wav"
        return None

    @classmethod
    def _save_mp3_metadata(cls, audio: MP3, title: str, artist: str, album: str, genre: str = None):
        """Save metadata to MP3 file."""
        try:
            if audio.tags is None:
                audio.add_tags()

            from mutagen.id3 import TIT2, TPE1, TALB, TCON

            if title is not None:
                audio.tags["TIT2"] = TIT2(encoding=3, text=title)
            if artist is not None:
                audio.tags["TPE1"] = TPE1(encoding=3, text=artist)
            if album is not None:
                audio.tags["TALB"] = TALB(encoding=3, text=album)
            if genre is not None:
                audio.tags["TCON"] = TCON(encoding=3, text=genre)
        except Exception as e:
            logger.error(f"Error saving MP3 metadata: {e}", exc_info=True)

    @classmethod
    def _save_flac_metadata(cls, audio: FLAC, title: str, artist: str, album: str, genre: str = None):
        """Save metadata to FLAC file."""
        try:
            if title is not None:
                audio["title"] = [title]
            if artist is not None:
                audio["artist"] = [artist]
            if album is not None:
                audio["album"] = [album]
            if genre is not None:
                audio["genre"] = [genre]
        except Exception as e:
            logger.error(f"Error saving FLAC metadata: {e}", exc_info=True)

    @classmethod
    def _save_ogg_metadata(cls, audio: OggVorbis, title: str, artist: str, album: str, genre: str = None):
        """Save metadata to OGG file."""
        try:
            if title is not None:
                audio["title"] = [title]
            if artist is not None:
                audio["artist"] = [artist]
            if album is not None:
                audio["album"] = [album]
            if genre is not None:
                audio["genre"] = [genre]
        except Exception as e:
            logger.error(f"Error saving OGG metadata: {e}", exc_info=True)

    @classmethod
    def _save_mp4_metadata(cls, audio: MP4, title: str, artist: str, album: str, genre: str = None):
        """Save metadata to MP4/M4A file."""
        try:
            if title is not None:
                audio["\xa9nam"] = [title]
            if artist is not None:
                audio["\xa9ART"] = [artist]
            if album is not None:
                audio["\xa9alb"] = [album]
            if genre is not None:
                audio["\xa9gen"] = [genre]
        except Exception as e:
            logger.error(f"Error saving MP4 metadata: {e}", exc_info=True)

    @classmethod
    def _save_wav_metadata(cls, audio: WAVE, title: str, artist: str, album: str, genre: str = None):
        """Save metadata to WAV file using ID3 tags."""
        try:
            if audio.tags is None:
                audio.add_tags()

            from mutagen.id3 import TIT2, TPE1, TALB, TCON

            if title is not None:
                audio.tags["TIT2"] = TIT2(encoding=3, text=title)
            if artist is not None:
                audio.tags["TPE1"] = TPE1(encoding=3, text=artist)
            if album is not None:
                audio.tags["TALB"] = TALB(encoding=3, text=album)
            if genre is not None:
                audio.tags["TCON"] = TCON(encoding=3, text=genre)
        except Exception as e:
            logger.error(f"Error saving WAV metadata: {e}", exc_info=True)

    @classmethod
    def _save_generic_metadata(cls, audio, title: str, artist: str, album: str, genre: str = None):
        """Save metadata to generic audio file."""
        try:
            if title is not None:
                audio["title"] = [title]
            if artist is not None:
                audio["artist"] = [artist]
            if album is not None:
                audio["album"] = [album]
            if genre is not None:
                audio["genre"] = [genre]
        except Exception as e:
            logger.error(f"Error saving generic metadata: {e}", exc_info=True)
