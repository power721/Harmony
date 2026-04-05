import json
from pathlib import Path

from system.plugins.manager import PluginManager
from system.plugins.state_store import PluginStateStore


class _ContextFactory:
    def build(self, _manifest):
        return object()


def test_state_store_persists_enabled_flag(tmp_path: Path):
    store = PluginStateStore(tmp_path / "state.json")
    store.set_enabled("qqmusic", True, source="builtin", version="1.0.0")

    payload = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert payload["qqmusic"]["enabled"] is True


def test_manager_loads_builtin_plugin_and_persists_state(tmp_path: Path):
    builtin_root = tmp_path / "builtin"
    plugin_root = builtin_root / "qqmusic"
    plugin_root.mkdir(parents=True)

    (plugin_root / "plugin.json").write_text(
        json.dumps(
            {
                "id": "qqmusic",
                "name": "QQ Music",
                "version": "1.0.0",
                "api_version": "1",
                "entrypoint": "plugin_main.py",
                "entry_class": "QQMusicPlugin",
                "capabilities": ["sidebar"],
                "min_app_version": "0.1.0",
            }
        ),
        encoding="utf-8",
    )
    (plugin_root / "plugin_main.py").write_text(
        "class QQMusicPlugin:\n"
        "    plugin_id = 'qqmusic'\n"
        "    def register(self, context):\n"
        "        self.context = context\n"
        "    def unregister(self, context):\n"
        "        self.context = None\n",
        encoding="utf-8",
    )

    store = PluginStateStore(tmp_path / "state.json")
    manager = PluginManager(
        builtin_root=builtin_root,
        external_root=tmp_path / "external",
        state_store=store,
        context_factory=_ContextFactory(),
    )

    manager.load_enabled_plugins()

    state = store.get("qqmusic")
    assert state is not None
    assert state["enabled"] is True


def test_manager_skips_import_for_disabled_external_plugin(tmp_path: Path):
    external_root = tmp_path / "external"
    plugin_root = external_root / "danger"
    plugin_root.mkdir(parents=True)

    (plugin_root / "plugin.json").write_text(
        json.dumps(
            {
                "id": "danger",
                "name": "Danger Plugin",
                "version": "1.0.0",
                "api_version": "1",
                "entrypoint": "plugin_main.py",
                "entry_class": "DangerPlugin",
                "capabilities": ["sidebar"],
                "min_app_version": "0.1.0",
            }
        ),
        encoding="utf-8",
    )
    (plugin_root / "plugin_main.py").write_text(
        "raise RuntimeError('should not import disabled external plugin')\n"
        "class DangerPlugin:\n"
        "    plugin_id = 'danger'\n"
        "    def register(self, context):\n"
        "        pass\n"
        "    def unregister(self, context):\n"
        "        pass\n",
        encoding="utf-8",
    )

    store = PluginStateStore(tmp_path / "state.json")
    store.set_enabled("danger", False, source="external", version="1.0.0")
    manager = PluginManager(
        builtin_root=tmp_path / "builtin",
        external_root=external_root,
        state_store=store,
        context_factory=_ContextFactory(),
    )

    manager.load_enabled_plugins()

    state = store.get("danger")
    assert state is not None
    assert state["enabled"] is False
