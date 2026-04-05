import zipfile
from pathlib import Path

from scripts.build_plugin_zip import build_plugin_zip


def test_build_plugin_zip_contains_manifest_and_entrypoint(tmp_path: Path):
    plugin_root = Path("plugins/builtin/qqmusic")
    output_zip = tmp_path / "qqmusic.zip"

    build_plugin_zip(plugin_root, output_zip)

    with zipfile.ZipFile(output_zip) as archive:
        names = set(archive.namelist())

    assert "plugin.json" in names
    assert "plugin_main.py" in names
