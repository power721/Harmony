"""
Helpers for generating stable cloud download cache paths.
"""

from pathlib import Path

from domain.cloud import CloudFile
from utils.helpers import sanitize_filename


def build_cloud_cache_path(download_dir: str | Path, cloud_file: CloudFile) -> Path:
    """Build a unique cache path for a cloud file."""
    download_path = Path(download_dir)
    safe_name = sanitize_filename(cloud_file.name) or "cloud_file"
    safe_file_id = sanitize_filename(cloud_file.file_id) or "unknown"
    suffix = Path(safe_name).suffix
    stem = Path(safe_name).stem if suffix else safe_name
    unique_name = f"{stem}__{safe_file_id}{suffix}"
    return download_path / unique_name
