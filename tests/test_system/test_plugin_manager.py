import json
from pathlib import Path

from system.plugins.manager import PluginManager
from system.plugins.state_store import PluginStateStore


class _ContextFactory:
    def build(self, _manifest):
        return object()


class _RegistryContextFactory:
    def __init__(self, registry):
        self._registry = registry

    def build(self, manifest):
        registry = self._registry
        plugin_id = manifest.id

        class _UiBridge:
            def register_sidebar_entry(self, spec):
                registry.register_sidebar_entry(plugin_id, spec)

            def register_settings_tab(self, _spec):
                return None

        class _Context:
            ui = _UiBridge()

        return _Context()


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


def test_manager_loads_plugin_with_relative_import(tmp_path: Path):
    builtin_root = tmp_path / "builtin"
    plugin_root = builtin_root / "relative"
    (plugin_root / "lib").mkdir(parents=True)

    (plugin_root / "plugin.json").write_text(
        json.dumps(
            {
                "id": "relative",
                "name": "Relative Plugin",
                "version": "1.0.0",
                "api_version": "1",
                "entrypoint": "plugin_main.py",
                "entry_class": "RelativePlugin",
                "capabilities": ["sidebar"],
                "min_app_version": "0.1.0",
            }
        ),
        encoding="utf-8",
    )
    (plugin_root / "__init__.py").write_text("", encoding="utf-8")
    (plugin_root / "lib" / "__init__.py").write_text("", encoding="utf-8")
    (plugin_root / "lib" / "factory.py").write_text(
        "from harmony_plugin_api.registry_types import SidebarEntrySpec\n\n"
        "def make_spec(plugin_id):\n"
        "    return SidebarEntrySpec(\n"
        "        plugin_id=plugin_id,\n"
        "        entry_id=f'{plugin_id}.sidebar',\n"
        "        title='Relative',\n"
        "        order=10,\n"
        "        icon_name=None,\n"
        "        page_factory=lambda _context, _parent: object(),\n"
        "    )\n",
        encoding="utf-8",
    )
    (plugin_root / "plugin_main.py").write_text(
        "from .lib.factory import make_spec\n\n"
        "class RelativePlugin:\n"
        "    plugin_id = 'relative'\n"
        "    def register(self, context):\n"
        "        context.ui.register_sidebar_entry(make_spec(self.plugin_id))\n"
        "    def unregister(self, context):\n"
        "        pass\n",
        encoding="utf-8",
    )

    store = PluginStateStore(tmp_path / "state.json")
    manager = PluginManager(
        builtin_root=builtin_root,
        external_root=tmp_path / "external",
        state_store=store,
        context_factory=_RegistryContextFactory(None),
    )
    manager._context_factory = _RegistryContextFactory(manager.registry)

    manager.load_enabled_plugins()

    assert [item.plugin_id for item in manager.registry.sidebar_entries()] == ["relative"]


def test_manager_continues_after_plugin_failure_and_persists_load_error(tmp_path: Path):
    builtin_root = tmp_path / "builtin"
    broken_root = builtin_root / "broken"
    healthy_root = builtin_root / "healthy"
    broken_root.mkdir(parents=True)
    healthy_root.mkdir(parents=True)

    (broken_root / "plugin.json").write_text(
        json.dumps(
            {
                "id": "broken",
                "name": "Broken Plugin",
                "version": "1.0.0",
                "api_version": "1",
                "entrypoint": "plugin_main.py",
                "entry_class": "BrokenPlugin",
                "capabilities": ["sidebar"],
                "min_app_version": "0.1.0",
            }
        ),
        encoding="utf-8",
    )
    (broken_root / "plugin_main.py").write_text(
        "from harmony_plugin_api.registry_types import SidebarEntrySpec\n\n"
        "class BrokenPlugin:\n"
        "    plugin_id = 'broken'\n"
        "    def register(self, context):\n"
        "        context.ui.register_sidebar_entry(\n"
        "            SidebarEntrySpec(\n"
        "                plugin_id='broken',\n"
        "                entry_id='broken.sidebar',\n"
        "                title='Broken',\n"
        "                order=1,\n"
        "                icon_name=None,\n"
        "                page_factory=lambda _context, _parent: object(),\n"
        "            )\n"
        "        )\n"
        "        raise RuntimeError('broken plugin failed')\n"
        "    def unregister(self, context):\n"
        "        pass\n",
        encoding="utf-8",
    )

    (healthy_root / "plugin.json").write_text(
        json.dumps(
            {
                "id": "healthy",
                "name": "Healthy Plugin",
                "version": "1.0.0",
                "api_version": "1",
                "entrypoint": "plugin_main.py",
                "entry_class": "HealthyPlugin",
                "capabilities": ["sidebar"],
                "min_app_version": "0.1.0",
            }
        ),
        encoding="utf-8",
    )
    (healthy_root / "plugin_main.py").write_text(
        "from harmony_plugin_api.registry_types import SidebarEntrySpec\n\n"
        "class HealthyPlugin:\n"
        "    plugin_id = 'healthy'\n"
        "    def register(self, context):\n"
        "        context.ui.register_sidebar_entry(\n"
        "            SidebarEntrySpec(\n"
        "                plugin_id='healthy',\n"
        "                entry_id='healthy.sidebar',\n"
        "                title='Healthy',\n"
        "                order=2,\n"
        "                icon_name=None,\n"
        "                page_factory=lambda _context, _parent: object(),\n"
        "            )\n"
        "        )\n"
        "    def unregister(self, context):\n"
        "        pass\n",
        encoding="utf-8",
    )

    store = PluginStateStore(tmp_path / "state.json")
    manager = PluginManager(
        builtin_root=builtin_root,
        external_root=tmp_path / "external",
        state_store=store,
        context_factory=_RegistryContextFactory(None),
    )
    manager._context_factory = _RegistryContextFactory(manager.registry)

    manager.load_enabled_plugins()

    broken_state = store.get("broken")
    healthy_state = store.get("healthy")
    assert broken_state is not None
    assert healthy_state is not None
    assert broken_state["load_error"]
    assert healthy_state["enabled"] is True
    assert [item.plugin_id for item in manager.registry.sidebar_entries()] == ["healthy"]
