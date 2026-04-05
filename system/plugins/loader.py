from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from harmony_plugin_api.manifest import PluginManifest

from .errors import PluginLoadError


class PluginLoader:
    def load_plugin(self, plugin_root: Path):
        manifest = PluginManifest.from_dict(
            json.loads((plugin_root / "plugin.json").read_text(encoding="utf-8"))
        )
        module_path = plugin_root / manifest.entrypoint
        spec = importlib.util.spec_from_file_location(
            f"plugin_{manifest.id}", module_path
        )
        if spec is None or spec.loader is None:
            raise PluginLoadError(f"Cannot load entrypoint: {module_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        plugin_class = getattr(module, manifest.entry_class)
        return manifest, plugin_class()
