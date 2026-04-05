import json
from pathlib import Path
from types import SimpleNamespace
import zipfile

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
