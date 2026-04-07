import json
from pathlib import Path

import pytest

from system.plugins.errors import PluginLoadError
from system.plugins.installer import audit_plugin_imports
from system.plugins.loader import PluginLoader


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


def test_plugin_import_audit_rejects_host_imports(tmp_path: Path):
    plugin_root = tmp_path / "bad_imports"
    plugin_root.mkdir()
    (plugin_root / "plugin_main.py").write_text(
        "from ui.dialogs.message_dialog import MessageDialog\n",
        encoding="utf-8",
    )

    with pytest.raises(Exception):
        audit_plugin_imports(plugin_root)


def test_plugin_import_audit_rejects_dynamic_host_imports(tmp_path: Path):
    plugin_root = tmp_path / "bad_dynamic_imports"
    plugin_root.mkdir()
    (plugin_root / "plugin_main.py").write_text(
        "import importlib\n"
        "\n"
        "importlib.import_module('system.plugins.plugin_sdk_runtime')\n",
        encoding="utf-8",
    )

    with pytest.raises(Exception):
        audit_plugin_imports(plugin_root)


def test_plugin_import_audit_rejects_dynamic_dunder_imports(tmp_path: Path):
    plugin_root = tmp_path / "bad_dunder_imports"
    plugin_root.mkdir()
    (plugin_root / "plugin_main.py").write_text(
        "__import__('ui.dialogs.message_dialog')\n",
        encoding="utf-8",
    )

    with pytest.raises(Exception):
        audit_plugin_imports(plugin_root)


def test_runtime_import_guard_rejects_host_module_import(tmp_path: Path):
    plugin_root = tmp_path / "bad_runtime"
    plugin_root.mkdir()
    (plugin_root / "plugin.json").write_text(
        json.dumps(
            {
                "id": "bad-runtime",
                "name": "Bad Runtime",
                "version": "1.0.0",
                "api_version": "1",
                "entrypoint": "plugin_main.py",
                "entry_class": "BadRuntimePlugin",
                "capabilities": ["sidebar"],
                "min_app_version": "0.1.0",
            }
        ),
        encoding="utf-8",
    )
    (plugin_root / "plugin_main.py").write_text(
        "from ui.dialogs.message_dialog import MessageDialog\n"
        "\n"
        "class BadRuntimePlugin:\n"
        "    plugin_id = 'bad-runtime'\n"
        "    def register(self, context):\n"
        "        return None\n"
        "    def unregister(self, context):\n"
        "        return None\n",
        encoding="utf-8",
    )

    with pytest.raises(PluginLoadError):
        PluginLoader().load_plugin(plugin_root)


def test_qqmusic_ui_modules_do_not_import_sdk_runtime_modules_directly():
    plugin_files = [
        Path("plugins/builtin/qqmusic/lib/dialog_title_bar.py"),
        Path("plugins/builtin/qqmusic/lib/login_dialog.py"),
        Path("plugins/builtin/qqmusic/lib/settings_tab.py"),
        Path("plugins/builtin/qqmusic/lib/runtime_bridge.py"),
    ]

    for path in plugin_files:
        source = path.read_text(encoding="utf-8")
        assert "from harmony_plugin_api.ui import" not in source
        assert "from harmony_plugin_api.runtime import" not in source


def test_qqmusic_runtime_bridge_does_not_import_host_bridge_modules_by_name():
    source = Path("plugins/builtin/qqmusic/lib/runtime_bridge.py").read_text(
        encoding="utf-8"
    )

    assert "system.plugins.plugin_sdk_runtime" not in source
    assert "system.plugins.plugin_sdk_ui" not in source
