from __future__ import annotations

from pathlib import Path

from .loader import PluginLoader
from .registry import PluginRegistry


class PluginManager:
    def __init__(self, builtin_root: Path, external_root: Path, state_store, context_factory) -> None:
        self._builtin_root = builtin_root
        self._external_root = external_root
        self._state_store = state_store
        self._context_factory = context_factory
        self._loader = PluginLoader()
        self.registry = PluginRegistry()
        self._loaded_plugins: dict[str, tuple[object, object]] = {}

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
            )
        return roots

    def load_enabled_plugins(self) -> None:
        for source, plugin_root in self.discover_roots():
            if source == "external":
                manifest = self._loader.read_manifest(plugin_root)
                state = self._state_store.get(manifest.id)
                if state and state.get("enabled") is False:
                    continue
                manifest, plugin = self._loader.load_plugin(plugin_root, manifest)
            else:
                manifest, plugin = self._loader.load_plugin(plugin_root)
                state = self._state_store.get(manifest.id)

            context = self._context_factory.build(manifest)
            plugin.register(context)
            self._loaded_plugins[manifest.id] = (manifest, plugin)
            self._state_store.set_enabled(
                manifest.id,
                True if state is None else bool(state.get("enabled", True)),
                source=source,
                version=manifest.version,
            )
