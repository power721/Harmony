from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class OnlineDownloadGateway:
    """Host-side generic online download gateway backed by plugin providers."""

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

    def __init__(self, config_manager=None, plugin_manager=None, event_bus=None):
        self._config = config_manager
        self._plugin_manager = plugin_manager
        self._event_bus = event_bus
        self._download_dir = self._get_default_download_dir()
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

    def _iter_cache_dirs(self) -> list[str]:
        cache_dirs = [self._download_dir]
        try:
            for entry in os.scandir(self._download_dir):
                if entry.is_dir():
                    cache_dirs.append(entry.path)
        except FileNotFoundError:
            return cache_dirs
        return cache_dirs

    def _provider_cache_dir(self, provider_id: Optional[str]) -> str:
        normalized = str(provider_id or "").strip()
        if not normalized:
            return self._download_dir
        safe_provider = normalized.replace("/", "_").replace("\\", "_")
        provider_dir = os.path.join(self._download_dir, safe_provider)
        os.makedirs(provider_dir, exist_ok=True)
        return provider_dir

    def _find_existing_cached_path_for_provider(
        self,
        song_mid: str,
        provider_id: Optional[str] = None,
    ) -> Optional[str]:
        if provider_id:
            provider_dir = self._provider_cache_dir(provider_id)
            for ext in self._CACHE_EXTENSIONS:
                candidate = os.path.join(provider_dir, f"{song_mid}{ext}")
                if os.path.exists(candidate):
                    return candidate
        return self._find_existing_cached_path(song_mid)

    def _get_provider(self, provider_id: str | None = None):
        manager = self._plugin_manager() if callable(self._plugin_manager) else self._plugin_manager
        if manager is None:
            return None
        providers = manager.registry.online_providers()
        normalized_provider_id = str(provider_id or "").strip()
        if normalized_provider_id.lower() == "online":
            normalized_provider_id = ""
            if len(providers) == 1:
                provider = providers[0]
                if callable(getattr(provider, "download_track", None)):
                    return provider
        for provider in providers:
            if normalized_provider_id and getattr(provider, "provider_id", None) != normalized_provider_id:
                continue
            if callable(getattr(provider, "download_track", None)):
                return provider
        return None

    @staticmethod
    def _normalize_quality_options(options) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        if not options:
            return normalized
        for item in options:
            if isinstance(item, str):
                value = item.strip()
                if value:
                    normalized.append({"value": value, "label": value})
                continue
            if not isinstance(item, dict):
                continue
            value = str(item.get("value", "") or "").strip()
            if not value:
                continue
            label = str(item.get("label", "") or value).strip() or value
            normalized.append({"value": value, "label": label})
        return normalized

    def _normalize_quality(self, quality: str) -> str:
        return str(quality or "").strip().lower()

    def _guess_extension(self, quality: str) -> str:
        q = self._normalize_quality(quality)
        if q in {"flac", "master", "atmos_2", "atmos_51", "dolby", "hires"}:
            return ".flac"
        if q in {"ape"}:
            return ".ape"
        if q in {"dts"}:
            return ".dts"
        if q.startswith("ogg"):
            return ".ogg"
        if q.startswith("aac"):
            return ".m4a"
        return ".mp3"

    def get_cached_path(
        self,
        song_mid: str,
        quality: Optional[str] = None,
        provider_id: Optional[str] = None,
    ) -> str:
        cache_dir = self._provider_cache_dir(provider_id)
        existing_path = self._find_existing_cached_path_for_provider(song_mid, provider_id)
        if existing_path:
            return existing_path
        ext = self._guess_extension(quality or "320")
        return os.path.join(cache_dir, f"{song_mid}{ext}")

    def is_cached(
        self,
        song_mid: str,
        quality: Optional[str] = None,
        provider_id: Optional[str] = None,
    ) -> bool:
        _ = quality
        return self._find_existing_cached_path_for_provider(song_mid, provider_id) is not None

    def pop_last_download_quality(self, song_mid: str) -> Optional[str]:
        return self._last_download_qualities.pop(song_mid, None)

    def get_download_qualities(
        self,
        song_mid: str,
        provider_id: Optional[str] = None,
    ) -> list[dict[str, str]]:
        provider = self._get_provider(provider_id)
        if provider is None:
            return []
        getter = getattr(provider, "get_download_qualities", None)
        if not callable(getter):
            return []
        try:
            return self._normalize_quality_options(getter(song_mid))
        except Exception:
            logger.exception(
                "[OnlineDownloadGateway] Failed to get download qualities: provider=%s song=%s",
                provider_id,
                song_mid,
            )
            return []

    def delete_cached_file(self, song_mid: str) -> bool:
        deleted = False
        for cache_dir in self._iter_cache_dirs():
            for ext in self._CACHE_EXTENSIONS:
                path = os.path.join(cache_dir, f"{song_mid}{ext}")
                if os.path.exists(path):
                    try:
                        os.remove(path)
                        deleted = True
                    except OSError:
                        logger.warning("[OnlineDownloadGateway] Failed to remove %s", path)
        self._last_download_qualities.pop(song_mid, None)
        return deleted

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
        selected_quality = quality or "320"

        cached_path = self.get_cached_path(song_mid, selected_quality, provider_id=provider_id)
        if not force and os.path.exists(cached_path):
            self._last_download_qualities[song_mid] = self._normalize_quality(selected_quality)
            return cached_path

        provider = self._get_provider(provider_id)
        if provider is None:
            logger.error(f"[OnlineDownloadGateway] [{provider_id}] No online provider available")
            return None

        if self._event_bus and hasattr(self._event_bus, "download_started"):
            self._event_bus.download_started.emit(song_mid)

        try:
            target_dir = self._provider_cache_dir(provider_id)
            redownload = getattr(provider, "redownload_track", None)
            if force and callable(redownload):
                result = redownload(
                    track_id=song_mid,
                    quality=selected_quality,
                    target_dir=target_dir,
                    progress_callback=progress_callback,
                )
            else:
                result = provider.download_track(
                    track_id=song_mid,
                    quality=selected_quality,
                    target_dir=target_dir,
                    progress_callback=progress_callback,
                    force=force,
                )
            if isinstance(result, str):
                local_path = result
            elif isinstance(result, os.PathLike):
                local_path = os.fspath(result)
            elif isinstance(result, dict):
                local_path = str(result.get("local_path", "") or "")
            else:
                local_path = ""
            if not local_path:
                raise RuntimeError("provider returned empty local path")
            actual_quality = selected_quality
            if isinstance(result, dict):
                actual_quality = str(result.get("quality", selected_quality) or selected_quality)
            self._last_download_qualities[song_mid] = self._normalize_quality(actual_quality)
            if self._event_bus and hasattr(self._event_bus, "download_completed"):
                self._event_bus.download_completed.emit(song_mid, local_path)
            return local_path
        except Exception as exc:
            self._last_download_qualities.pop(song_mid, None)
            if self._event_bus and hasattr(self._event_bus, "download_error"):
                self._event_bus.download_error.emit(song_mid, str(exc))
            return None
