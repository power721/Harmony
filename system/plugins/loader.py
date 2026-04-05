from __future__ import annotations

import importlib.util
import json
import re
import sys
import types
from pathlib import Path

from harmony_plugin_api.manifest import PluginManifest

from .errors import PluginLoadError


class PluginLoader:
    def read_manifest(self, plugin_root: Path) -> PluginManifest:
        return PluginManifest.from_dict(
            json.loads((plugin_root / "plugin.json").read_text(encoding="utf-8"))
        )

    def load_plugin(self, plugin_root: Path, manifest: PluginManifest | None = None):
        if manifest is None:
            manifest = self.read_manifest(plugin_root)
        module_path = plugin_root / manifest.entrypoint
        if not module_path.exists():
            raise PluginLoadError(f"Entrypoint file does not exist: {module_path}")

        safe_id = re.sub(r"[^0-9a-zA-Z_]", "_", manifest.id)
        package_name = f"_harmony_plugin_{safe_id}"
        package_module = sys.modules.get(package_name)
        if package_module is None:
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
            plugin_class = getattr(module, manifest.entry_class)
            return manifest, plugin_class()
        except Exception as exc:
            raise PluginLoadError(
                f"Failed to load plugin '{manifest.id}': {exc}"
            ) from exc
