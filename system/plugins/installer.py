from __future__ import annotations

import ast
import json
import shutil
import zipfile
from pathlib import Path

from harmony_plugin_api.manifest import PluginManifest

from .errors import PluginInstallError
from .loader import PluginLoader

_FORBIDDEN_ROOT_IMPORTS = {
    "app",
    "domain",
    "services",
    "repositories",
    "infrastructure",
    "system",
    "ui",
}


def audit_plugin_imports(plugin_root: Path) -> None:
    for py_file in plugin_root.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level and node.level > 0:
                    continue
                if not node.module:
                    continue
                names = [node.module.split(".")[0]]
            else:
                continue

            if any(name in _FORBIDDEN_ROOT_IMPORTS for name in names):
                raise PluginInstallError(f"Forbidden host import in {py_file}")


class PluginInstaller:
    def __init__(self, external_root: Path, temp_root: Path) -> None:
        self._external_root = external_root
        self._temp_root = temp_root
        self._loader = PluginLoader()

    def install_zip(self, zip_path: Path) -> Path:
        extract_root = self._temp_root / zip_path.stem
        if extract_root.exists():
            shutil.rmtree(extract_root)
        extract_root.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(extract_root)

        audit_plugin_imports(extract_root)
        manifest = PluginManifest.from_dict(
            json.loads((extract_root / "plugin.json").read_text(encoding="utf-8"))
        )
        try:
            self._loader.load_plugin(extract_root, manifest)
        except Exception as exc:
            raise PluginInstallError(
                f"Invalid plugin package structure for '{manifest.id}': {exc}"
            ) from exc

        self._external_root.mkdir(parents=True, exist_ok=True)
        final_root = self._external_root / manifest.id
        if final_root.exists():
            shutil.rmtree(final_root)
        shutil.copytree(extract_root, final_root)
        return final_root
