from __future__ import annotations

import os
from typing import Any, Optional

from .common import normalize_quality, parse_quality


class PluginOnlineDownloadService:
    """Plugin-local downloader for QQ Music online tracks."""

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
        context,
        config_manager=None,
        credential_provider=None,
        online_music_service=None,
        download_dir: Optional[str] = None,
    ):
        self._context = context
        self._config = config_manager
        self._provider = credential_provider
        self._online_service = online_music_service
        self._download_dir = download_dir or self._get_default_download_dir()
        self._last_download_qualities: dict[str, str] = {}
        os.makedirs(self._download_dir, exist_ok=True)

    def _get_default_download_dir(self) -> str:
        if self._config and hasattr(self._config, "get_online_music_download_dir"):
            config_dir = self._config.get_online_music_download_dir()
            if config_dir:
                if os.path.isabs(config_dir):
                    return config_dir
                return os.path.join(os.getcwd(), config_dir)
        return os.path.join(os.getcwd(), "data", "online_cache")

    def set_download_dir(self, path: str) -> None:
        self._download_dir = path
        os.makedirs(self._download_dir, exist_ok=True)

    def _find_existing_cached_path(self, song_mid: str) -> Optional[str]:
        for ext in self._CACHE_EXTENSIONS:
            candidate = os.path.join(self._download_dir, f"{song_mid}{ext}")
            if os.path.exists(candidate):
                return candidate
        return None

    def _get_extension_for_quality(self, quality: str) -> str:
        return parse_quality(quality).get("e", ".mp3")

    def _delete_other_cached_variants(self, song_mid: str, keep_path: str) -> None:
        keep_basename = os.path.basename(keep_path)
        for ext in self._CACHE_EXTENSIONS:
            candidate = os.path.join(self._download_dir, f"{song_mid}{ext}")
            if os.path.basename(candidate) == keep_basename:
                continue
            if os.path.exists(candidate):
                try:
                    os.remove(candidate)
                except OSError:
                    continue

    def get_cached_path(
        self,
        song_mid: str,
        quality: Optional[str] = None,
        provider_id: Optional[str] = None,
    ) -> str:
        del provider_id
        existing_path = self._find_existing_cached_path(song_mid)
        if existing_path:
            return existing_path
        selected_quality = quality or "320"
        ext = self._get_extension_for_quality(selected_quality)
        return os.path.join(self._download_dir, f"{song_mid}{ext}")

    def is_cached(
        self,
        song_mid: str,
        quality: Optional[str] = None,
        provider_id: Optional[str] = None,
    ) -> bool:
        _ = quality
        _ = provider_id
        return self._find_existing_cached_path(song_mid) is not None

    def pop_last_download_quality(self, song_mid: str) -> Optional[str]:
        return self._last_download_qualities.pop(song_mid, None)

    def download(
        self,
        song_mid: str,
        song_title: str = "",
        provider_id: Optional[str] = None,
        quality: Optional[str] = None,
        progress_callback=None,
        force: bool = False,
    ) -> Optional[str]:
        del song_title
        del provider_id
        selected_quality = quality or "320"

        cached_path = self.get_cached_path(song_mid, selected_quality)
        if not force and os.path.exists(cached_path):
            self._last_download_qualities[song_mid] = normalize_quality(selected_quality)
            return cached_path

        playback_info: dict[str, Any] | None = None
        if self._online_service and hasattr(self._online_service, "get_playback_url_info"):
            playback_info = self._online_service.get_playback_url_info(song_mid, selected_quality)
        if not playback_info and self._provider and hasattr(self._provider, "get_playback_url_info"):
            playback_info = self._provider.get_playback_url_info(song_mid, selected_quality)

        if not playback_info:
            return None

        url = playback_info.get("url")
        if not url:
            return None

        actual_quality = str(playback_info.get("quality", selected_quality))
        extension = playback_info.get("extension") or self._get_extension_for_quality(actual_quality)
        target_path = os.path.join(self._download_dir, f"{song_mid}{extension}")
        temp_path = f"{target_path}.tmp"

        request_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://y.qq.com/",
        }
        try:
            with self._context.http.stream("GET", url, headers=request_headers, timeout=60) as response:
                total_size = int(response.headers.get("content-length", 0) or 0)
                downloaded = 0
                with open(temp_path, "wb") as handle:
                    for chunk in response.iter_content(chunk_size=8192):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(downloaded, total_size)
            os.replace(temp_path, target_path)
            self._delete_other_cached_variants(song_mid, target_path)
            self._last_download_qualities[song_mid] = normalize_quality(actual_quality)
            return target_path
        except Exception:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            self._last_download_qualities.pop(song_mid, None)
            return None
