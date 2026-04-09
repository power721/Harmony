import zipfile
from pathlib import Path

from system.plugins.installer import PluginInstaller
from scripts.build_plugin_zip import build_plugin_zip


def test_build_plugin_zip_contains_manifest_and_entrypoint(tmp_path: Path):
    plugin_root = Path("plugins/builtin/qqmusic")
    output_zip = tmp_path / "qqmusic.zip"

    build_plugin_zip(plugin_root, output_zip)

    with zipfile.ZipFile(output_zip) as archive:
        names = set(archive.namelist())

    assert "plugin.json" in names
    assert "plugin_main.py" in names


def test_built_qqmusic_zip_is_installable(tmp_path: Path):
    plugin_root = Path("plugins/builtin/qqmusic")
    output_zip = tmp_path / "qqmusic.zip"
    build_plugin_zip(plugin_root, output_zip)

    installer = PluginInstaller(
        external_root=tmp_path / "external",
        temp_root=tmp_path / "temp",
    )
    installed_root = installer.install_zip(output_zip)

    assert installed_root.name == "qqmusic"
    assert (installed_root / "plugin.json").exists()
    assert (installed_root / "plugin_main.py").exists()
