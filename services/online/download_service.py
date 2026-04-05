"""
Online music download service.
Downloads online music to local cache for playback.
"""

import logging
import os
from typing import Dict, Optional, Callable, Any, TYPE_CHECKING

from infrastructure.network import HttpClient
from services.cloud.qqmusic.common import parse_quality, normalize_quality
from system.event_bus import EventBus
from services.metadata.metadata_service import MetadataService

if TYPE_CHECKING:
    from system.config import ConfigManager
    from services.cloud.qqmusic.qqmusic_service import QQMusicService

logger = logging.getLogger(__name__)


class OnlineDownloadService:
    """
    Service for downloading online music.

    Works with OnlineMusicService to get playback URLs and download files.
    Supports both QQ Music local API and remote API.
    """

    _CACHE_EXTENSIONS = (
        ".flac",
        ".mp3",
        ".ogg",
        ".opus",
        ".m4a",
        ".mp4",
        ".ape",
        ".dts",
        ".wav",
    )

    def __init__(
        self,
        config_manager: Optional["ConfigManager"] = None,
        qqmusic_service: Optional["QQMusicService"] = None,
        online_music_service=None,
        download_dir: Optional[str] = None
    ):
        """
        Initialize download service.

        Args:
            config_manager: ConfigManager instance
            qqmusic_service: QQMusicService instance
            online_music_service: OnlineMusicService instance (preferred)
            download_dir: Download directory path
        """
        self._config = config_manager
        self._qqmusic = qqmusic_service
        self._online_service = online_music_service
        self._download_dir = download_dir or self._get_default_download_dir()
        self._event_bus = EventBus.instance()
        self._last_download_qualities: Dict[str, str] = {}

        # Ensure download directory exists
        os.makedirs(self._download_dir, exist_ok=True)

    def _get_default_download_dir(self) -> str:
        """Get default download directory."""
        # First check config
        if self._config:
            config_dir = self._config.get_online_music_download_dir()
            if config_dir:
                # If relative path, make it relative to current directory
                if not os.path.isabs(config_dir):
                    return os.path.join(os.getcwd(), config_dir)
                return config_dir
        # Fallback to default
        cache_dir = os.path.join(os.getcwd(), "data", "online_cache")
        return cache_dir

    def set_download_dir(self, path: str):
        """Set download directory."""
        self._download_dir = path
        os.makedirs(self._download_dir, exist_ok=True)

    def get_cached_path(self, song_mid: str, quality: Optional[str] = None) -> str:
        """
        Get cached file path for a song.

        Args:
            song_mid: Song MID
            quality: Audio quality (uses config default if None)

        Returns:
            Local file path
        """
        existing_path = self._find_existing_cached_path(song_mid)
        if existing_path:
            return existing_path

        if quality is None:
            quality = "320"
        ext = self._get_extension_for_quality(quality)
        filename = f"{song_mid}{ext}"
        return os.path.join(self._download_dir, filename)

    def is_cached(self, song_mid: str, quality: Optional[str] = None) -> bool:
        """
        Check if song is already cached.

        Args:
            song_mid: Song MID
            quality: Audio quality (uses config default if None)

        Returns:
            True if cached
        """
        return self._find_existing_cached_path(song_mid) is not None

    def pop_last_download_quality(self, song_mid: str) -> Optional[str]:
        """Return and clear the most recently resolved quality for a song."""
        return self._last_download_qualities.pop(song_mid, None)

    def download(
        self,
        song_mid: str,
        song_title: str = "",
        quality: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        force: bool = False
    ) -> Optional[str]:
        """
        Download a song.

        Args:
            song_mid: Song MID
            song_title: Song title (for logging)
            quality: Audio quality (master/flac/320/128), uses config default if None
            progress_callback: Callback for progress (downloaded, total)

        Returns:
            Local file path if successful, None otherwise
        """
        # Use configured quality if not specified
        if quality is None:
            quality = "320"

        # Check cache first (skip if force re-download)
        cached_path = self.get_cached_path(song_mid, quality)
        if not force and os.path.exists(cached_path):
            self._last_download_qualities[song_mid] = normalize_quality(quality)
            logger.info(f"Song already cached: {cached_path}")
            return cached_path

        # Get playback URL - prefer online service (supports remote API)
        url = None
        actual_quality = quality
        playback_extension = None

        if self._online_service:
            # Use online service (supports both QQ Music and remote API)
            playback_info = None
            if hasattr(self._online_service, "get_playback_url_info"):
                playback_info = self._online_service.get_playback_url_info(song_mid, quality)

            if playback_info:
                url = playback_info.get("url")
                actual_quality = playback_info.get("quality") or quality
                playback_extension = playback_info.get("extension")
            else:
                url = self._online_service.get_playback_url(song_mid, quality)

        elif self._qqmusic:
            # Fallback to QQ Music direct API
            quality_fallback = ["320", "128", "flac"]
            for q in quality_fallback:
                playback_info = self._qqmusic.get_playback_url_info(song_mid, q)
                if playback_info:
                    url = playback_info.get("url")
                    actual_quality = playback_info.get("quality") or q
                    playback_extension = playback_info.get("extension")
                    break

        if not url:
            logger.error(f"Failed to get playback URL for {song_mid}, song may require VIP")
            return None

        # Update cached path with actual quality
        cached_path = self.get_cached_path(song_mid, actual_quality)
        if playback_extension:
            cached_path = os.path.join(self._download_dir, f"{song_mid}{playback_extension}")

        # Download file
        try:
            logger.info(f"Downloading: {song_mid} {song_title} - {quality}")

            # Emit download started event
            self._event_bus.download_started.emit(song_mid)

            request_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://y.qq.com/',
            }
            temp_path = cached_path + ".tmp"
            with HttpClient.shared().stream("GET", url, headers=request_headers, timeout=60) as response:
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0

                # Write to temp file first
                with open(temp_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if progress_callback:
                                progress_callback(downloaded, total_size)

            final_path = self._get_final_download_path(song_mid, cached_path, temp_path)
            os.replace(temp_path, final_path)
            self._delete_other_cached_variants(song_mid, final_path)
            self._last_download_qualities[song_mid] = normalize_quality(actual_quality)

            logger.info(f"Download complete: {final_path}")

            # Extract metadata from downloaded file
            metadata = self._extract_metadata(song_mid, final_path)

            # Emit download completed event
            self._event_bus.download_completed.emit(song_mid, final_path)

            # Emit metadata loaded event
            if metadata:
                self._event_bus.online_track_metadata_loaded.emit(song_mid, metadata)

            return final_path

        except Exception as e:
            logger.error(f"Download failed: {e}")
            self._last_download_qualities.pop(song_mid, None)
            # Clean up temp file
            temp_path = cached_path + ".tmp"
            if os.path.exists(temp_path):
                os.remove(temp_path)
            # Emit download error event
            self._event_bus.download_error.emit(song_mid, str(e))
            return None

    def _extract_metadata(self, song_mid: str, local_path: str) -> Optional[Dict[str, Any]]:
        """
        Extract metadata from downloaded file.

        Uses local file metadata first, then supplements with online API if available.

        Args:
            song_mid: Song MID
            local_path: Local file path

        Returns:
            Metadata dict or None
        """
        metadata = {}

        # Extract from local file
        try:
            local_metadata = MetadataService.extract_metadata(local_path)
            metadata.update({
                "title": local_metadata.get("title", ""),
                "artist": local_metadata.get("artist", ""),
                "album": local_metadata.get("album", ""),
                "duration": local_metadata.get("duration", 0),
                "cover": local_metadata.get("cover"),
            })
            logger.debug(f"Local metadata for {song_mid}: title={metadata.get('title')}, album={metadata.get('album')}, artist={metadata.get('artist')}")
        except Exception as e:
            logger.warning(f"Failed to extract local metadata: {e}")

        # Supplement with online API if available
        online_metadata = self._fetch_online_metadata(song_mid)
        if online_metadata:
            # Use online data to fill missing fields
            if online_metadata.get("title"):
                metadata["title"] = online_metadata["title"]
            if online_metadata.get("artist"):
                metadata["artist"] = online_metadata["artist"]
            if online_metadata.get("album"):
                metadata["album"] = online_metadata["album"]
            if online_metadata.get("duration"):
                metadata["duration"] = online_metadata["duration"]
            # Add online-only fields
            if online_metadata.get("genre"):
                metadata["genre"] = online_metadata["genre"]
            if online_metadata.get("language"):
                metadata["language"] = online_metadata["language"]
            if online_metadata.get("publish_date"):
                metadata["publish_date"] = online_metadata["publish_date"]
            MetadataService.save_metadata(local_path, metadata["title"], metadata["artist"], metadata["album"])

        return metadata if metadata else None

    def _fetch_online_metadata(self, song_mid: str) -> Optional[Dict[str, Any]]:
        """
        Fetch metadata from online API.

        Args:
            song_mid: Song MID

        Returns:
            Metadata dict or None
        """
        # Try online service first
        if self._online_service:
            try:
                return self._online_service.get_song_detail(song_mid)
            except Exception as e:
                logger.debug(f"Online service get_song_detail failed: {e}")

        # Fallback to direct API call
        try:
            url = "https://api.ygking.top/api/song/detail"
            params = {"mid": song_mid}

            response = HttpClient.shared().get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("code") == 0:
                song_data = data.get("data", {})
                metadata = {
                    "title": song_data.get("title", ""),
                    "artist": ", ".join(s.get("name", "") for s in song_data.get("singer", [])),
                    "album": song_data.get("album", {}).get("name", "") if song_data.get("album") else "",
                    "duration": song_data.get("interval", 0),
                    "genre": song_data.get("genre"),
                    "language": song_data.get("language"),
                    "publish_date": song_data.get("publish_date"),
                }
                return metadata

        except Exception as e:
            logger.debug(f"Failed to fetch online metadata: {e}")

        return None

    def clear_cache(self):
        """Clear all cached files."""
        import shutil
        if os.path.exists(self._download_dir):
            shutil.rmtree(self._download_dir)
            os.makedirs(self._download_dir, exist_ok=True)
            logger.info(f"Cleared cache directory: {self._download_dir}")

    def delete_cached_file(self, song_mid: str) -> bool:
        """Delete all cached files for a song (all quality variants).

        Args:
            song_mid: Song MID

        Returns:
            True if any file was deleted
        """
        deleted = False
        for ext in self._CACHE_EXTENSIONS:
            path = os.path.join(self._download_dir, f"{song_mid}{ext}")
            if os.path.exists(path):
                try:
                    os.remove(path)
                    deleted = True
                    logger.info(f"Deleted cached file: {path}")
                except OSError as e:
                    logger.warning(f"Failed to delete cached file {path}: {e}")

            tmp_path = f"{path}.tmp"
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                    deleted = True
                    logger.info(f"Deleted cached file: {tmp_path}")
                except OSError as e:
                    logger.warning(f"Failed to delete cached file {tmp_path}: {e}")
        return deleted

    def _get_extension_for_quality(self, quality: str) -> str:
        """Map a QQ Music quality code to its preferred container extension."""
        return parse_quality(quality).get("e", ".mp3")

    def _find_existing_cached_path(self, song_mid: str) -> Optional[str]:
        """Find any existing cached variant for a song."""
        for ext in self._CACHE_EXTENSIONS:
            path = os.path.join(self._download_dir, f"{song_mid}{ext}")
            if os.path.exists(path):
                return path
        return None

    def _get_final_download_path(self, song_mid: str, fallback_path: str, temp_path: str) -> str:
        """Choose the final cache path from the downloaded file's actual content."""
        actual_ext = MetadataService.detect_file_extension(temp_path)
        if not actual_ext:
            return fallback_path
        return os.path.join(self._download_dir, f"{song_mid}{actual_ext}")

    def _delete_other_cached_variants(self, song_mid: str, keep_path: str) -> None:
        """Remove stale cache files with mismatched extensions."""
        for ext in self._CACHE_EXTENSIONS:
            path = os.path.join(self._download_dir, f"{song_mid}{ext}")
            if path != keep_path and os.path.exists(path):
                os.remove(path)

    def get_cache_size(self) -> int:
        """Get total size of cached files in bytes."""
        total_size = 0
        if os.path.exists(self._download_dir):
            for filename in os.listdir(self._download_dir):
                filepath = os.path.join(self._download_dir, filename)
                if os.path.isfile(filepath):
                    total_size += os.path.getsize(filepath)
        return total_size

    def format_cache_size(self) -> str:
        """Get formatted cache size string."""
        size = self.get_cache_size()
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.1f} GB"
