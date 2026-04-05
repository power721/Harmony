from pathlib import Path

from system.plugins.installer import audit_plugin_imports


def test_plugin_import_audit_allows_sdk_only_imports(tmp_path: Path):
    plugin_root = tmp_path / "qqmusic"
    plugin_root.mkdir()
    (plugin_root / "plugin_main.py").write_text(
        "from harmony_plugin_api.plugin import HarmonyPlugin\n",
        encoding="utf-8",
    )

    audit_plugin_imports(plugin_root)


def test_builtin_qqmusic_plugin_passes_import_audit():
    audit_plugin_imports(Path("plugins/builtin/qqmusic"))
