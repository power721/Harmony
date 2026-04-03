from pathlib import Path
from unittest.mock import MagicMock

from services.online.cache_cleaner_service import CacheCleanerService


def test_cache_cleaner_supports_extended_audio_extensions(tmp_path):
    download_service = MagicMock()
    download_service._download_dir = str(tmp_path)
    download_service._CACHE_EXTENSIONS = (".flac", ".mp3", ".ogg", ".m4a")

    cleaner = CacheCleanerService(
        config_manager=MagicMock(),
        download_service=download_service,
        event_bus=MagicMock(),
    )

    (tmp_path / "song1.ogg").write_bytes(b"ogg")
    (tmp_path / "song2.m4a").write_bytes(b"m4a")

    info = cleaner.get_cache_info()

    assert info["file_count"] == 2

    deleted = cleaner._delete_song_files(Path(tmp_path), "song1")
    assert str(tmp_path / "song1.ogg") in deleted
