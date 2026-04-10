import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import zipfile

from PySide6.QtGui import QIcon

from scripts.build_plugin_zip import build_plugin_zip
from system.plugins.installer import PluginInstaller
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


class _LyricsRegistryContextFactory:
    def __init__(self, registry):
        self._registry = registry

    def build(self, manifest):
        registry = self._registry
        plugin_id = manifest.id

        class _ServicesBridge:
            def register_lyrics_source(self, source):
                registry.register_lyrics_source(plugin_id, source)

        class _Context:
            services = _ServicesBridge()

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


def test_manager_can_toggle_plugin_enabled_state_without_loading(tmp_path: Path):
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
        "        pass\n"
        "    def unregister(self, context):\n"
        "        pass\n",
        encoding="utf-8",
    )

    store = PluginStateStore(tmp_path / "state.json")
    manager = PluginManager(
        builtin_root=builtin_root,
        external_root=tmp_path / "external",
        state_store=store,
        context_factory=_ContextFactory(),
    )

    manager.set_plugin_enabled("qqmusic", False)
    disabled_state = store.get("qqmusic")
    manager.set_plugin_enabled("qqmusic", True)
    enabled_state = store.get("qqmusic")

    assert disabled_state is not None
    assert disabled_state["enabled"] is False
    assert enabled_state is not None
    assert enabled_state["enabled"] is True
    assert enabled_state["version"] == "1.0.0"


def test_manager_toggle_for_restart_required_plugin_only_updates_state(tmp_path: Path):
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
                "requires_restart_on_toggle": True,
            }
        ),
        encoding="utf-8",
    )
    (plugin_root / "plugin_main.py").write_text(
        "class QQMusicPlugin:\n"
        "    plugin_id = 'qqmusic'\n"
        "    def register(self, context):\n"
        "        pass\n"
        "    def unregister(self, context):\n"
        "        pass\n",
        encoding="utf-8",
    )

    store = PluginStateStore(tmp_path / "state.json")
    manager = PluginManager(
        builtin_root=builtin_root,
        external_root=tmp_path / "external",
        state_store=store,
        context_factory=_ContextFactory(),
    )
    manager._load_plugin_root = Mock()
    manager._unload_plugin = Mock()

    disable_result = manager.set_plugin_enabled("qqmusic", False)
    disabled_state = store.get("qqmusic")
    enable_result = manager.set_plugin_enabled("qqmusic", True)
    enabled_state = store.get("qqmusic")

    assert disable_result == {"requires_restart": True}
    assert enable_result == {"requires_restart": True}
    assert disabled_state is not None
    assert disabled_state["enabled"] is False
    assert enabled_state is not None
    assert enabled_state["enabled"] is True
    manager._load_plugin_root.assert_not_called()
    manager._unload_plugin.assert_not_called()


def test_manager_disabling_loaded_plugin_unregisters_runtime_lyrics_sources(tmp_path: Path):
    builtin_root = tmp_path / "builtin"
    plugin_root = builtin_root / "lyrics"
    plugin_root.mkdir(parents=True)

    (plugin_root / "plugin.json").write_text(
        json.dumps(
            {
                "id": "lyrics",
                "name": "Lyrics Plugin",
                "version": "1.0.0",
                "api_version": "1",
                "entrypoint": "plugin_main.py",
                "entry_class": "LyricsPlugin",
                "capabilities": ["lyrics_source"],
                "min_app_version": "0.1.0",
            }
        ),
        encoding="utf-8",
    )
    (plugin_root / "plugin_main.py").write_text(
        "class LyricsPlugin:\n"
        "    plugin_id = 'lyrics'\n"
        "    def register(self, context):\n"
        "        context.services.register_lyrics_source(object())\n"
        "    def unregister(self, context):\n"
        "        pass\n",
        encoding="utf-8",
    )

    store = PluginStateStore(tmp_path / "state.json")
    manager = PluginManager(
        builtin_root=builtin_root,
        external_root=tmp_path / "external",
        state_store=store,
        context_factory=_LyricsRegistryContextFactory(None),
    )
    manager._context_factory = _LyricsRegistryContextFactory(manager.registry)

    manager.load_enabled_plugins()
    assert len(manager.registry.lyrics_sources()) == 1

    manager.set_plugin_enabled("lyrics", False)

    assert manager.registry.lyrics_sources() == []


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


