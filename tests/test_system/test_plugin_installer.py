from pathlib import Path
import json
import shutil
import zipfile

import pytest

from system.plugins.errors import PluginInstallError
from system.plugins.installer import PluginInstaller, audit_plugin_imports
from system.plugins.loader import PluginLoader


def test_import_audit_rejects_host_internal_import(tmp_path: Path):
    plugin_root = tmp_path / "plugin"
    plugin_root.mkdir()
    (plugin_root / "plugin_main.py").write_text(
        "from services.library.library_service import LibraryService\n",
        encoding="utf-8",
    )

    with pytest.raises(PluginInstallError):
        audit_plugin_imports(plugin_root)


def test_import_audit_allows_plugin_relative_import_under_host_like_name(
    tmp_path: Path,
):
    plugin_root = tmp_path / "plugin"
    (plugin_root / "services").mkdir(parents=True)
    (plugin_root / "services" / "helper.py").write_text(
        "value = 1\n",
        encoding="utf-8",
    )
    (plugin_root / "plugin_main.py").write_text(
        "from .services.helper import value\n",
        encoding="utf-8",
    )

    audit_plugin_imports(plugin_root)


def _build_plugin_zip(tmp_path: Path, zip_name: str, files: dict[str, str]) -> Path:
    zip_path = tmp_path / zip_name
    with zipfile.ZipFile(zip_path, "w") as archive:
        for rel_path, content in files.items():
            archive.writestr(rel_path, content)
    return zip_path


def test_install_zip_rejects_missing_entrypoint(tmp_path: Path):
    installer = PluginInstaller(
        external_root=tmp_path / "external",
        temp_root=tmp_path / "temp",
    )
    plugin_zip = _build_plugin_zip(
        tmp_path,
        "missing_entry.zip",
        {
            "plugin.json": json.dumps(
                {
                    "id": "missing-entry",
                    "name": "Missing Entry",
                    "version": "1.0.0",
                    "api_version": "1",
                    "entrypoint": "plugin_main.py",
                    "entry_class": "MissingEntryPlugin",
                    "capabilities": ["sidebar"],
                    "min_app_version": "0.1.0",
                }
            ),
        },
    )

    with pytest.raises(PluginInstallError):
        installer.install_zip(plugin_zip)

    assert not (tmp_path / "external" / "missing-entry").exists()


def test_install_zip_rejects_missing_entry_class(tmp_path: Path):
    installer = PluginInstaller(
        external_root=tmp_path / "external",
        temp_root=tmp_path / "temp",
    )
    plugin_zip = _build_plugin_zip(
        tmp_path,
        "missing_class.zip",
        {
            "plugin.json": json.dumps(
                {
                    "id": "missing-class",
                    "name": "Missing Class",
                    "version": "1.0.0",
                    "api_version": "1",
                    "entrypoint": "plugin_main.py",
                    "entry_class": "ExpectedPluginClass",
                    "capabilities": ["sidebar"],
                    "min_app_version": "0.1.0",
                }
            ),
            "plugin_main.py": "class OtherPlugin:\n    pass\n",
        },
    )

    with pytest.raises(PluginInstallError):
        installer.install_zip(plugin_zip)

    assert not (tmp_path / "external" / "missing-class").exists()


def test_install_then_load_uses_installed_relative_module_code(tmp_path: Path):
    installer = PluginInstaller(
        external_root=tmp_path / "external",
        temp_root=tmp_path / "temp",
    )
    plugin_zip = _build_plugin_zip(
        tmp_path,
        "relative_plugin.zip",
        {
            "plugin.json": json.dumps(
                {
                    "id": "relative-installed",
                    "name": "Relative Installed",
                    "version": "1.0.0",
                    "api_version": "1",
                    "entrypoint": "plugin_main.py",
                    "entry_class": "RelativeInstalledPlugin",
                    "capabilities": ["sidebar"],
                    "min_app_version": "0.1.0",
                }
            ),
            "__init__.py": "",
            "lib/__init__.py": "",
            "lib/source.py": "def get_marker():\n    return 'from_zip'\n",
            "plugin_main.py": (
                "from .lib.source import get_marker\n\n"
                "class RelativeInstalledPlugin:\n"
                "    plugin_id = 'relative-installed'\n"
                "    def register(self, context):\n"
                "        pass\n"
                "    def unregister(self, context):\n"
                "        pass\n"
                "    def marker(self):\n"
                "        return get_marker()\n"
            ),
        },
    )

    installed_root = installer.install_zip(plugin_zip)
    (installed_root / "lib" / "source.py").write_text(
        "def get_marker():\n    return 'from_installed'\n",
        encoding="utf-8",
    )

    _manifest, plugin = PluginLoader().load_plugin(installed_root)

    assert plugin.marker() == "from_installed"


def test_install_zip_missing_manifest_raises_plugin_install_error(tmp_path: Path):
    installer = PluginInstaller(
        external_root=tmp_path / "external",
        temp_root=tmp_path / "temp",
    )
    plugin_zip = _build_plugin_zip(
        tmp_path,
        "missing_manifest.zip",
        {
            "plugin_main.py": "class MissingManifestPlugin:\n    pass\n",
        },
    )

    with pytest.raises(PluginInstallError):
        installer.install_zip(plugin_zip)


