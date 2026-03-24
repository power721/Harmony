"""
Online music download service.
Downloads online music to local cache for playback.
"""

import logging
import os
from typing import Dict, Optional, Callable, Any, TYPE_CHECKING

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
        if quality is None:
            quality = self._config.get_qqmusic_quality() if self._config else "320"
        ext = ".flac" if quality in ("master", "flac") else ".mp3"
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
        path = self.get_cached_path(song_mid, quality)
        return os.path.exists(path)

    def download(
        self,
        song_mid: str,
        song_title: str = "",
        quality: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
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
            quality = self._config.get_qqmusic_quality() if self._config else "320"

        # Check cache first
        cached_path = self.get_cached_path(song_mid, quality)
        if os.path.exists(cached_path):
            logger.info(f"Song already cached: {cached_path}")
            return cached_path

        # Get playback URL - prefer online service (supports remote API)
        url = None
        actual_quality = quality

        if self._online_service:
            # Use online service (supports both QQ Music and remote API)
            url = self._online_service.get_playback_url(song_mid, quality)
            if url:
                # Determine actual quality from URL extension
                if ".flac" in url:
                    actual_quality = "flac"
                elif ".mp3" in url:
                    actual_quality = "320"

        elif self._qqmusic:
            # Fallback to QQ Music direct API
            quality_fallback = ["320", "128", "flac"]
            for q in quality_fallback:
                url = self._qqmusic.get_playback_url(song_mid, q)
                if url:
                    actual_quality = q
                    break

        if not url:
            logger.error(f"Failed to get playback URL for {song_mid}, song may require VIP")
            return None

        # Update cached path with actual quality
        cached_path = self.get_cached_path(song_mid, actual_quality)

        # Download file
        try:
            import requests

            logger.info(f"Downloading: {song_title or song_mid}")

            # Emit download started event
            self._event_bus.download_started.emit(song_mid)

            response = requests.get(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Referer': 'https://y.qq.com/',
                },
                stream=True,
                timeout=60
            )
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            # Write to temp file first
            temp_path = cached_path + ".tmp"
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(downloaded, total_size)

            # Rename to final path
            os.rename(temp_path, cached_path)

            logger.info(f"Download complete: {cached_path}")

            # Extract metadata from downloaded file
            metadata = self._extract_metadata(song_mid, cached_path)

            # Emit download completed event
            self._event_bus.download_completed.emit(song_mid, cached_path)

            # Emit metadata loaded event
            if metadata:
                self._event_bus.online_track_metadata_loaded.emit(song_mid, metadata)

            return cached_path

        except Exception as e:
            logger.error(f"Download failed: {e}")
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
            print(metadata)
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
            import requests
            url = f"https://api.ygking.top/api/song/detail"
            params = {"mid": song_mid}

            response = requests.get(url, params=params, timeout=10)
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
