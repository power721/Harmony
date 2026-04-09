from __future__ import annotations

import logging
import time
from pathlib import Path
from urllib.parse import urlparse

from infrastructure import HttpClient
from .installer import PluginInstaller
from .loader import PluginLoader
from .registry import PluginRegistry

logger = logging.getLogger(__name__)


class PluginManager:
    def __init__(self, builtin_root: Path, external_root: Path, state_store, context_factory) -> None:
        self._builtin_root = builtin_root
        self._external_root = external_root
        self._state_store = state_store
        self._context_factory = context_factory
        self._loader = PluginLoader()
        self._installer = PluginInstaller(
            external_root=external_root,
            temp_root=external_root.parent / "tmp",
        )
        self.registry = PluginRegistry()
        self._loaded_plugins: dict[str, tuple[object, object, object]] = {}

    def _read_manifest_or_none(self, plugin_root: Path):
        try:
            return self._loader.read_manifest(plugin_root)
        except Exception as exc:
            logger.warning(
                "[PluginManager] Ignoring invalid plugin manifest at %s: %s",
                plugin_root,
                exc,
            )
            return None

    def _load_plugin_root(self, source: str, plugin_root: Path) -> None:
        manifest = None
        state = None
        plugin = None
        context = None
        started_at = time.perf_counter()
        try:
            manifest = self._loader.read_manifest(plugin_root)
            if manifest.id in self._loaded_plugins:
                logger.debug("[PluginManager] Skip already loaded plugin %s", manifest.id)
                return

            state = self._state_store.get(manifest.id)
            if state and state.get("enabled") is False:
                logger.info("[PluginManager] Skip disabled plugin %s", manifest.id)
                return

            logger.info(
                "[PluginManager] Loading plugin %s from %s (%s)",
                manifest.id,
                plugin_root,
                source,
            )
            manifest, plugin = self._loader.load_plugin(plugin_root, manifest)
            context = self._context_factory.build(manifest)
            plugin.register(context)
            self._loaded_plugins[manifest.id] = (manifest, plugin, context)
            duration_ms = (time.perf_counter() - started_at) * 1000
            logger.info(
                "[PluginManager] Loaded plugin %s in %.1fms",
                manifest.id,
                duration_ms,
            )
            self._state_store.set_enabled(
                manifest.id,
                True if state is None else bool(state.get("enabled", True)),
                source=source,
                version=manifest.version,
                load_error=None,
            )
        except Exception as exc:
            plugin_id = manifest.id if manifest is not None else plugin_root.name
            version = manifest.version if manifest is not None else ""
            enabled_on_error = True if state is None else bool(state.get("enabled", True))
            if plugin is not None and context is not None:
                try:
                    plugin.unregister(context)
                except Exception:
                    pass
            logger.exception(
                "[PluginManager] Failed to load plugin %s from %s",
                plugin_id,
                plugin_root,
            )
            self.registry.unregister_plugin(plugin_id)
            self._loaded_plugins.pop(plugin_id, None)
            self._state_store.set_enabled(
                plugin_id,
                enabled_on_error,
                source=source,
                version=version,
                load_error=str(exc),
            )

    def _unload_plugin(self, plugin_id: str) -> None:
        loaded = self._loaded_plugins.pop(plugin_id, None)
        if loaded is None:
            self.registry.unregister_plugin(plugin_id)
            return

        _manifest, plugin, context = loaded
        try:
            plugin.unregister(context)
        except Exception:
            logger.exception("[PluginManager] Failed to unregister plugin %s", plugin_id)
        finally:
            self.registry.unregister_plugin(plugin_id)

    def discover_roots(self) -> list[tuple[str, Path]]:
        def _is_plugin_root(path: Path) -> bool:
            return path.is_dir() and (path / "plugin.json").exists()

        roots = []
        if self._builtin_root.exists():
            roots.extend(
                ("builtin", path)
                for path in self._builtin_root.iterdir()
                if _is_plugin_root(path)
            )
        if self._external_root.exists():
            roots.extend(
                ("external", path)
                for path in self._external_root.iterdir()
                if _is_plugin_root(path)
                and not path.name.endswith(".staging")
                and not path.name.endswith(".backup")
            )
        selected: dict[str, tuple[str, Path]] = {}
        for source, plugin_root in sorted(roots, key=lambda item: (item[0], item[1].name)):
            manifest = self._read_manifest_or_none(plugin_root)
            if manifest is None:
                continue
            current = selected.get(manifest.id)
            if current is None or source == "external":
                selected[manifest.id] = (source, plugin_root)
        return sorted(selected.values(), key=lambda item: (item[0], item[1].name))

    def load_enabled_plugins(self) -> None:
        roots = self.discover_roots()
        logger.info("[PluginManager] Discovered %s plugin roots", len(roots))
        for source, plugin_root in roots:
            self._load_plugin_root(source, plugin_root)

    def list_plugins(self) -> list[dict]:
        plugins = []
        for source, plugin_root in self.discover_roots():
            manifest = self._read_manifest_or_none(plugin_root)
            if manifest is None:
                continue
            state = self._state_store.get(manifest.id) or {}
            plugins.append(
                {
                    "id": manifest.id,
                    "name": manifest.name,
                    "version": manifest.version,
                    "source": source,
                    "enabled": bool(state.get("enabled", True)),
                    "load_error": state.get("load_error"),
                }
            )
        return plugins

    def set_plugin_enabled(self, plugin_id: str, enabled: bool) -> None:
        for source, plugin_root in self.discover_roots():
            manifest = self._read_manifest_or_none(plugin_root)
            if manifest is None:
                continue
            if manifest.id != plugin_id:
                continue
            existing = self._state_store.get(plugin_id) or {}
            self._state_store.set_enabled(
                plugin_id,
                enabled,
                source=existing.get("source", source),
                version=existing.get("version", manifest.version),
                load_error=existing.get("load_error"),
            )
            if enabled:
                self._load_plugin_root(source, plugin_root)
            else:
                self._unload_plugin(plugin_id)
            return
        raise KeyError(f"Unknown plugin: {plugin_id}")

    def install_zip(self, zip_path: str | Path) -> Path:
        return self._installer.install_zip(Path(zip_path))

    def install_from_url(self, url: str) -> Path:
        parsed = urlparse(url)
        archive_name = Path(parsed.path).name or "plugin.zip"
        download_path = self._installer._temp_root / archive_name
        download_path.parent.mkdir(parents=True, exist_ok=True)
        response = HttpClient.shared().get(url, timeout=60)
        response.raise_for_status()
        download_path.write_bytes(response.content)
        return self.install_zip(download_path)