def test_constructor_failure_installs_then_records_runtime_load_error(tmp_path: Path):
    external_root = tmp_path / "external"
    installer = PluginInstaller(
        external_root=external_root,
        temp_root=tmp_path / "temp",
    )
    zip_path = tmp_path / "ctor_fails.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(
            "plugin.json",
            json.dumps(
                {
                    "id": "ctor-fails",
                    "name": "Ctor Fails",
                    "version": "1.0.0",
                    "api_version": "1",
                    "entrypoint": "plugin_main.py",
                    "entry_class": "CtorFailsPlugin",
                    "capabilities": ["sidebar"],
                    "min_app_version": "0.1.0",
                }
            ),
        )
        archive.writestr(
            "plugin_main.py",
            "class CtorFailsPlugin:\n"
            "    plugin_id = 'ctor-fails'\n"
            "    def __init__(self):\n"
            "        raise RuntimeError('ctor exploded')\n"
            "    def register(self, context):\n"
            "        pass\n"
            "    def unregister(self, context):\n"
            "        pass\n",
        )

    installed_root = installer.install_zip(zip_path)
    assert installed_root.exists()

    store = PluginStateStore(tmp_path / "state.json")
    manager = PluginManager(
        builtin_root=tmp_path / "builtin",
        external_root=external_root,
        state_store=store,
        context_factory=_ContextFactory(),
    )

    manager.load_enabled_plugins()

    state = store.get("ctor-fails")
    assert state is not None
    assert state["enabled"] is True
    assert state["load_error"]


