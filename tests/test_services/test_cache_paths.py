import pytest

from domain.cloud import CloudFile
from services.cloud.cache_paths import build_cloud_cache_path


def test_build_cloud_cache_path_rejects_blank_download_dir():
    cloud_file = CloudFile(file_id="file-1", name="song.mp3")

    with pytest.raises(ValueError, match="download_dir"):
        build_cloud_cache_path("   ", cloud_file)


def test_build_cloud_cache_path_rejects_missing_cloud_file(tmp_path):
    with pytest.raises(ValueError, match="cloud_file"):
        build_cloud_cache_path(tmp_path, None)
