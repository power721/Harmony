from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
import types
from pathlib import Path

from harmony_plugin_api.manifest import PluginManifest

from .errors import PluginLoadError


class PluginLoader:
    def _package_name(self, manifest_id: str, plugin_root: Path) -> str:
        safe_id = re.sub(r"[^0-9a-zA-Z_]", "_", manifest_id)
        root_hash = hashlib.sha1(
            str(plugin_root.resolve()).encode("utf-8")
        ).hexdigest()[:12]
        return f"_harmony_plugin_{safe_id}_{root_hash}"

    def _purge_package_modules(self, package_name: str) -> None:
        names = [
            module_name
            for module_name in sys.modules
            if module_name == package_name or module_name.startswith(f"{package_name}.")
        ]
        for module_name in names:
            sys.modules.pop(module_name, None)

    def read_manifest(self, plugin_root: Path) -> PluginManifest:
        return PluginManifest.from_dict(
            json.loads((plugin_root / "plugin.json").read_text(encoding="utf-8"))
        )

    def _load_entry_module(
        self,
        plugin_root: Path,
        manifest: PluginManifest,
    ):
        if manifest is None:
            manifest = self.read_manifest(plugin_root)
        module_path = plugin_root / manifest.entrypoint
        if not module_path.exists():
            raise PluginLoadError(f"Entrypoint file does not exist: {module_path}")

        package_name = self._package_name(manifest.id, plugin_root)
        self._purge_package_modules(package_name)
        package_module = types.ModuleType(package_name)
        package_module.__path__ = [str(plugin_root)]
        sys.modules[package_name] = package_module

        entrypoint_module = Path(manifest.entrypoint).with_suffix("")
        module_name = f"{package_name}.{'.'.join(entrypoint_module.parts)}"
        spec = importlib.util.spec_from_file_location(
            module_name, module_path
        )
        if spec is None or spec.loader is None:
            raise PluginLoadError(f"Cannot load entrypoint: {module_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
            return module
        except Exception as exc:
            raise PluginLoadError(
                f"Failed to load plugin '{manifest.id}': {exc}"
            ) from exc

    def validate_plugin_structure(
        self, plugin_root: Path, manifest: PluginManifest | None = None
    ) -> PluginManifest:
        if manifest is None:
            manifest = self.read_manifest(plugin_root)
        module = self._load_entry_module(plugin_root, manifest)
        if not hasattr(module, manifest.entry_class):
            raise PluginLoadError(
                f"Entrypoint missing class '{manifest.entry_class}' for '{manifest.id}'"
            )
        return manifest

    def load_plugin(self, plugin_root: Path, manifest: PluginManifest | None = None):
        if manifest is None:
            manifest = self.read_manifest(plugin_root)
        module = self._load_entry_module(plugin_root, manifest)
        if not hasattr(module, manifest.entry_class):
            raise PluginLoadError(
                f"Entrypoint missing class '{manifest.entry_class}' for '{manifest.id}'"
            )
        try:
            plugin_class = getattr(module, manifest.entry_class)
            return manifest, plugin_class()
        except Exception as exc:
            raise PluginLoadError(
                f"Failed to load plugin '{manifest.id}': {exc}"
            ) from exc
