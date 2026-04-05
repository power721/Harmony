from pathlib import Path
import json
import zipfile

import pytest

from system.plugins.errors import PluginInstallError
from system.plugins.installer import PluginInstaller, audit_plugin_imports
from system.plugins.loader import PluginLoader


def test_import_audit_rejects_host_internal_import(tmp_path: Path):
    plugin_root = tmp_path / "plugin"
    plugin_root.mkdir()
    (plugin_root / "plugin_main.py").write_text(
        "from services.lyrics.qqmusic_lyrics import QQMusicClient\n",
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
