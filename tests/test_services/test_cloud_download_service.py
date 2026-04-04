"""
Tests for CloudDownloadService cache path handling.
"""

from domain.cloud import CloudFile
from services.cloud.download_service import CloudDownloadService


def test_get_cached_path_does_not_reuse_same_name_cache_for_different_file_ids(tmp_path):
    """Different cloud file IDs with the same display name must not share a cache hit."""
    service = CloudDownloadService()
    service.set_download_dir(str(tmp_path))

    first_file = CloudFile(file_id="fid-1", name="song.mp3", size=4)
    second_file = CloudFile(file_id="fid-2", name="song.mp3", size=4)

    legacy_shared_path = tmp_path / "song.mp3"
    legacy_shared_path.write_bytes(b"demo")

    assert service.get_cached_path(first_file.file_id, first_file) is None
    assert service.get_cached_path(second_file.file_id, second_file) is None