def test_install_zip_does_not_execute_plugin_top_level_code(tmp_path: Path):
    installer = PluginInstaller(
        external_root=tmp_path / "external",
        temp_root=tmp_path / "temp",
    )
    plugin_zip = _build_plugin_zip(
        tmp_path,
        "no_exec_on_install.zip",
        {
            "plugin.json": json.dumps(
                {
                    "id": "no-exec-on-install",
                    "name": "No Exec On Install",
                    "version": "1.0.0",
                    "api_version": "1",
                    "entrypoint": "plugin_main.py",
                    "entry_class": "NoExecPlugin",
                    "capabilities": ["sidebar"],
                    "min_app_version": "0.1.0",
                }
            ),
            "plugin_main.py": (
                "from pathlib import Path\n"
                "Path(__file__).with_name('import_executed.txt').write_text('1', encoding='utf-8')\n"
                "class NoExecPlugin:\n"
                "    plugin_id = 'no-exec-on-install'\n"
                "    def register(self, context):\n"
                "        pass\n"
                "    def unregister(self, context):\n"
                "        pass\n"
            ),
        },
    )

    installed_root = installer.install_zip(plugin_zip)

    assert not (installed_root / "import_executed.txt").exists()
    assert not (
        tmp_path / "temp" / "no_exec_on_install" / "import_executed.txt"
    ).exists()


def test_install_zip_accepts_single_wrapping_directory(tmp_path: Path):
    installer = PluginInstaller(
        external_root=tmp_path / "external",
        temp_root=tmp_path / "temp",
    )
    plugin_zip = _build_plugin_zip(
        tmp_path,
        "wrapped_plugin.zip",
        {
            "wrapped/plugin.json": json.dumps(
                {
                    "id": "wrapped-plugin",
                    "name": "Wrapped Plugin",
                    "version": "1.0.0",
                    "api_version": "1",
                    "entrypoint": "plugin_main.py",
                    "entry_class": "WrappedPlugin",
                    "capabilities": ["sidebar"],
                    "min_app_version": "0.1.0",
                }
            ),
            "wrapped/plugin_main.py": (
                "class WrappedPlugin:\n"
                "    plugin_id = 'wrapped-plugin'\n"
                "    def register(self, context):\n"
                "        pass\n"
                "    def unregister(self, context):\n"
                "        pass\n"
            ),
        },
    )

    installed_root = installer.install_zip(plugin_zip)

    assert installed_root == tmp_path / "external" / "wrapped-plugin"
    assert (installed_root / "plugin.json").exists()
    assert (installed_root / "plugin_main.py").exists()


def test_install_zip_rejects_path_traversal_entries(tmp_path: Path):
    installer = PluginInstaller(
        external_root=tmp_path / "external",
        temp_root=tmp_path / "temp",
    )
    plugin_zip = _build_plugin_zip(
        tmp_path,
        "zip_slip.zip",
        {
            "plugin.json": json.dumps(
                {
                    "id": "zip-slip",
                    "name": "Zip Slip",
                    "version": "1.0.0",
                    "api_version": "1",
                    "entrypoint": "plugin_main.py",
                    "entry_class": "ZipSlipPlugin",
                    "capabilities": ["sidebar"],
                    "min_app_version": "0.1.0",
                }
            ),
            "plugin_main.py": "class ZipSlipPlugin:\n    pass\n",
            "../escaped.txt": "owned\n",
        },
    )

    with pytest.raises(PluginInstallError, match="archive entry"):
        installer.install_zip(plugin_zip)

    assert not (tmp_path / "temp" / "escaped.txt").exists()
    assert not (tmp_path / "escaped.txt").exists()
    assert not (tmp_path / "external" / "zip-slip").exists()


def test_install_zip_replacement_is_transactional_on_copy_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    installer = PluginInstaller(
        external_root=tmp_path / "external",
        temp_root=tmp_path / "temp",
    )
    existing_root = tmp_path / "external" / "stable-plugin"
    existing_root.mkdir(parents=True)
    (existing_root / "version.txt").write_text("old", encoding="utf-8")

    plugin_zip = _build_plugin_zip(
        tmp_path,
        "stable_plugin.zip",
        {
            "plugin.json": json.dumps(
                {
                    "id": "stable-plugin",
                    "name": "Stable Plugin",
                    "version": "2.0.0",
                    "api_version": "1",
                    "entrypoint": "plugin_main.py",
                    "entry_class": "StablePlugin",
                    "capabilities": ["sidebar"],
                    "min_app_version": "0.1.0",
                }
            ),
            "plugin_main.py": "class StablePlugin:\n    pass\n",
            "version.txt": "new\n",
        },
    )

    original_copytree = shutil.copytree

    def _failing_copytree(src, dst, *args, **kwargs):
        if str(dst).endswith(".staging"):
            raise OSError("copy failed")
        return original_copytree(src, dst, *args, **kwargs)

    monkeypatch.setattr(shutil, "copytree", _failing_copytree)

    with pytest.raises(PluginInstallError):
        installer.install_zip(plugin_zip)

    assert existing_root.exists()
    assert (existing_root / "version.txt").read_text(encoding="utf-8") == "old"


def test_install_zip_rejects_reserved_suffix_plugin_id(tmp_path: Path):
    installer = PluginInstaller(
        external_root=tmp_path / "external",
        temp_root=tmp_path / "temp",
    )
    plugin_zip = _build_plugin_zip(
        tmp_path,
        "bad_suffix.zip",
        {
            "plugin.json": json.dumps(
                {
                    "id": "qqmusic.backup",
                    "name": "Bad Suffix",
                    "version": "1.0.0",
                    "api_version": "1",
                    "entrypoint": "plugin_main.py",
                    "entry_class": "BadSuffixPlugin",
                    "capabilities": ["sidebar"],
                    "min_app_version": "0.1.0",
                }
            ),
            "plugin_main.py": (
                "class BadSuffixPlugin:\n"
                "    plugin_id = 'qqmusic.backup'\n"
                "    def register(self, context):\n"
                "        pass\n"
                "    def unregister(self, context):\n"
                "        pass\n"
            ),
        },
    )

    with pytest.raises(PluginInstallError):
        installer.install_zip(plugin_zip)