def test_manager_calls_unregister_when_register_raises(tmp_path: Path):
    builtin_root = tmp_path / "builtin"
    plugin_root = builtin_root / "broken-unregister"
    plugin_root.mkdir(parents=True)
    flag_file = tmp_path / "unregister_called.txt"

    (plugin_root / "plugin.json").write_text(
        json.dumps(
            {
                "id": "broken-unregister",
                "name": "Broken Unregister",
                "version": "1.0.0",
                "api_version": "1",
                "entrypoint": "plugin_main.py",
                "entry_class": "BrokenUnregisterPlugin",
                "capabilities": ["sidebar"],
                "min_app_version": "0.1.0",
            }
        ),
        encoding="utf-8",
    )
    (plugin_root / "plugin_main.py").write_text(
        "from pathlib import Path\n"
        "from harmony_plugin_api.registry_types import SidebarEntrySpec\n\n"
        "class BrokenUnregisterPlugin:\n"
        "    plugin_id = 'broken-unregister'\n"
        "    def register(self, context):\n"
        "        context.ui.register_sidebar_entry(\n"
        "            SidebarEntrySpec(\n"
        "                plugin_id='broken-unregister',\n"
        "                entry_id='broken-unregister.sidebar',\n"
        "                title='Broken Unregister',\n"
        "                order=5,\n"
        "                icon_name=None,\n"
        "                page_factory=lambda _context, _parent: object(),\n"
        "            )\n"
        "        )\n"
        "        raise RuntimeError('register failed after partial work')\n"
        "    def unregister(self, context):\n"
        f"        Path(r'{flag_file}').write_text('1', encoding='utf-8')\n",
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

    state = store.get("broken-unregister")
    assert state is not None
    assert state["enabled"] is True
    assert state["load_error"]
    assert flag_file.exists()
    assert manager.registry.sidebar_entries() == []


def test_manager_load_enabled_plugins_is_idempotent(tmp_path: Path):
    builtin_root = tmp_path / "builtin"
    plugin_root = builtin_root / "once"
    plugin_root.mkdir(parents=True)
    (plugin_root / "plugin.json").write_text(
        json.dumps(
            {
                "id": "once",
                "name": "Once Plugin",
                "version": "1.0.0",
                "api_version": "1",
                "entrypoint": "plugin_main.py",
                "entry_class": "OncePlugin",
                "capabilities": ["sidebar"],
                "min_app_version": "0.1.0",
            }
        ),
        encoding="utf-8",
    )
    (plugin_root / "plugin_main.py").write_text(
        "from harmony_plugin_api.registry_types import SidebarEntrySpec\n\n"
        "class OncePlugin:\n"
        "    plugin_id = 'once'\n"
        "    def register(self, context):\n"
        "        context.ui.register_sidebar_entry(\n"
        "            SidebarEntrySpec(\n"
        "                plugin_id='once',\n"
        "                entry_id='once.sidebar',\n"
        "                title='Once',\n"
        "                order=7,\n"
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
    manager.load_enabled_plugins()

    assert len(manager.registry.sidebar_entries()) == 1


def test_external_plugin_failure_keeps_enabled_and_retries_after_fix(tmp_path: Path):
    external_root = tmp_path / "external"
    plugin_root = external_root / "retryable"
    plugin_root.mkdir(parents=True)
    (plugin_root / "plugin.json").write_text(
        json.dumps(
            {
                "id": "retryable",
                "name": "Retryable Plugin",
                "version": "1.0.0",
                "api_version": "1",
                "entrypoint": "plugin_main.py",
                "entry_class": "RetryablePlugin",
                "capabilities": ["sidebar"],
                "min_app_version": "0.1.0",
            }
        ),
        encoding="utf-8",
    )
    (plugin_root / "plugin_main.py").write_text(
        "class RetryablePlugin:\n"
        "    plugin_id = 'retryable'\n"
        "    def __init__(self):\n"
        "        raise RuntimeError('boom')\n"
        "    def register(self, context):\n"
        "        pass\n"
        "    def unregister(self, context):\n"
        "        pass\n",
        encoding="utf-8",
    )

    store = PluginStateStore(tmp_path / "state.json")
    store.set_enabled("retryable", True, source="external", version="1.0.0")
    first_manager = PluginManager(
        builtin_root=tmp_path / "builtin",
        external_root=external_root,
        state_store=store,
        context_factory=_RegistryContextFactory(None),
    )
    first_manager._context_factory = _RegistryContextFactory(first_manager.registry)
    first_manager.load_enabled_plugins()

    failed_state = store.get("retryable")
    assert failed_state is not None
    assert failed_state["enabled"] is True
    assert failed_state["load_error"]

    (plugin_root / "plugin_main.py").write_text(
        "from harmony_plugin_api.registry_types import SidebarEntrySpec\n\n"
        "class RetryablePlugin:\n"
        "    plugin_id = 'retryable'\n"
        "    def register(self, context):\n"
        "        context.ui.register_sidebar_entry(\n"
        "            SidebarEntrySpec(\n"
        "                plugin_id='retryable',\n"
        "                entry_id='retryable.sidebar',\n"
        "                title='Retryable',\n"
        "                order=9,\n"
        "                icon_name=None,\n"
        "                page_factory=lambda _context, _parent: object(),\n"
        "            )\n"
        "        )\n"
        "    def unregister(self, context):\n"
        "        pass\n",
        encoding="utf-8",
    )

    second_manager = PluginManager(
        builtin_root=tmp_path / "builtin",
        external_root=external_root,
        state_store=store,
        context_factory=_RegistryContextFactory(None),
    )
    second_manager._context_factory = _RegistryContextFactory(second_manager.registry)
    second_manager.load_enabled_plugins()

    recovered_state = store.get("retryable")
    assert recovered_state is not None
    assert recovered_state["enabled"] is True
    assert recovered_state["load_error"] is None
    assert [item.plugin_id for item in second_manager.registry.sidebar_entries()] == [
        "retryable"
    ]


def test_manager_startup_survives_corrupted_state_json(tmp_path: Path):
    builtin_root = tmp_path / "builtin"
    plugin_root = builtin_root / "safe"
    plugin_root.mkdir(parents=True)
    (plugin_root / "plugin.json").write_text(
        json.dumps(
            {
                "id": "safe",
                "name": "Safe Plugin",
                "version": "1.0.0",
                "api_version": "1",
                "entrypoint": "plugin_main.py",
                "entry_class": "SafePlugin",
                "capabilities": ["sidebar"],
                "min_app_version": "0.1.0",
            }
        ),
        encoding="utf-8",
    )
    (plugin_root / "plugin_main.py").write_text(
        "from harmony_plugin_api.registry_types import SidebarEntrySpec\n\n"
        "class SafePlugin:\n"
        "    plugin_id = 'safe'\n"
        "    def register(self, context):\n"
        "        context.ui.register_sidebar_entry(\n"
        "            SidebarEntrySpec(\n"
        "                plugin_id='safe',\n"
        "                entry_id='safe.sidebar',\n"
        "                title='Safe',\n"
        "                order=3,\n"
        "                icon_name=None,\n"
        "                page_factory=lambda _context, _parent: object(),\n"
        "            )\n"
        "        )\n"
        "    def unregister(self, context):\n"
        "        pass\n",
        encoding="utf-8",
    )

    state_path = tmp_path / "state.json"
    state_path.write_text("{broken", encoding="utf-8")
    store = PluginStateStore(state_path)
    manager = PluginManager(
        builtin_root=builtin_root,
        external_root=tmp_path / "external",
        state_store=store,
        context_factory=_RegistryContextFactory(None),
    )
    manager._context_factory = _RegistryContextFactory(manager.registry)

    manager.load_enabled_plugins()

    state = store.get("safe")
    assert state is not None
    assert state["enabled"] is True
    assert state["load_error"] is None
    assert [item.plugin_id for item in manager.registry.sidebar_entries()] == ["safe"]


def test_manager_skips_disabled_builtin_plugin(tmp_path: Path):
    builtin_root = tmp_path / "builtin"
    plugin_root = builtin_root / "builtin-disabled"
    plugin_root.mkdir(parents=True)
    (plugin_root / "plugin.json").write_text(
        json.dumps(
            {
                "id": "builtin-disabled",
                "name": "Builtin Disabled",
                "version": "1.0.0",
                "api_version": "1",
                "entrypoint": "plugin_main.py",
                "entry_class": "BuiltinDisabledPlugin",
                "capabilities": ["sidebar"],
                "min_app_version": "0.1.0",
            }
        ),
        encoding="utf-8",
    )
    (plugin_root / "plugin_main.py").write_text(
        "from harmony_plugin_api.registry_types import SidebarEntrySpec\n\n"
        "class BuiltinDisabledPlugin:\n"
        "    plugin_id = 'builtin-disabled'\n"
        "    def register(self, context):\n"
        "        context.ui.register_sidebar_entry(\n"
        "            SidebarEntrySpec(\n"
        "                plugin_id='builtin-disabled',\n"
        "                entry_id='builtin-disabled.sidebar',\n"
        "                title='Builtin Disabled',\n"
        "                order=4,\n"
        "                icon_name=None,\n"
        "                page_factory=lambda _context, _parent: object(),\n"
        "            )\n"
        "        )\n"
        "    def unregister(self, context):\n"
        "        pass\n",
        encoding="utf-8",
    )

    store = PluginStateStore(tmp_path / "state.json")
    store.set_enabled("builtin-disabled", False, source="builtin", version="1.0.0")
    manager = PluginManager(
        builtin_root=builtin_root,
        external_root=tmp_path / "external",
        state_store=store,
        context_factory=_RegistryContextFactory(None),
    )
    manager._context_factory = _RegistryContextFactory(manager.registry)

    manager.load_enabled_plugins()

    state = store.get("builtin-disabled")
    assert state is not None
    assert state["enabled"] is False
    assert manager.registry.sidebar_entries() == []


def test_manager_ignores_external_installer_scratch_directories(tmp_path: Path):
    external_root = tmp_path / "external"
    scratch_staging = external_root / "demo.staging"
    scratch_backup = external_root / "demo.backup"
    real_plugin = external_root / "real-plugin"
    scratch_staging.mkdir(parents=True)
    scratch_backup.mkdir(parents=True)
    real_plugin.mkdir(parents=True)

    for scratch_dir in (scratch_staging, scratch_backup):
        (scratch_dir / "plugin.json").write_text(
            json.dumps(
                {
                    "id": scratch_dir.name,
                    "name": scratch_dir.name,
                    "version": "1.0.0",
                    "api_version": "1",
                    "entrypoint": "plugin_main.py",
                    "entry_class": "ScratchPlugin",
                    "capabilities": ["sidebar"],
                    "min_app_version": "0.1.0",
                }
            ),
            encoding="utf-8",
        )
        (scratch_dir / "plugin_main.py").write_text(
            "raise RuntimeError('scratch directory should be ignored')\n"
            "class ScratchPlugin:\n"
            "    plugin_id = 'scratch'\n"
            "    def register(self, context):\n"
            "        pass\n"
            "    def unregister(self, context):\n"
            "        pass\n",
            encoding="utf-8",
        )

    (real_plugin / "plugin.json").write_text(
        json.dumps(
            {
                "id": "real-plugin",
                "name": "Real Plugin",
                "version": "1.0.0",
                "api_version": "1",
                "entrypoint": "plugin_main.py",
                "entry_class": "RealPlugin",
                "capabilities": ["sidebar"],
                "min_app_version": "0.1.0",
            }
        ),
        encoding="utf-8",
    )
    (real_plugin / "plugin_main.py").write_text(
        "from harmony_plugin_api.registry_types import SidebarEntrySpec\n\n"
        "class RealPlugin:\n"
        "    plugin_id = 'real-plugin'\n"
        "    def register(self, context):\n"
        "        context.ui.register_sidebar_entry(\n"
        "            SidebarEntrySpec(\n"
        "                plugin_id='real-plugin',\n"
        "                entry_id='real-plugin.sidebar',\n"
        "                title='Real Plugin',\n"
        "                order=6,\n"
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
        builtin_root=tmp_path / "builtin",
        external_root=external_root,
        state_store=store,
        context_factory=_RegistryContextFactory(None),
    )
    manager._context_factory = _RegistryContextFactory(manager.registry)

    discovered = manager.discover_roots()
    assert ("external", real_plugin) in discovered
    assert ("external", scratch_staging) not in discovered
    assert ("external", scratch_backup) not in discovered

    manager.load_enabled_plugins()

    state = store.get("real-plugin")
    assert state is not None
    assert state["enabled"] is True
    assert [item.plugin_id for item in manager.registry.sidebar_entries()] == [
        "real-plugin"
    ]


def test_manager_loads_real_builtin_plugins_from_repository(tmp_path: Path):
    class _UiBridge:
        def __init__(self):
            self.sidebar_entries = []
            self.settings_tabs = []

        def register_sidebar_entry(self, spec):
            self.sidebar_entries.append(spec)

        def register_settings_tab(self, spec):
            self.settings_tabs.append(spec)

    class _ServiceBridge:
        def __init__(self):
            self.lyrics_sources = []
            self.cover_sources = []
            self.artist_cover_sources = []
            self.online_providers = []
            self.media = object()

        def register_lyrics_source(self, source):
            self.lyrics_sources.append(source)

        def register_cover_source(self, source):
            self.cover_sources.append(source)

        def register_artist_cover_source(self, source):
            self.artist_cover_sources.append(source)

        def register_online_music_provider(self, provider):
            self.online_providers.append(provider)

    class _BuiltinContextFactory:
        def __init__(self):
            self.ui = _UiBridge()
            self.services = _ServiceBridge()

        def build(self, manifest):
            return SimpleNamespace(
                plugin_id=manifest.id,
                manifest=manifest,
                logger=object(),
                http=SimpleNamespace(get=lambda *_args, **_kwargs: None),
                events=object(),
                settings=SimpleNamespace(
                    get=lambda *_args, **_kwargs: None,
                    set=lambda *_args, **_kwargs: None,
                ),
                storage=SimpleNamespace(),
                ui=self.ui,
                services=self.services,
            )

    root = Path(__file__).resolve().parents[2]
    store = PluginStateStore(tmp_path / "state.json")
    context_factory = _BuiltinContextFactory()
    manager = PluginManager(
        builtin_root=root / "plugins" / "builtin",
        external_root=tmp_path / "external",
        state_store=store,
        context_factory=context_factory,
    )

    manager.load_enabled_plugins()

    loaded_ids = set(manager._loaded_plugins)
    assert "lrclib" in loaded_ids
    assert "qqmusic" in loaded_ids


def test_external_plugin_overrides_builtin_with_same_id(tmp_path: Path):
    builtin_root = tmp_path / "builtin"
    external_root = tmp_path / "external"
    builtin_plugin = builtin_root / "qqmusic"
    external_plugin = external_root / "qqmusic"
    builtin_plugin.mkdir(parents=True)
    external_plugin.mkdir(parents=True)

    for plugin_root, version, title in (
        (builtin_plugin, "1.0.0", "Builtin QQ Music"),
        (external_plugin, "1.1.0", "External QQ Music"),
    ):
        (plugin_root / "plugin.json").write_text(
            json.dumps(
                {
                    "id": "qqmusic",
                    "name": "QQ Music",
                    "version": version,
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
            "from harmony_plugin_api.registry_types import SidebarEntrySpec\n\n"
            "class QQMusicPlugin:\n"
            "    plugin_id = 'qqmusic'\n"
            "    def register(self, context):\n"
            "        context.ui.register_sidebar_entry(\n"
            "            SidebarEntrySpec(\n"
            f"                plugin_id='qqmusic', entry_id='qqmusic.sidebar', title='{title}', order=1, icon_name=None, page_factory=lambda _context, _parent: object(),\n"
            "            )\n"
            "        )\n"
            "    def unregister(self, context):\n"
            "        pass\n",
            encoding="utf-8",
        )

    store = PluginStateStore(tmp_path / "state.json")
    manager = PluginManager(
        builtin_root=builtin_root,
        external_root=external_root,
        state_store=store,
        context_factory=_RegistryContextFactory(None),
    )
    manager._context_factory = _RegistryContextFactory(manager.registry)

    manager.load_enabled_plugins()

    listed = manager.list_plugins()
    assert [item["id"] for item in listed] == ["qqmusic"]
    assert listed[0]["source"] == "external"
    assert listed[0]["version"] == "1.1.0"
    assert [item.title for item in manager.registry.sidebar_entries()] == ["External QQ Music"]


def test_external_only_qqmusic_plugin_loads_without_builtin_root(tmp_path: Path, qtbot):
    class _Signal:
        def connect(self, _callback):
            return None

        def disconnect(self, _callback):
            return None

    class _ThemeBridge:
        def register_widget(self, _widget):
            return None

        def get_qss(self, template: str) -> str:
            return template

        def current_theme(self):
            return SimpleNamespace(
                background="#101010",
                background_alt="#1a1a1a",
                background_hover="#202020",
                text="#ffffff",
                text_secondary="#b3b3b3",
                highlight="#1db954",
                highlight_hover="#1ed760",
                border="#404040",
                selection="#333333",
            )

        def get_popup_surface_style(self) -> str:
            return ""

        def get_completer_popup_style(self) -> str:
            return ""

    class _DialogBridge:
        def information(self, *_args, **_kwargs):
            return None

        def warning(self, *_args, **_kwargs):
            return None

        def question(self, *_args, **_kwargs):
            return None

        def critical(self, *_args, **_kwargs):
            return None

        def setup_title_bar(self, *_args, **_kwargs):
            return None

    class _UiBridge:
        def __init__(self):
            self._sidebar_entries = []
            self._settings_tabs = []
            self.theme = _ThemeBridge()
            self.dialogs = _DialogBridge()

        def register_sidebar_entry(self, spec):
            self._sidebar_entries.append(spec)

        def register_settings_tab(self, spec):
            self._settings_tabs.append(spec)

    class _RuntimeBridge:
        def create_online_music_service(self, **_kwargs):
            return SimpleNamespace(_has_qqmusic_credential=lambda: False)

        def create_online_download_service(self, **_kwargs):
            return SimpleNamespace()

        def get_icon(self, *_args, **_kwargs):
            return QIcon()

        def image_cache_get(self, _url: str):
            return None

        def image_cache_set(self, _url: str, _image_data: bytes):
            return None

        def image_cache_path(self, _url: str):
            return None

        def http_get_content(self, _url: str, **_kwargs):
            return None

        def cover_pixmap_cache_initialize(self):
            return None

        def cover_pixmap_cache_get(self, _cache_key: str):
            return None

        def cover_pixmap_cache_set(self, _cache_key: str, _pixmap):
            return None

        def bootstrap(self):
            return None

        def library_service(self):
            return None

        def favorites_service(self):
            return None

        def favorite_mids_from_library(self) -> set[str]:
            return set()

        def remove_library_favorite_by_mid(self, _mid: str) -> bool:
            return False

        def add_requests_to_favorites(self, _requests):
            return []

        def add_requests_to_playlist(self, _parent, _requests, _log_prefix: str):
            return []

        def add_track_ids_to_playlist(self, _parent, _track_ids, _log_prefix: str):
            return None

        def event_bus(self):
            return SimpleNamespace(
                language_changed=_Signal(),
                favorite_changed=_Signal(),
            )

    class _ServiceBridge:
        def __init__(self):
            self.media = SimpleNamespace()
            self.lyrics_sources = []
            self.cover_sources = []
            self.artist_cover_sources = []
            self.online_providers = []

        def register_lyrics_source(self, source):
            self.lyrics_sources.append(source)

        def register_cover_source(self, source):
            self.cover_sources.append(source)

        def register_artist_cover_source(self, source):
            self.artist_cover_sources.append(source)

        def register_online_music_provider(self, provider):
            self.online_providers.append(provider)

    class _ExternalOnlyContextFactory:
        def __init__(self):
            self.ui = _UiBridge()
            self.services = _ServiceBridge()
            self.runtime = _RuntimeBridge()

        def build(self, manifest):
            return SimpleNamespace(
                plugin_id=manifest.id,
                manifest=manifest,
                logger=SimpleNamespace(info=lambda *_args, **_kwargs: None),
                http=SimpleNamespace(get=lambda *_args, **_kwargs: None),
                events=SimpleNamespace(language_changed=_Signal()),
                language="zh",
                settings=SimpleNamespace(
                    get=lambda *_args, **_kwargs: None,
                    set=lambda *_args, **_kwargs: None,
                ),
                storage=SimpleNamespace(),
                ui=self.ui,
                runtime=self.runtime,
                services=self.services,
            )

    plugin_root = Path("plugins/builtin/qqmusic")
    output_zip = tmp_path / "qqmusic.zip"
    build_plugin_zip(plugin_root, output_zip)

    installer = PluginInstaller(
        external_root=tmp_path / "external",
        temp_root=tmp_path / "temp",
    )
    installer.install_zip(output_zip)

    context_factory = _ExternalOnlyContextFactory()
    manager = PluginManager(
        builtin_root=tmp_path / "builtin-empty",
        external_root=tmp_path / "external",
        state_store=PluginStateStore(tmp_path / "state.json"),
        context_factory=context_factory,
    )

    manager.load_enabled_plugins()

    assert "qqmusic" in manager._loaded_plugins
    assert len(context_factory.ui._sidebar_entries) == 1
    assert len(context_factory.ui._settings_tabs) == 1
    page = context_factory.ui._sidebar_entries[0].page_factory(None, None)
    qtbot.addWidget(page)
    assert page is not None
    assert len(context_factory.services.online_providers) == 1


def test_discover_roots_ignores_non_plugin_directories(tmp_path: Path):
    builtin_root = tmp_path / "builtin"
    builtin_root.mkdir()
    (builtin_root / "__pycache__").mkdir()
    real_plugin = builtin_root / "real"
    real_plugin.mkdir()
    (real_plugin / "plugin.json").write_text(
        json.dumps(
            {
                "id": "real",
                "name": "Real",
                "version": "1.0.0",
                "api_version": "1",
                "entrypoint": "plugin_main.py",
                "entry_class": "RealPlugin",
                "capabilities": ["sidebar"],
                "min_app_version": "0.1.0",
            }
        ),
        encoding="utf-8",
    )

    manager = PluginManager(
        builtin_root=builtin_root,
        external_root=tmp_path / "external",
        state_store=PluginStateStore(tmp_path / "state.json"),
        context_factory=_ContextFactory(),
    )

    discovered = manager.discover_roots()

    assert ("builtin", real_plugin) in discovered
    assert all(path.name != "__pycache__" for _source, path in discovered)


def test_discover_roots_skips_invalid_manifest_plugin(tmp_path: Path):
    builtin_root = tmp_path / "builtin"
    external_root = tmp_path / "external"
    builtin_root.mkdir()
    external_root.mkdir()

    good_plugin = builtin_root / "good"
    good_plugin.mkdir()
    (good_plugin / "plugin.json").write_text(
        json.dumps(
            {
                "id": "good",
                "name": "Good",
                "version": "1.0.0",
                "api_version": "1",
                "entrypoint": "plugin_main.py",
                "entry_class": "GoodPlugin",
                "capabilities": ["sidebar"],
                "min_app_version": "0.1.0",
            }
        ),
        encoding="utf-8",
    )
    (good_plugin / "plugin_main.py").write_text(
        "class GoodPlugin:\n    pass\n",
        encoding="utf-8",
    )

    broken_plugin = external_root / "broken"
    broken_plugin.mkdir()
    (broken_plugin / "plugin.json").write_text(
        json.dumps({"name": "Broken"}),
        encoding="utf-8",
    )

    manager = PluginManager(
        builtin_root=builtin_root,
        external_root=external_root,
        state_store=PluginStateStore(tmp_path / "state.json"),
        context_factory=_ContextFactory(),
    )

    discovered = manager.discover_roots()
    listed = manager.list_plugins()

    assert discovered == [("builtin", good_plugin)]
    assert [plugin["id"] for plugin in listed] == ["good"]
