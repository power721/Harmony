from pathlib import Path
import json
import zipfile

import pytest

from system.plugins.errors import PluginInstallError
from system.plugins.installer import PluginInstaller, audit_plugin_imports


def test_import_audit_rejects_host_internal_import(tmp_path: Path):
    plugin_root = tmp_path / "plugin"
    plugin_root.mkdir()
    (plugin_root / "plugin_main.py").write_text(
        "from services.lyrics.qqmusic_lyrics import QQMusicClient\n",
        encoding="utf-8",
    )

    with pytest.raises(PluginInstallError):
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
