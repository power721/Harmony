from __future__ import annotations

import ast
import json
import shutil
import zipfile
from pathlib import Path, PurePosixPath

from harmony_plugin_api.manifest import PluginManifest

from .errors import PluginInstallError

_FORBIDDEN_ROOT_IMPORTS = {
    "app",
    "domain",
    "services",
    "repositories",
    "infrastructure",
    "system",
    "ui",
}


def _import_roots_from_node(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name.split(".")[0] for alias in node.names]
    if isinstance(node, ast.ImportFrom):
        if node.level and node.level > 0:
            return []
        if not node.module:
            return []
        return [node.module.split(".")[0]]
    if not isinstance(node, ast.Call):
        return []

    if (
        isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "importlib"
        and node.func.attr == "import_module"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    ):
        return [node.args[0].value.split(".")[0]]

    if (
        isinstance(node.func, ast.Name)
        and node.func.id == "__import__"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    ):
        return [node.args[0].value.split(".")[0]]

    return []


def audit_plugin_imports(plugin_root: Path) -> None:
    for py_file in plugin_root.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            names = _import_roots_from_node(node)
            if not names:
                continue

            if any(name in _FORBIDDEN_ROOT_IMPORTS for name in names):
                raise PluginInstallError(f"Forbidden host import in {py_file}")


class PluginInstaller:
    def __init__(self, external_root: Path, temp_root: Path) -> None:
        self._external_root = external_root
        self._temp_root = temp_root

    def _validate_plugin_id(self, plugin_id: str) -> None:
        if plugin_id.endswith(".staging") or plugin_id.endswith(".backup"):
            raise PluginInstallError(
                f"Plugin id uses reserved suffix: {plugin_id}"
            )

    def _load_manifest(self, plugin_root: Path) -> PluginManifest:
        manifest_path = plugin_root / "plugin.json"
        raw = manifest_path.read_text(encoding="utf-8")
        return PluginManifest.from_dict(json.loads(raw))

    def _resolve_plugin_root(self, extract_root: Path) -> Path:
        """Support archives that either unpack directly or under a single wrapper directory."""
        if (extract_root / "plugin.json").exists():
            return extract_root

        child_dirs = [
            path
            for path in extract_root.iterdir()
            if path.is_dir() and path.name != "__MACOSX"
        ]
        if len(child_dirs) == 1 and (child_dirs[0] / "plugin.json").exists():
            return child_dirs[0]

        return extract_root

    def _validate_archive_entries(
        self,
        archive: zipfile.ZipFile,
        extract_root: Path,
    ) -> None:
        root = extract_root.resolve()
        for info in archive.infolist():
            raw_name = str(info.filename or "")
            if not raw_name:
                raise PluginInstallError("Plugin archive entry name cannot be empty")

            normalized = raw_name.replace("\\", "/")
            member_path = PurePosixPath(normalized)
            if member_path.is_absolute():
                raise PluginInstallError(
                    f"Plugin archive entry escapes extraction root: {raw_name}"
                )

            if any(part == ".." for part in member_path.parts):
                raise PluginInstallError(
                    f"Plugin archive entry escapes extraction root: {raw_name}"
                )

            if member_path.parts and member_path.parts[0].endswith(":"):
                raise PluginInstallError(
                    f"Plugin archive entry uses unsupported drive path: {raw_name}"
                )

            candidate = (extract_root / Path(*member_path.parts)).resolve()
            try:
                candidate.relative_to(root)
            except ValueError as exc:
                raise PluginInstallError(
                    f"Plugin archive entry escapes extraction root: {raw_name}"
                ) from exc

    def _validate_entrypoint_structure(
        self, plugin_root: Path, manifest: PluginManifest
    ) -> None:
        entrypoint_path = plugin_root / manifest.entrypoint
        if not entrypoint_path.exists():
            raise PluginInstallError(
                f"Entrypoint file does not exist: {entrypoint_path}"
            )

        source = entrypoint_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(entrypoint_path))
        has_entry_class = any(
            isinstance(node, ast.ClassDef) and node.name == manifest.entry_class
            for node in ast.walk(tree)
        )
        if not has_entry_class:
            raise PluginInstallError(
                f"Entrypoint missing class '{manifest.entry_class}' for '{manifest.id}'"
            )

    def install_zip(self, zip_path: Path) -> Path:
        try:
            extract_root = self._temp_root / zip_path.stem
            if extract_root.exists():
                shutil.rmtree(extract_root)
            extract_root.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(zip_path) as archive:
                self._validate_archive_entries(archive, extract_root)
                archive.extractall(extract_root)

            plugin_root = self._resolve_plugin_root(extract_root)
            audit_plugin_imports(plugin_root)
            manifest = self._load_manifest(plugin_root)
            self._validate_plugin_id(manifest.id)
            self._validate_entrypoint_structure(plugin_root, manifest)

            self._external_root.mkdir(parents=True, exist_ok=True)
            final_root = self._external_root / manifest.id
            staging_root = self._external_root / f"{manifest.id}.staging"
            backup_root = self._external_root / f"{manifest.id}.backup"

            if staging_root.exists():
                shutil.rmtree(staging_root)
            if backup_root.exists():
                shutil.rmtree(backup_root)

            shutil.copytree(plugin_root, staging_root)

            had_existing = final_root.exists()
            if had_existing:
                final_root.replace(backup_root)

            try:
                staging_root.replace(final_root)
            except Exception:
                if had_existing and backup_root.exists() and not final_root.exists():
                    backup_root.replace(final_root)
                if staging_root.exists():
                    shutil.rmtree(staging_root)
                raise
            else:
                if backup_root.exists():
                    shutil.rmtree(backup_root)
            return final_root
        except PluginInstallError:
            raise
        except Exception as exc:
            raise PluginInstallError(f"Failed to install plugin from {zip_path}: {exc}") from exc
