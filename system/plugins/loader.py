from __future__ import annotations

import builtins
import hashlib
import importlib.util
import json
import logging
import re
import sys
import types
from contextlib import contextmanager
from pathlib import Path

from harmony_plugin_api.manifest import PluginManifest

from .errors import PluginLoadError
from .installer import audit_plugin_imports

logger = logging.getLogger(__name__)
_FORBIDDEN_IMPORT_ROOTS = {
    "app",
    "domain",
    "services",
    "repositories",
    "infrastructure",
    "system",
    "ui",
}


class PluginLoader:
    @contextmanager
    def _guard_imports(self, package_name: str):
        original_import = builtins.__import__

        def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if level == 0 and name:
                caller_name = ""
                if isinstance(globals, dict):
                    caller_name = str(globals.get("__name__", "") or "")
                root = name.split(".")[0]
                if (
                    caller_name.startswith(package_name)
                    and root in _FORBIDDEN_IMPORT_ROOTS
                ):
                    raise ImportError(f"Forbidden host import: {name}")
            return original_import(name, globals, locals, fromlist, level)

        builtins.__import__ = _guarded_import
        try:
            yield
        finally:
            builtins.__import__ = original_import

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
        try:
            audit_plugin_imports(plugin_root)
        except Exception as exc:
            raise PluginLoadError(
                f"Failed to load plugin '{manifest.id}': {exc}"
            ) from exc
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
            logger.debug(
                "[PluginLoader] Executing entry module %s for plugin %s",
                module_name,
                manifest.id,
            )
            with self._guard_imports(package_name):
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
            logger.debug(
                "[PluginLoader] Instantiating plugin class %s for %s",
                manifest.entry_class,
                manifest.id,
            )
            return manifest, plugin_class()
        except Exception as exc:
            raise PluginLoadError(
                f"Failed to load plugin '{manifest.id}': {exc}"
            ) from exc
