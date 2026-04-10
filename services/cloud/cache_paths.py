"""
Helpers for generating stable cloud download cache paths.
"""

from pathlib import Path

from domain.cloud import CloudFile
from utils.helpers import sanitize_filename


def build_cloud_cache_path(download_dir: str | Path, cloud_file: CloudFile) -> Path:
    """Build a unique cache path for a cloud file."""
    if cloud_file is None:
        raise ValueError("cloud_file is required")
    if not str(download_dir or "").strip():
        raise ValueError("download_dir is required")

    download_path = Path(download_dir)
    if not download_path.exists():
        raise ValueError(f"download_dir does not exist: {download_dir}")
    if not download_path.is_dir():
        raise ValueError(f"download_dir is not a directory: {download_dir}")
    safe_name = sanitize_filename(cloud_file.name) or "cloud_file"
    safe_file_id = sanitize_filename(cloud_file.file_id) or "unknown"
    suffix = Path(safe_name).suffix
    stem = Path(safe_name).stem if suffix else safe_name
    unique_name = f"{stem}__{safe_file_id}{suffix}"
    return download_path / unique_name
