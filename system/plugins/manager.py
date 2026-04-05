from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from infrastructure import HttpClient
from .installer import PluginInstaller
from .loader import PluginLoader
from .registry import PluginRegistry


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

    def discover_roots(self) -> list[tuple[str, Path]]:
        roots = []
        if self._builtin_root.exists():
            roots.extend(
                ("builtin", path) for path in self._builtin_root.iterdir() if path.is_dir()
            )
        if self._external_root.exists():
            roots.extend(
                ("external", path)
                for path in self._external_root.iterdir()
                if path.is_dir()
                and not path.name.endswith(".staging")
                and not path.name.endswith(".backup")
            )
        return sorted(roots, key=lambda item: (item[0], item[1].name))

    def load_enabled_plugins(self) -> None:
        for source, plugin_root in self.discover_roots():
            manifest = None
            state = None
            plugin = None
            context = None
            try:
                manifest = self._loader.read_manifest(plugin_root)
                if manifest.id in self._loaded_plugins:
                    continue

                state = self._state_store.get(manifest.id)
                if state and state.get("enabled") is False:
                    continue

                manifest, plugin = self._loader.load_plugin(plugin_root, manifest)
                context = self._context_factory.build(manifest)
                plugin.register(context)
                self._loaded_plugins[manifest.id] = (manifest, plugin, context)
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
                self.registry.unregister_plugin(plugin_id)
                self._loaded_plugins.pop(plugin_id, None)
                self._state_store.set_enabled(
                    plugin_id,
                    enabled_on_error,
                    source=source,
                    version=version,
                    load_error=str(exc),
                )

    def list_plugins(self) -> list[dict]:
        plugins = []
        for source, plugin_root in self.discover_roots():
            manifest = self._loader.read_manifest(plugin_root)
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
