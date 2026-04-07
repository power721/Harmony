# Plugin System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a host-owned plugin runtime, migrate LRCLIB into a built-in plugin, migrate QQ Music into a removable plugin, and support plugin install from local zip files and direct URL downloads inside the settings dialog.

**Architecture:** Add a new runtime under `system/plugins/` plus a stable SDK under `harmony_plugin_api/`. The host keeps ownership of lifecycle, settings persistence, playback/download bridges, sidebar mounting, and settings-shell UI; plugins register sidebar entries, settings tabs, lyrics sources, cover sources, and online-music providers through the SDK. LRCLIB proves the minimal built-in path first, then QQ Music moves behind the same runtime and is packaged as a zip artifact.

**Tech Stack:** Python 3.11, PySide6, pytest, pytest-qt, `uv`, JSON manifests, `zipfile`, `importlib`, `ast`

---

## File Map

### New Runtime and SDK Files

- Create: `harmony_plugin_api/__init__.py` — public SDK exports
- Create: `harmony_plugin_api/manifest.py` — plugin manifest model and capability validation
- Create: `harmony_plugin_api/plugin.py` — `HarmonyPlugin` entry interface
- Create: `harmony_plugin_api/context.py` — plugin context and bridge protocols
- Create: `harmony_plugin_api/registry_types.py` — sidebar and settings tab specs
- Create: `harmony_plugin_api/lyrics.py` — plugin-side lyrics protocol and result models
- Create: `harmony_plugin_api/cover.py` — plugin-side cover protocols and result models
- Create: `harmony_plugin_api/online.py` — plugin-side online provider protocol and DTOs
- Create: `harmony_plugin_api/media.py` — plugin playback/download request DTOs
- Create: `system/plugins/__init__.py` — host runtime exports
- Create: `system/plugins/errors.py` — install/load/runtime exceptions
- Create: `system/plugins/registry.py` — runtime extension registry and per-plugin rollback
- Create: `system/plugins/state_store.py` — `data/plugins/state.json` persistence
- Create: `system/plugins/loader.py` — manifest parsing and entry loading
- Create: `system/plugins/installer.py` — local zip and URL install logic plus import audit
- Create: `system/plugins/manager.py` — discovery, enable/disable, load/unload
- Create: `system/plugins/host_services.py` — host implementations of SDK bridge protocols
- Create: `system/plugins/media_bridge.py` — host bridge for cache/download/playback handoff

### New Built-In Plugin Files

- Create: `plugins/builtin/lrclib/plugin.json`
- Create: `plugins/builtin/lrclib/plugin_main.py`
- Create: `plugins/builtin/lrclib/lib/lrclib_source.py`
- Create: `plugins/builtin/qqmusic/plugin.json`
- Create: `plugins/builtin/qqmusic/plugin_main.py`
- Create: `plugins/builtin/qqmusic/lib/client.py`
- Create: `plugins/builtin/qqmusic/lib/login_dialog.py`
- Create: `plugins/builtin/qqmusic/lib/settings_tab.py`
- Create: `plugins/builtin/qqmusic/lib/lyrics_source.py`
- Create: `plugins/builtin/qqmusic/lib/cover_source.py`
- Create: `plugins/builtin/qqmusic/lib/artist_cover_source.py`
- Create: `plugins/builtin/qqmusic/lib/provider.py`
- Create: `plugins/builtin/qqmusic/lib/root_view.py`

### New UI and Tooling Files

- Create: `ui/dialogs/plugin_management_tab.py`
- Create: `scripts/build_plugin_zip.py`

### New Tests

- Create: `tests/test_system/test_plugin_manifest.py`
- Create: `tests/test_system/test_plugin_registry.py`
- Create: `tests/test_system/test_plugin_manager.py`
- Create: `tests/test_system/test_plugin_installer.py`
- Create: `tests/test_system/test_plugin_online_bridge.py`
- Create: `tests/test_system/test_plugin_import_guard.py`
- Create: `tests/test_app/test_plugin_bootstrap.py`
- Create: `tests/test_ui/test_plugin_settings_tab.py`
- Create: `tests/test_ui/test_plugin_sidebar_integration.py`
- Create: `tests/test_services/test_plugin_lyrics_registry.py`
- Create: `tests/test_services/test_plugin_cover_registry.py`
- Create: `tests/test_plugins/test_lrclib_plugin.py`
- Create: `tests/test_plugins/test_qqmusic_plugin.py`
- Create: `tests/test_system/test_plugin_packaging.py`

### Existing Files to Modify

- Modify: `app/bootstrap.py:344-414` — remove QQ-specific bootstrap wiring and initialize plugin manager/bridges
- Modify: `system/config.py:68-80,693-800` — remove host-owned QQ setting helpers after the plugin takes over namespaced settings
- Modify: `services/lyrics/lyrics_service.py:57-72` — replace hardcoded QQ/LRCLIB source registration with registry-driven sources
- Modify: `services/metadata/cover_service.py:46-74` — merge plugin cover and artist-cover sources into host search flow
- Modify: `services/online/download_service.py:42-177` — accept explicit quality instead of reading QQ host settings
- Modify: `services/sources/lyrics_sources.py:137-380` — delete QQ and LRCLIB host source implementations after migration
- Modify: `services/sources/cover_sources.py:121-180` — delete QQ host cover implementation after migration
- Modify: `services/sources/artist_cover_sources.py:79-130` — delete QQ host artist-cover implementation after migration
- Modify: `services/sources/__init__.py:9-52` — stop exporting migrated QQ/LRCLIB source classes
- Modify: `ui/dialogs/settings_dialog.py:214-858` — add host-owned `插件` tab and mount plugin settings tabs dynamically
- Modify: `ui/windows/components/sidebar.py:17-176` — support runtime plugin entries instead of only fixed constants
- Modify: `ui/windows/main_window.py:394-474,523-528` — stop hardcoding `OnlineMusicView` and mount plugin pages from the registry
- Modify: `translations/en.json`
- Modify: `translations/zh.json`

### Existing Files to Delete After Migration

- Delete: `services/lyrics/qqmusic_lyrics.py`
- Delete: `services/cloud/qqmusic/__init__.py`
- Delete: `services/cloud/qqmusic/client.py`
- Delete: `services/cloud/qqmusic/common.py`
- Delete: `services/cloud/qqmusic/crypto.py`
- Delete: `services/cloud/qqmusic/qr_login.py`
- Delete: `services/cloud/qqmusic/qqmusic_service.py`
- Delete: `services/cloud/qqmusic/tripledes.py`

### Verification Rule

The repository baseline is not clean under `uv run pytest tests/`, so each task below verifies only the focused files touched in that task. Do not use the unstable full-suite run as a success criterion for plugin work.

### Task 1: Add SDK Contracts and Manifest Validation

**Files:**
- Create: `harmony_plugin_api/__init__.py`
- Create: `harmony_plugin_api/manifest.py`
- Create: `harmony_plugin_api/plugin.py`
- Create: `harmony_plugin_api/context.py`
- Create: `harmony_plugin_api/registry_types.py`
- Create: `harmony_plugin_api/lyrics.py`
- Create: `harmony_plugin_api/cover.py`
- Create: `harmony_plugin_api/online.py`
- Create: `harmony_plugin_api/media.py`
- Test: `tests/test_system/test_plugin_manifest.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest

from harmony_plugin_api.manifest import PluginManifest, PluginManifestError
from harmony_plugin_api.registry_types import SidebarEntrySpec


def test_manifest_accepts_cover_capability():
    manifest = PluginManifest.from_dict(
        {
            "id": "qqmusic",
            "name": "QQ Music",
            "version": "1.0.0",
            "api_version": "1",
            "entrypoint": "plugin_main.py",
            "entry_class": "QQMusicPlugin",
            "capabilities": ["sidebar", "settings_tab", "lyrics_source", "cover", "online_music_provider"],
            "min_app_version": "0.1.0",
        }
    )

    assert manifest.id == "qqmusic"
    assert "cover" in manifest.capabilities


def test_manifest_rejects_unknown_capability():
    with pytest.raises(PluginManifestError):
        PluginManifest.from_dict(
            {
                "id": "broken",
                "name": "Broken Plugin",
                "version": "1.0.0",
                "api_version": "1",
                "entrypoint": "plugin_main.py",
                "entry_class": "BrokenPlugin",
                "capabilities": ["sidebar", "banana"],
                "min_app_version": "0.1.0",
            }
        )


def test_sidebar_spec_requires_widget_factory():
    spec = SidebarEntrySpec(
        plugin_id="qqmusic",
        entry_id="qqmusic.sidebar",
        title="QQ Music",
        order=80,
        icon_name="GLOBE",
        page_factory=lambda _context, _parent: object(),
    )

    assert spec.entry_id == "qqmusic.sidebar"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_system/test_plugin_manifest.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'harmony_plugin_api'`

- [ ] **Step 3: Write minimal implementation**

```python
# harmony_plugin_api/manifest.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Capability = Literal[
    "sidebar",
    "settings_tab",
    "lyrics_source",
    "cover",
    "online_music_provider",
]

_ALLOWED_CAPABILITIES = {"sidebar", "settings_tab", "lyrics_source", "cover", "online_music_provider"}


class PluginManifestError(ValueError):
    pass


@dataclass(frozen=True)
class PluginManifest:
    id: str
    name: str
    version: str
    api_version: str
    entrypoint: str
    entry_class: str
    capabilities: tuple[str, ...]
    min_app_version: str
    max_app_version: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "PluginManifest":
        required = ("id", "name", "version", "api_version", "entrypoint", "entry_class", "capabilities", "min_app_version")
        missing = [key for key in required if key not in data]
        if missing:
            raise PluginManifestError(f"Missing manifest keys: {', '.join(missing)}")
        capabilities = tuple(str(item) for item in data["capabilities"])
        unknown = sorted(set(capabilities) - _ALLOWED_CAPABILITIES)
        if unknown:
            raise PluginManifestError(f"Unknown capabilities: {', '.join(unknown)}")
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            version=str(data["version"]),
            api_version=str(data["api_version"]),
            entrypoint=str(data["entrypoint"]),
            entry_class=str(data["entry_class"]),
            capabilities=capabilities,
            min_app_version=str(data["min_app_version"]),
            max_app_version=str(data["max_app_version"]) if data.get("max_app_version") else None,
        )
```

```python
# harmony_plugin_api/plugin.py
from __future__ import annotations

from typing import Protocol

from .context import PluginContext


class HarmonyPlugin(Protocol):
    plugin_id: str

    def register(self, context: PluginContext) -> None:
        ...

    def unregister(self, context: PluginContext) -> None:
        ...
```

```python
# harmony_plugin_api/context.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .manifest import PluginManifest


class PluginSettingsBridge(Protocol):
    def get(self, key: str, default: Any = None) -> Any:
        ...

    def set(self, key: str, value: Any) -> None:
        ...


class PluginStorageBridge(Protocol):
    @property
    def data_dir(self) -> Path:
        ...

    @property
    def cache_dir(self) -> Path:
        ...

    @property
    def temp_dir(self) -> Path:
        ...


class PluginUiBridge(Protocol):
    def register_sidebar_entry(self, spec: Any) -> None:
        ...

    def register_settings_tab(self, spec: Any) -> None:
        ...


class PluginServiceBridge(Protocol):
    def register_lyrics_source(self, source: Any) -> None:
        ...

    def register_cover_source(self, source: Any) -> None:
        ...

    def register_artist_cover_source(self, source: Any) -> None:
        ...

    def register_online_music_provider(self, provider: Any) -> None:
        ...

    @property
    def media(self) -> Any:
        ...


@dataclass(frozen=True)
class PluginContext:
    plugin_id: str
    manifest: PluginManifest
    logger: Any
    http: Any
    events: Any
    storage: PluginStorageBridge
    settings: PluginSettingsBridge
    ui: PluginUiBridge
    services: PluginServiceBridge
```

```python
# harmony_plugin_api/registry_types.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class SidebarEntrySpec:
    plugin_id: str
    entry_id: str
    title: str
    order: int
    icon_name: str | None
    page_factory: Callable[[Any, Any], Any]


@dataclass(frozen=True)
class SettingsTabSpec:
    plugin_id: str
    tab_id: str
    title: str
    order: int
    widget_factory: Callable[[Any, Any], Any]
```

```python
# harmony_plugin_api/lyrics.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass(frozen=True)
class PluginLyricsResult:
    song_id: str
    title: str
    artist: str
    album: str = ""
    duration: float | None = None
    source: str = ""
    cover_url: str | None = None
    lyrics: str | None = None
    accesskey: str | None = None
    supports_yrc: bool = False


class PluginLyricsSource(Protocol):
    source_id: str
    display_name: str

    def search(self, title: str, artist: str, limit: int = 10) -> list[PluginLyricsResult]:
        ...

    def get_lyrics(self, result: PluginLyricsResult) -> Optional[str]:
        ...
```

```python
# harmony_plugin_api/cover.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PluginCoverResult:
    item_id: str
    title: str
    artist: str
    album: str = ""
    duration: float | None = None
    source: str = ""
    cover_url: str | None = None
    extra_id: str | None = None


@dataclass(frozen=True)
class PluginArtistCoverResult:
    artist_id: str
    name: str
    source: str = ""
    cover_url: str | None = None
    album_count: int | None = None


class PluginCoverSource(Protocol):
    source_id: str
    display_name: str

    def search(self, title: str, artist: str, album: str = "", duration: float | None = None) -> list[PluginCoverResult]:
        ...


class PluginArtistCoverSource(Protocol):
    source_id: str
    display_name: str

    def search(self, artist_name: str, limit: int = 10) -> list[PluginArtistCoverResult]:
        ...
```

```python
# harmony_plugin_api/online.py and harmony_plugin_api/media.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class PluginTrack:
    track_id: str
    title: str
    artist: str
    album: str = ""
    duration: int | None = None
    artwork_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PluginPlaybackRequest:
    provider_id: str
    track_id: str
    title: str
    quality: str
    metadata: dict[str, Any]


class PluginOnlineProvider(Protocol):
    provider_id: str
    display_name: str

    def create_page(self, context: Any, parent: Any = None) -> Any:
        ...

    def get_playback_url_info(self, track_id: str, quality: str) -> dict[str, Any] | None:
        ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_system/test_plugin_manifest.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add harmony_plugin_api/__init__.py harmony_plugin_api/manifest.py harmony_plugin_api/plugin.py harmony_plugin_api/context.py harmony_plugin_api/registry_types.py harmony_plugin_api/lyrics.py harmony_plugin_api/cover.py harmony_plugin_api/online.py harmony_plugin_api/media.py tests/test_system/test_plugin_manifest.py
git commit -m "新增插件SDK"
```

### Task 2: Build the Plugin Runtime, State Store, and Installer

**Files:**
- Create: `system/plugins/__init__.py`
- Create: `system/plugins/errors.py`
- Create: `system/plugins/registry.py`
- Create: `system/plugins/state_store.py`
- Create: `system/plugins/loader.py`
- Create: `system/plugins/installer.py`
- Create: `system/plugins/manager.py`
- Test: `tests/test_system/test_plugin_registry.py`
- Test: `tests/test_system/test_plugin_manager.py`
- Test: `tests/test_system/test_plugin_installer.py`

- [ ] **Step 1: Write the failing test**

```python
import json
from pathlib import Path

import pytest

from harmony_plugin_api.registry_types import SidebarEntrySpec
from system.plugins.errors import PluginInstallError
from system.plugins.installer import audit_plugin_imports
from system.plugins.registry import PluginRegistry
from system.plugins.state_store import PluginStateStore


def test_registry_unregister_plugin_removes_owned_entries():
    registry = PluginRegistry()
    spec = SidebarEntrySpec(
        plugin_id="qqmusic",
        entry_id="qqmusic.sidebar",
        title="QQ Music",
        order=80,
        icon_name="GLOBE",
        page_factory=lambda _context, _parent: object(),
    )

    registry.register_sidebar_entry("qqmusic", spec)
    registry.unregister_plugin("qqmusic")

    assert registry.sidebar_entries() == []


def test_state_store_persists_enabled_flag(tmp_path: Path):
    store = PluginStateStore(tmp_path / "state.json")
    store.set_enabled("qqmusic", True, source="builtin", version="1.0.0")

    payload = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert payload["qqmusic"]["enabled"] is True


def test_import_audit_rejects_host_internal_import(tmp_path: Path):
    plugin_root = tmp_path / "plugin"
    plugin_root.mkdir()
    (plugin_root / "plugin_main.py").write_text("from services.lyrics.qqmusic_lyrics import QQMusicClient\n", encoding="utf-8")

    with pytest.raises(PluginInstallError):
        audit_plugin_imports(plugin_root)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_system/test_plugin_registry.py tests/test_system/test_plugin_manager.py tests/test_system/test_plugin_installer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'system.plugins'`

- [ ] **Step 3: Write minimal implementation**

```python
# system/plugins/errors.py
class PluginError(Exception):
    pass


class PluginInstallError(PluginError):
    pass


class PluginLoadError(PluginError):
    pass
```

```python
# system/plugins/registry.py
from __future__ import annotations

from collections import defaultdict


class PluginRegistry:
    def __init__(self) -> None:
        self._sidebar_entries: list = []
        self._settings_tabs: list = []
        self._lyrics_sources: list = []
        self._cover_sources: list = []
        self._artist_cover_sources: list = []
        self._online_providers: list = []
        self._owned: dict[str, list[tuple[str, object]]] = defaultdict(list)

    def register_sidebar_entry(self, plugin_id: str, spec: object) -> None:
        self._sidebar_entries.append(spec)
        self._owned[plugin_id].append(("sidebar", spec))

    def register_settings_tab(self, plugin_id: str, spec: object) -> None:
        self._settings_tabs.append(spec)
        self._owned[plugin_id].append(("settings_tab", spec))

    def register_lyrics_source(self, plugin_id: str, source: object) -> None:
        self._lyrics_sources.append(source)
        self._owned[plugin_id].append(("lyrics_source", source))

    def register_cover_source(self, plugin_id: str, source: object) -> None:
        self._cover_sources.append(source)
        self._owned[plugin_id].append(("cover_source", source))

    def register_artist_cover_source(self, plugin_id: str, source: object) -> None:
        self._artist_cover_sources.append(source)
        self._owned[plugin_id].append(("artist_cover_source", source))

    def register_online_provider(self, plugin_id: str, provider: object) -> None:
        self._online_providers.append(provider)
        self._owned[plugin_id].append(("online_provider", provider))

    def unregister_plugin(self, plugin_id: str) -> None:
        owned_ids = {id(value) for _kind, value in self._owned.pop(plugin_id, [])}
        self._sidebar_entries = [item for item in self._sidebar_entries if id(item) not in owned_ids]
        self._settings_tabs = [item for item in self._settings_tabs if id(item) not in owned_ids]
        self._lyrics_sources = [item for item in self._lyrics_sources if id(item) not in owned_ids]
        self._cover_sources = [item for item in self._cover_sources if id(item) not in owned_ids]
        self._artist_cover_sources = [item for item in self._artist_cover_sources if id(item) not in owned_ids]
        self._online_providers = [item for item in self._online_providers if id(item) not in owned_ids]

    def sidebar_entries(self) -> list:
        return sorted(self._sidebar_entries, key=lambda item: item.order)

    def settings_tabs(self) -> list:
        return sorted(self._settings_tabs, key=lambda item: item.order)

    def lyrics_sources(self) -> list:
        return list(self._lyrics_sources)

    def cover_sources(self) -> list:
        return list(self._cover_sources)

    def artist_cover_sources(self) -> list:
        return list(self._artist_cover_sources)

    def online_providers(self) -> list:
        return list(self._online_providers)
```

```python
# system/plugins/state_store.py
from __future__ import annotations

import json
from pathlib import Path


class PluginStateStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> dict:
        if not self._path.exists():
            return {}
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _write(self, payload: dict) -> None:
        self._path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def set_enabled(self, plugin_id: str, enabled: bool, source: str, version: str, load_error: str | None = None) -> None:
        payload = self._read()
        payload[plugin_id] = {
            "enabled": enabled,
            "source": source,
            "version": version,
            "load_error": load_error,
        }
        self._write(payload)

    def get(self, plugin_id: str) -> dict | None:
        return self._read().get(plugin_id)
```

```python
# system/plugins/loader.py
from __future__ import annotations

import importlib.util
from pathlib import Path

from harmony_plugin_api.manifest import PluginManifest
from .errors import PluginLoadError


class PluginLoader:
    def load_plugin(self, plugin_root: Path):
        manifest = PluginManifest.from_dict(__import__("json").loads((plugin_root / "plugin.json").read_text(encoding="utf-8")))
        module_path = plugin_root / manifest.entrypoint
        spec = importlib.util.spec_from_file_location(f"plugin_{manifest.id}", module_path)
        if spec is None or spec.loader is None:
            raise PluginLoadError(f"Cannot load entrypoint: {module_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        plugin_class = getattr(module, manifest.entry_class)
        return manifest, plugin_class()
```

```python
# system/plugins/installer.py
from __future__ import annotations

import ast
import shutil
import zipfile
from pathlib import Path

from harmony_plugin_api.manifest import PluginManifest
from .errors import PluginInstallError

_FORBIDDEN_ROOT_IMPORTS = {"app", "domain", "services", "repositories", "infrastructure", "system", "ui"}


def audit_plugin_imports(plugin_root: Path) -> None:
    for py_file in plugin_root.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0]]
            else:
                continue
            if any(name in _FORBIDDEN_ROOT_IMPORTS for name in names):
                raise PluginInstallError(f"Forbidden host import in {py_file}")


class PluginInstaller:
    def __init__(self, external_root: Path, temp_root: Path) -> None:
        self._external_root = external_root
        self._temp_root = temp_root

    def install_zip(self, zip_path: Path) -> Path:
        extract_root = self._temp_root / zip_path.stem
        if extract_root.exists():
            shutil.rmtree(extract_root)
        extract_root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(extract_root)
        audit_plugin_imports(extract_root)
        manifest = PluginManifest.from_dict(__import__("json").loads((extract_root / "plugin.json").read_text(encoding="utf-8")))
        final_root = self._external_root / manifest.id
        if final_root.exists():
            shutil.rmtree(final_root)
        shutil.copytree(extract_root, final_root)
        return final_root
```

```python
# system/plugins/manager.py
from __future__ import annotations

from pathlib import Path

from .loader import PluginLoader
from .registry import PluginRegistry


class PluginManager:
    def __init__(self, builtin_root: Path, external_root: Path, state_store, context_factory) -> None:
        self._builtin_root = builtin_root
        self._external_root = external_root
        self._state_store = state_store
        self._context_factory = context_factory
        self._loader = PluginLoader()
        self.registry = PluginRegistry()
        self._loaded_plugins: dict[str, tuple[object, object]] = {}

    def discover_roots(self) -> list[tuple[str, Path]]:
        roots = []
        if self._builtin_root.exists():
            roots.extend(("builtin", path) for path in self._builtin_root.iterdir() if path.is_dir())
        if self._external_root.exists():
            roots.extend(("external", path) for path in self._external_root.iterdir() if path.is_dir())
        return roots

    def load_enabled_plugins(self) -> None:
        for source, plugin_root in self.discover_roots():
            manifest, plugin = self._loader.load_plugin(plugin_root)
            state = self._state_store.get(manifest.id)
            if source == "external" and state and state.get("enabled") is False:
                continue
            context = self._context_factory.build(manifest)
            plugin.register(context)
            self._loaded_plugins[manifest.id] = (manifest, plugin)
            self._state_store.set_enabled(manifest.id, True if state is None else bool(state.get("enabled", True)), source=source, version=manifest.version)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_system/test_plugin_registry.py tests/test_system/test_plugin_manager.py tests/test_system/test_plugin_installer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add system/plugins/__init__.py system/plugins/errors.py system/plugins/registry.py system/plugins/state_store.py system/plugins/loader.py system/plugins/installer.py system/plugins/manager.py tests/test_system/test_plugin_registry.py tests/test_system/test_plugin_manager.py tests/test_system/test_plugin_installer.py
git commit -m "实现插件运行时"
```

### Task 3: Wire Bootstrap and Add Host Plugin Bridges

**Files:**
- Create: `system/plugins/host_services.py`
- Create: `system/plugins/media_bridge.py`
- Modify: `app/bootstrap.py:344-414`
- Modify: `services/online/download_service.py:42-177`
- Test: `tests/test_app/test_plugin_bootstrap.py`
- Test: `tests/test_system/test_plugin_online_bridge.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path
from unittest.mock import Mock

from app.bootstrap import Bootstrap
from system.plugins.media_bridge import PluginMediaBridge


def test_bootstrap_exposes_plugin_manager(monkeypatch, tmp_path: Path):
    bootstrap = Bootstrap(":memory:")
    bootstrap._config = Mock()
    bootstrap._event_bus = Mock()
    bootstrap._http_client = Mock()

    manager = bootstrap.plugin_manager

    assert manager is bootstrap.plugin_manager


def test_media_bridge_passes_explicit_quality_to_download_service():
    download_service = Mock()
    playback_service = Mock()
    library_service = Mock()
    bridge = PluginMediaBridge(download_service, playback_service, library_service)

    request = type(
        "Request",
        (),
        {
            "provider_id": "qqmusic",
            "track_id": "mid-1",
            "title": "Song 1",
            "quality": "flac",
            "metadata": {"title": "Song 1", "artist": "Singer 1"},
        },
    )()

    bridge.cache_remote_track(request)

    download_service.download.assert_called_once_with(
        "mid-1",
        song_title="Song 1",
        quality="flac",
        progress_callback=None,
        force=False,
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_app/test_plugin_bootstrap.py tests/test_system/test_plugin_online_bridge.py -v`
Expected: FAIL with `AttributeError: 'Bootstrap' object has no attribute 'plugin_manager'` and `ModuleNotFoundError: No module named 'system.plugins.media_bridge'`

- [ ] **Step 3: Write minimal implementation**

```python
# system/plugins/media_bridge.py
from __future__ import annotations


class PluginMediaBridge:
    def __init__(self, download_service, playback_service, library_service) -> None:
        self._download_service = download_service
        self._playback_service = playback_service
        self._library_service = library_service

    def cache_remote_track(self, request, progress_callback=None, force: bool = False):
        return self._download_service.download(
            request.track_id,
            song_title=request.title,
            quality=request.quality,
            progress_callback=progress_callback,
            force=force,
        )

    def add_online_track(self, request):
        metadata = request.metadata
        return self._library_service.add_online_track(
            title=metadata.get("title", request.title),
            artist=metadata.get("artist", ""),
            album=metadata.get("album", ""),
            song_mid=request.track_id,
            source=request.provider_id,
        )
```

```python
# system/plugins/host_services.py
from __future__ import annotations

from pathlib import Path

from harmony_plugin_api.context import PluginContext


class PluginSettingsBridgeImpl:
    def __init__(self, plugin_id: str, config) -> None:
        self._plugin_id = plugin_id
        self._config = config

    def _key(self, key: str) -> str:
        return f"plugins.{self._plugin_id}.{key}"

    def get(self, key: str, default=None):
        return self._config.get(self._key(key), default)

    def set(self, key: str, value) -> None:
        self._config.set(self._key(key), value)


class PluginStorageBridgeImpl:
    def __init__(self, root: Path, plugin_id: str) -> None:
        self.data_dir = root / plugin_id / "data"
        self.cache_dir = root / plugin_id / "cache"
        self.temp_dir = root / plugin_id / "tmp"
        for path in (self.data_dir, self.cache_dir, self.temp_dir):
            path.mkdir(parents=True, exist_ok=True)


class PluginUiBridgeImpl:
    def __init__(self, plugin_id: str, registry) -> None:
        self._plugin_id = plugin_id
        self._registry = registry

    def register_sidebar_entry(self, spec) -> None:
        self._registry.register_sidebar_entry(self._plugin_id, spec)

    def register_settings_tab(self, spec) -> None:
        self._registry.register_settings_tab(self._plugin_id, spec)


class PluginServiceBridgeImpl:
    def __init__(self, plugin_id: str, registry, media_bridge) -> None:
        self._plugin_id = plugin_id
        self._registry = registry
        self._media = media_bridge

    @property
    def media(self):
        return self._media

    def register_lyrics_source(self, source) -> None:
        self._registry.register_lyrics_source(self._plugin_id, source)

    def register_cover_source(self, source) -> None:
        self._registry.register_cover_source(self._plugin_id, source)

    def register_artist_cover_source(self, source) -> None:
        self._registry.register_artist_cover_source(self._plugin_id, source)

    def register_online_music_provider(self, provider) -> None:
        self._registry.register_online_provider(self._plugin_id, provider)
```

```python
# app/bootstrap.py
from pathlib import Path

from system.plugins.host_services import (
    PluginServiceBridgeImpl,
    PluginSettingsBridgeImpl,
    PluginStorageBridgeImpl,
    PluginUiBridgeImpl,
)
from system.plugins.manager import PluginManager
from system.plugins.media_bridge import PluginMediaBridge
from system.plugins.state_store import PluginStateStore


def _build_plugin_context_factory(self):
    bootstrap = self

    class _ContextFactory:
        def build(self, manifest):
            media_bridge = PluginMediaBridge(
                bootstrap.online_download_service,
                bootstrap.playback_service,
                bootstrap.library_service,
            )
            return PluginContext(
                plugin_id=manifest.id,
                manifest=manifest,
                logger=logging.getLogger(f"plugin.{manifest.id}"),
                http=bootstrap.http_client,
                events=bootstrap.event_bus,
                storage=PluginStorageBridgeImpl(Path("data/plugins/storage"), manifest.id),
                settings=PluginSettingsBridgeImpl(manifest.id, bootstrap.config),
                ui=PluginUiBridgeImpl(manifest.id, bootstrap.plugin_manager.registry),
                services=PluginServiceBridgeImpl(manifest.id, bootstrap.plugin_manager.registry, media_bridge),
            )

    return _ContextFactory()


@property
def plugin_manager(self):
    if self._plugin_manager is None:
        builtin_root = Path("plugins/builtin")
        external_root = Path("data/plugins/external")
        state_store = PluginStateStore(Path("data/plugins/state.json"))
        self._plugin_manager = PluginManager(
            builtin_root=builtin_root,
            external_root=external_root,
            state_store=state_store,
            context_factory=self._build_plugin_context_factory(),
        )
    return self._plugin_manager
```

```python
# services/online/download_service.py
if quality is None:
    quality = "320"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_app/test_plugin_bootstrap.py tests/test_system/test_plugin_online_bridge.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add system/plugins/host_services.py system/plugins/media_bridge.py app/bootstrap.py services/online/download_service.py tests/test_app/test_plugin_bootstrap.py tests/test_system/test_plugin_online_bridge.py
git commit -m "接入插件宿主桥接"
```

### Task 4: Add the Host-Owned `插件` Tab to the Settings Dialog

**Files:**
- Create: `ui/dialogs/plugin_management_tab.py`
- Modify: `ui/dialogs/settings_dialog.py:214-858`
- Modify: `translations/en.json`
- Modify: `translations/zh.json`
- Test: `tests/test_ui/test_plugin_settings_tab.py`

- [ ] **Step 1: Write the failing test**

```python
from unittest.mock import Mock

from PySide6.QtWidgets import QApplication, QTabWidget

from ui.dialogs.plugin_management_tab import PluginManagementTab
from ui.dialogs.settings_dialog import GeneralSettingsDialog


def test_plugin_management_tab_shows_plugin_rows(qtbot):
    manager = Mock()
    manager.list_plugins.return_value = [
        {"id": "lrclib", "name": "LRCLIB", "version": "1.0.0", "source": "builtin", "enabled": True, "load_error": None},
        {"id": "qqmusic", "name": "QQ Music", "version": "1.0.0", "source": "external", "enabled": False, "load_error": "load failed"},
    ]

    widget = PluginManagementTab(manager)
    qtbot.addWidget(widget)

    assert widget._table.rowCount() == 2


def test_settings_dialog_includes_plugins_tab(monkeypatch, qtbot):
    config = Mock()
    config.get.return_value = "dark"
    config.get_ai_enabled.return_value = False
    config.get_ai_base_url.return_value = ""
    config.get_ai_api_key.return_value = ""
    config.get_ai_model.return_value = ""
    config.get_acoustid_enabled.return_value = False
    config.get_acoustid_api_key.return_value = ""
    config.get_online_music_download_dir.return_value = "data/online_cache"
    config.get_cache_cleanup_strategy.return_value = "manual"
    config.get_cache_cleanup_auto_enabled.return_value = False
    config.get_cache_cleanup_time_days.return_value = 30
    config.get_cache_cleanup_size_mb.return_value = 1000
    config.get_cache_cleanup_count.return_value = 100
    config.get_cache_cleanup_interval_hours.return_value = 1
    config.get_audio_engine.return_value = "mpv"

    dialog = GeneralSettingsDialog(config)
    qtbot.addWidget(dialog)
    tab_widget = dialog.findChild(QTabWidget)

    tab_labels = [tab_widget.tabText(index) for index in range(tab_widget.count())]
    assert "Plugins" in tab_labels or "插件" in tab_labels
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ui/test_plugin_settings_tab.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ui.dialogs.plugin_management_tab'`

- [ ] **Step 3: Write minimal implementation**

```python
# ui/dialogs/plugin_management_tab.py
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QFileDialog,
)

from system.i18n import t


class PluginManagementTab(QWidget):
    def __init__(self, plugin_manager, parent=None):
        super().__init__(parent)
        self._plugin_manager = plugin_manager
        self._table = QTableWidget(0, 5, self)
        self._url_input = QLineEdit(self)
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(self._table)

        controls = QHBoxLayout()
        install_zip_btn = QPushButton(t("plugins_install_zip"))
        install_zip_btn.clicked.connect(self._install_zip)
        install_url_btn = QPushButton(t("plugins_install_url"))
        install_url_btn.clicked.connect(self._install_url)
        controls.addWidget(self._url_input)
        controls.addWidget(install_zip_btn)
        controls.addWidget(install_url_btn)
        layout.addLayout(controls)

    def refresh(self) -> None:
        rows = self._plugin_manager.list_plugins()
        self._table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            self._table.setItem(row_index, 0, QTableWidgetItem(row["name"]))
            self._table.setItem(row_index, 1, QTableWidgetItem(row["version"]))
            self._table.setItem(row_index, 2, QTableWidgetItem(row["source"]))
            self._table.setItem(row_index, 3, QTableWidgetItem("enabled" if row["enabled"] else "disabled"))
            self._table.setItem(row_index, 4, QTableWidgetItem(row["load_error"] or ""))

    def _install_zip(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, t("plugins_install_zip"), "", "Zip Files (*.zip)")
        if path:
            self._plugin_manager.install_zip(path)
            self.refresh()

    def _install_url(self) -> None:
        url = self._url_input.text().strip()
        if url:
            self._plugin_manager.install_from_url(url)
            self.refresh()
```

```python
# ui/dialogs/settings_dialog.py
from ui.dialogs.plugin_management_tab import PluginManagementTab

tab_widget.addTab(playback_tab, t("playback_tab"))
tab_widget.addTab(appearance_tab, t("theme_tab"))
tab_widget.addTab(cache_tab, t("cache_tab"))
tab_widget.addTab(covers_tab, t("covers_tab"))
tab_widget.addTab(repair_tab, t("repair_tab"))
tab_widget.addTab(ai_tab, t("ai_tab"))
tab_widget.addTab(acoustid_tab, t("acoustid_tab"))

bootstrap = Bootstrap.instance()
plugin_tab = PluginManagementTab(bootstrap.plugin_manager, self)
tab_widget.addTab(plugin_tab, t("plugins_tab"))
for spec in bootstrap.plugin_manager.registry.settings_tabs():
    tab_widget.addTab(spec.widget_factory(bootstrap.plugin_manager, self), spec.title)
```

```json
// translations/en.json
"plugins_tab": "Plugins",
"plugins_install_zip": "Install Zip",
"plugins_install_url": "Install URL",
"plugins_enable": "Enable",
"plugins_disable": "Disable",
"plugins_uninstall": "Uninstall",
"plugins_source_builtin": "Built-in",
"plugins_source_external": "External",
"plugins_load_error": "Load Error"
```

```json
// translations/zh.json
"plugins_tab": "插件",
"plugins_install_zip": "安装 Zip",
"plugins_install_url": "在线安装",
"plugins_enable": "启用",
"plugins_disable": "禁用",
"plugins_uninstall": "卸载",
"plugins_source_builtin": "内置",
"plugins_source_external": "外部",
"plugins_load_error": "加载错误"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ui/test_plugin_settings_tab.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui/dialogs/plugin_management_tab.py ui/dialogs/settings_dialog.py translations/en.json translations/zh.json tests/test_ui/test_plugin_settings_tab.py
git commit -m "新增插件管理页"
```

### Task 5: Make Sidebar and MainWindow Consume Plugin Pages Dynamically

**Files:**
- Modify: `ui/windows/components/sidebar.py:17-176`
- Modify: `ui/windows/main_window.py:394-474,523-528`
- Test: `tests/test_ui/test_plugin_sidebar_integration.py`

- [ ] **Step 1: Write the failing test**

```python
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QLabel

from ui.windows.components.sidebar import Sidebar
from ui.windows.main_window import MainWindow


def test_sidebar_can_add_plugin_entry(qtbot):
    sidebar = Sidebar()
    qtbot.addWidget(sidebar)

    sidebar.add_plugin_entry(page_index=200, title="QQ Music", icon_name="GLOBE")

    assert any(index == 200 for index, _button in sidebar._nav_buttons)


def test_main_window_mounts_plugin_pages(qtbot):
    bootstrap = Mock()
    bootstrap.db = Mock()
    bootstrap.config = Mock()
    bootstrap.playback_service = Mock()
    bootstrap.library_service = Mock()
    bootstrap.favorites_service = Mock()
    bootstrap.play_history_service = Mock()
    bootstrap.cloud_account_service = Mock()
    bootstrap.cloud_file_service = Mock()
    bootstrap.cover_service = Mock()
    bootstrap.playlist_service = Mock()
    bootstrap.plugin_manager.registry.sidebar_entries.return_value = [
        type(
            "Spec",
            (),
            {
                "plugin_id": "qqmusic",
                "entry_id": "qqmusic.sidebar",
                "title": "QQ Music",
                "order": 80,
                "icon_name": "GLOBE",
                "page_factory": staticmethod(lambda _context, _parent: QLabel("QQ Music View")),
            },
        )()
    ]

    with patch("ui.windows.main_window.Bootstrap.instance", return_value=bootstrap), \
            patch.object(MainWindow, "_setup_connections"), \
            patch.object(MainWindow, "_setup_system_tray"), \
            patch.object(MainWindow, "_setup_hotkeys"), \
            patch.object(MainWindow, "_restore_settings"):
        window = MainWindow()
        qtbot.addWidget(window)

    assert "qqmusic" in window._plugin_page_keys.values()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ui/test_plugin_sidebar_integration.py -v`
Expected: FAIL with `AttributeError: 'Sidebar' object has no attribute 'add_plugin_entry'`

- [ ] **Step 3: Write minimal implementation**

```python
# ui/windows/components/sidebar.py
from ui.icons import IconName, IconButton


def _coerce_icon_name(icon_name: str | None) -> IconName:
    if not icon_name:
        return IconName.GLOBE
    return getattr(IconName, icon_name, IconName.GLOBE)


class Sidebar(QWidget):
    ...
    def add_plugin_entry(self, page_index: int, title: str, icon_name: str | None = None) -> None:
        btn = IconButton(_coerce_icon_name(icon_name), title, size=18)
        btn.setCheckable(True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda checked, idx=page_index: self._on_nav_clicked(idx))
        self.layout().insertWidget(len(self._nav_buttons) + 2, btn)
        self._nav_buttons.append((page_index, btn))
```

```python
# ui/windows/main_window.py
class MainWindow(QMainWindow):
    ...
    def _mount_plugin_pages(self) -> None:
        self._plugin_page_keys = {}
        bootstrap = Bootstrap.instance()
        for spec in bootstrap.plugin_manager.registry.sidebar_entries():
            page_index = self._stacked_widget.count()
            widget = spec.page_factory(bootstrap.plugin_manager, self)
            self._stacked_widget.addWidget(widget)
            self._sidebar.add_plugin_entry(page_index=page_index, title=spec.title, icon_name=spec.icon_name)
            self._plugin_page_keys[page_index] = spec.plugin_id

    def _setup_ui(self):
        ...
        self._sidebar = self._create_sidebar()
        ...
        self._stacked_widget.addWidget(self._genres_view)  # 9
        self._stacked_widget.addWidget(self._genre_view)  # 10
        self._mount_plugin_pages()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ui/test_plugin_sidebar_integration.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui/windows/components/sidebar.py ui/windows/main_window.py tests/test_ui/test_plugin_sidebar_integration.py
git commit -m "支持插件侧边栏页面"
```

### Task 6: Move LRCLIB to a Built-In Plugin and Make Lyrics/Cover Registration Dynamic

**Files:**
- Create: `plugins/builtin/lrclib/plugin.json`
- Create: `plugins/builtin/lrclib/plugin_main.py`
- Create: `plugins/builtin/lrclib/lib/lrclib_source.py`
- Modify: `services/lyrics/lyrics_service.py:57-72`
- Modify: `services/metadata/cover_service.py:46-74`
- Modify: `services/sources/lyrics_sources.py:271-380`
- Modify: `services/sources/__init__.py:17-46`
- Test: `tests/test_services/test_plugin_lyrics_registry.py`
- Test: `tests/test_services/test_plugin_cover_registry.py`
- Test: `tests/test_plugins/test_lrclib_plugin.py`

- [ ] **Step 1: Write the failing test**

```python
from types import SimpleNamespace

from harmony_plugin_api.cover import PluginArtistCoverResult, PluginCoverResult
from harmony_plugin_api.lyrics import PluginLyricsResult
from services.lyrics.lyrics_service import LyricsService
from services.metadata.cover_service import CoverService


def test_lyrics_service_merges_plugin_sources(monkeypatch):
    fake_plugin_source = SimpleNamespace(
        source_id="lrclib",
        display_name="LRCLIB",
        search=lambda *_args, **_kwargs: [
            PluginLyricsResult(song_id="song-1", title="Song 1", artist="Singer 1", source="lrclib", lyrics="[00:01.00]line"),
        ],
        get_lyrics=lambda result: result.lyrics,
    )
    fake_manager = SimpleNamespace(registry=SimpleNamespace(lyrics_sources=lambda: [fake_plugin_source]))
    monkeypatch.setattr("services.lyrics.lyrics_service.Bootstrap.instance", lambda: SimpleNamespace(plugin_manager=fake_manager))

    results = LyricsService.search_songs("Song 1", "Singer 1")

    assert any(item["source"] == "lrclib" for item in results)


def test_cover_service_merges_plugin_cover_sources(monkeypatch):
    fake_cover = SimpleNamespace(
        source_id="qqmusic",
        display_name="QQ Music",
        search=lambda *_args, **_kwargs: [PluginCoverResult(item_id="mid-1", title="Song 1", artist="Singer 1", source="qqmusic", cover_url="https://example.com/cover.jpg")],
    )
    fake_artist_cover = SimpleNamespace(
        source_id="qqmusic-artist",
        display_name="QQ Music Artist",
        search=lambda *_args, **_kwargs: [PluginArtistCoverResult(artist_id="artist-1", name="Singer 1", source="qqmusic", cover_url="https://example.com/artist.jpg")],
    )
    fake_registry = SimpleNamespace(cover_sources=lambda: [fake_cover], artist_cover_sources=lambda: [fake_artist_cover])
    fake_manager = SimpleNamespace(registry=fake_registry)
    monkeypatch.setattr("services.metadata.cover_service.Bootstrap.instance", lambda: SimpleNamespace(plugin_manager=fake_manager))
    service = CoverService(http_client=SimpleNamespace(), sources=None)

    assert service._get_sources()[-1] is fake_cover
    assert service._get_artist_sources()[-1] is fake_artist_cover
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_services/test_plugin_lyrics_registry.py tests/test_services/test_plugin_cover_registry.py tests/test_plugins/test_lrclib_plugin.py -v`
Expected: FAIL because `LyricsService` and `CoverService` still hardcode host source classes, and `plugins/builtin/lrclib` does not exist

- [ ] **Step 3: Write minimal implementation**

```json
// plugins/builtin/lrclib/plugin.json
{
  "id": "lrclib",
  "name": "LRCLIB",
  "version": "1.0.0",
  "api_version": "1",
  "entrypoint": "plugin_main.py",
  "entry_class": "LRCLIBPlugin",
  "capabilities": ["lyrics_source"],
  "min_app_version": "0.1.0"
}
```

```python
# plugins/builtin/lrclib/lib/lrclib_source.py
from harmony_plugin_api.lyrics import PluginLyricsResult


class LRCLIBPluginSource:
    source_id = "lrclib"
    display_name = "LRCLIB"

    def __init__(self, http_client) -> None:
        self._http_client = http_client

    def search(self, title: str, artist: str, limit: int = 10) -> list[PluginLyricsResult]:
        response = self._http_client.get(
            "https://lrclib.net/api/search",
            params={"track_name": title, "artist_name": artist},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=3,
        )
        payload = response.json() if response.status_code == 200 else []
        return [
            PluginLyricsResult(
                song_id=str(item.get("id", "")),
                title=item.get("trackName", ""),
                artist=item.get("artistName", ""),
                album=item.get("albumName", ""),
                duration=item.get("duration"),
                source="lrclib",
                lyrics=item.get("syncedLyrics") or item.get("plainLyrics"),
            )
            for item in payload[:limit]
            if item.get("syncedLyrics") or item.get("plainLyrics")
        ]

    def get_lyrics(self, result: PluginLyricsResult) -> str | None:
        return result.lyrics
```

```python
# plugins/builtin/lrclib/plugin_main.py
from harmony_plugin_api.plugin import HarmonyPlugin

from .lib.lrclib_source import LRCLIBPluginSource


class LRCLIBPlugin(HarmonyPlugin):
    plugin_id = "lrclib"

    def register(self, context) -> None:
        context.services.register_lyrics_source(LRCLIBPluginSource(context.http))

    def unregister(self, context) -> None:
        return None
```

```python
# services/lyrics/lyrics_service.py
from app.bootstrap import Bootstrap
from services.sources import NetEaseLyricsSource, KugouLyricsSource


@classmethod
def _get_sources(cls):
    http_client = _get_http_client()
    builtin_sources = [
        NetEaseLyricsSource(http_client),
        KugouLyricsSource(http_client),
    ]
    plugin_sources = Bootstrap.instance().plugin_manager.registry.lyrics_sources()
    return builtin_sources + plugin_sources
```

```python
# services/metadata/cover_service.py
from app.bootstrap import Bootstrap
from services.sources import ITunesCoverSource, LastFmCoverSource, NetEaseCoverSource, NetEaseArtistCoverSource, ITunesArtistCoverSource


def _get_sources(self):
    if self._sources is None:
        host_sources = [
            NetEaseCoverSource(self.http_client),
            ITunesCoverSource(self.http_client),
            LastFmCoverSource(self.http_client),
        ]
        plugin_sources = Bootstrap.instance().plugin_manager.registry.cover_sources()
        self._sources = host_sources + plugin_sources
    return [source for source in self._sources if getattr(source, "is_available", lambda: True)()]


def _get_artist_sources(self):
    host_sources = [
        NetEaseArtistCoverSource(self.http_client),
        ITunesArtistCoverSource(self.http_client),
    ]
    plugin_sources = Bootstrap.instance().plugin_manager.registry.artist_cover_sources()
    return host_sources + plugin_sources
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_services/test_plugin_lyrics_registry.py tests/test_services/test_plugin_cover_registry.py tests/test_plugins/test_lrclib_plugin.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add plugins/builtin/lrclib/plugin.json plugins/builtin/lrclib/plugin_main.py plugins/builtin/lrclib/lib/lrclib_source.py services/lyrics/lyrics_service.py services/metadata/cover_service.py services/sources/lyrics_sources.py services/sources/__init__.py tests/test_services/test_plugin_lyrics_registry.py tests/test_services/test_plugin_cover_registry.py tests/test_plugins/test_lrclib_plugin.py
git commit -m "迁移LRCLIB插件"
```

### Task 7: Create the QQ Music Plugin Package and Register Its Capabilities

**Files:**
- Create: `plugins/builtin/qqmusic/plugin.json`
- Create: `plugins/builtin/qqmusic/plugin_main.py`
- Create: `plugins/builtin/qqmusic/lib/settings_tab.py`
- Create: `plugins/builtin/qqmusic/lib/lyrics_source.py`
- Create: `plugins/builtin/qqmusic/lib/cover_source.py`
- Create: `plugins/builtin/qqmusic/lib/artist_cover_source.py`
- Create: `plugins/builtin/qqmusic/lib/provider.py`
- Test: `tests/test_plugins/test_qqmusic_plugin.py`

- [ ] **Step 1: Write the failing test**

```python
from unittest.mock import Mock

from plugins.builtin.qqmusic.plugin_main import QQMusicPlugin


def test_qqmusic_plugin_registers_expected_capabilities():
    context = Mock()
    plugin = QQMusicPlugin()

    plugin.register(context)

    assert context.ui.register_sidebar_entry.call_count == 1
    assert context.ui.register_settings_tab.call_count == 1
    assert context.services.register_lyrics_source.call_count == 1
    assert context.services.register_cover_source.call_count == 1
    assert context.services.register_artist_cover_source.call_count == 1
    assert context.services.register_online_music_provider.call_count == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_plugins/test_qqmusic_plugin.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'plugins.builtin.qqmusic'`

- [ ] **Step 3: Write minimal implementation**

```json
// plugins/builtin/qqmusic/plugin.json
{
  "id": "qqmusic",
  "name": "QQ Music",
  "version": "1.0.0",
  "api_version": "1",
  "entrypoint": "plugin_main.py",
  "entry_class": "QQMusicPlugin",
  "capabilities": ["sidebar", "settings_tab", "lyrics_source", "cover", "online_music_provider"],
  "min_app_version": "0.1.0"
}
```

```python
# plugins/builtin/qqmusic/plugin_main.py
from harmony_plugin_api.plugin import HarmonyPlugin
from harmony_plugin_api.registry_types import SettingsTabSpec, SidebarEntrySpec

from .lib.artist_cover_source import QQMusicArtistCoverPluginSource
from .lib.cover_source import QQMusicCoverPluginSource
from .lib.lyrics_source import QQMusicLyricsPluginSource
from .lib.provider import QQMusicOnlineProvider
from .lib.settings_tab import QQMusicSettingsTab


class QQMusicPlugin(HarmonyPlugin):
    plugin_id = "qqmusic"

    def register(self, context) -> None:
        context.ui.register_sidebar_entry(
            SidebarEntrySpec(
                plugin_id="qqmusic",
                entry_id="qqmusic.sidebar",
                title="QQ 音乐",
                order=80,
                icon_name="GLOBE",
                page_factory=lambda plugin_manager, parent: QQMusicOnlineProvider(context).create_page(context, parent),
            )
        )
        context.ui.register_settings_tab(
            SettingsTabSpec(
                plugin_id="qqmusic",
                tab_id="qqmusic.settings",
                title="QQ 音乐",
                order=80,
                widget_factory=lambda plugin_manager, parent: QQMusicSettingsTab(context, parent),
            )
        )
        context.services.register_lyrics_source(QQMusicLyricsPluginSource(context))
        context.services.register_cover_source(QQMusicCoverPluginSource(context))
        context.services.register_artist_cover_source(QQMusicArtistCoverPluginSource(context))
        context.services.register_online_music_provider(QQMusicOnlineProvider(context))

    def unregister(self, context) -> None:
        return None
```

```python
# plugins/builtin/qqmusic/lib/settings_tab.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QComboBox, QPushButton


class QQMusicSettingsTab(QWidget):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self._context = context
        layout = QVBoxLayout(self)
        self._quality_combo = QComboBox(self)
        for quality in ("320", "flac", "master"):
            self._quality_combo.addItem(quality, quality)
        self._quality_combo.setCurrentText(str(self._context.settings.get("quality", "320")))
        save_btn = QPushButton("Save", self)
        save_btn.clicked.connect(self._save)
        layout.addWidget(self._quality_combo)
        layout.addWidget(save_btn)

    def _save(self):
        self._context.settings.set("quality", self._quality_combo.currentData())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_plugins/test_qqmusic_plugin.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add plugins/builtin/qqmusic/plugin.json plugins/builtin/qqmusic/plugin_main.py plugins/builtin/qqmusic/lib/settings_tab.py plugins/builtin/qqmusic/lib/lyrics_source.py plugins/builtin/qqmusic/lib/cover_source.py plugins/builtin/qqmusic/lib/artist_cover_source.py plugins/builtin/qqmusic/lib/provider.py tests/test_plugins/test_qqmusic_plugin.py
git commit -m "创建QQ音乐插件包"
```

### Task 8: Migrate QQ Music Client, View Logic, and Remove Host Direct Wiring

**Files:**
- Create: `plugins/builtin/qqmusic/lib/client.py`
- Create: `plugins/builtin/qqmusic/lib/login_dialog.py`
- Create: `plugins/builtin/qqmusic/lib/root_view.py`
- Modify: `app/bootstrap.py:344-414`
- Modify: `ui/dialogs/settings_dialog.py:325-399`
- Modify: `ui/windows/main_window.py:394-406`
- Modify: `services/sources/lyrics_sources.py:137-183`
- Modify: `services/sources/cover_sources.py:121-180`
- Modify: `services/sources/artist_cover_sources.py:79-130`
- Modify: `services/sources/__init__.py:9-52`
- Test: `tests/test_ui/test_plugin_settings_tab.py`
- Test: `tests/test_system/test_plugin_import_guard.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

import pytest

from system.plugins.installer import audit_plugin_imports


def test_settings_dialog_omits_qqmusic_tab_without_plugin(monkeypatch, qtbot):
    from PySide6.QtWidgets import QTabWidget
    from ui.dialogs.settings_dialog import GeneralSettingsDialog

    config = type(
        "Config",
        (),
        {
            "get": lambda self, key, default=None: default if key != "ui.theme" else "dark",
            "get_ai_enabled": lambda self: False,
            "get_ai_base_url": lambda self: "",
            "get_ai_api_key": lambda self: "",
            "get_ai_model": lambda self: "",
            "get_acoustid_enabled": lambda self: False,
            "get_acoustid_api_key": lambda self: "",
            "get_online_music_download_dir": lambda self: "data/online_cache",
            "get_cache_cleanup_strategy": lambda self: "manual",
            "get_cache_cleanup_auto_enabled": lambda self: False,
            "get_cache_cleanup_time_days": lambda self: 30,
            "get_cache_cleanup_size_mb": lambda self: 1000,
            "get_cache_cleanup_count": lambda self: 100,
            "get_cache_cleanup_interval_hours": lambda self: 1,
            "get_audio_engine": lambda self: "mpv",
        },
    )()

    monkeypatch.setattr("ui.dialogs.settings_dialog.Bootstrap.instance", lambda: type("BootstrapStub", (), {"plugin_manager": type("Manager", (), {"registry": type("Registry", (), {"settings_tabs": staticmethod(lambda: [])})()})()})())
    dialog = GeneralSettingsDialog(config)
    qtbot.addWidget(dialog)
    tab_widget = dialog.findChild(QTabWidget)

    assert "QQ音乐" not in [tab_widget.tabText(index) for index in range(tab_widget.count())]


def test_plugin_import_audit_allows_sdk_only_imports(tmp_path: Path):
    plugin_root = tmp_path / "qqmusic"
    plugin_root.mkdir()
    (plugin_root / "plugin_main.py").write_text("from harmony_plugin_api.plugin import HarmonyPlugin\n", encoding="utf-8")

    audit_plugin_imports(plugin_root)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ui/test_plugin_settings_tab.py tests/test_system/test_plugin_import_guard.py -v`
Expected: FAIL because `settings_dialog.py` still builds the QQ Music tab directly and host QQ source modules are still present

- [ ] **Step 3: Write minimal implementation**

```python
# plugins/builtin/qqmusic/lib/client.py
from __future__ import annotations

from plugins.builtin.qqmusic.lib.login_dialog import QQMusicLoginDialog


class QQMusicPluginClient:
    def __init__(self, context):
        self._context = context
        self._credential = context.settings.get("credential", None)

    def get_quality(self) -> str:
        return str(self._context.settings.get("quality", "320"))

    def set_credential(self, credential: dict) -> None:
        self._credential = credential
        self._context.settings.set("credential", credential)

    def clear_credential(self) -> None:
        self._credential = None
        self._context.settings.set("credential", None)
```

```python
# plugins/builtin/qqmusic/lib/root_view.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel

from harmony_plugin_api.media import PluginPlaybackRequest


class QQMusicRootView(QWidget):
    def __init__(self, context, provider, parent=None):
        super().__init__(parent)
        self._context = context
        self._provider = provider
        self._status = QLabel("QQ Music", self)
        self._play_btn = QPushButton("Play first track", self)
        self._play_btn.clicked.connect(self._play_demo_track)
        layout = QVBoxLayout(self)
        layout.addWidget(self._status)
        layout.addWidget(self._play_btn)

    def _play_demo_track(self):
        track = self._provider.get_demo_track()
        request = PluginPlaybackRequest(
            provider_id="qqmusic",
            track_id=track.track_id,
            title=track.title,
            quality=self._context.settings.get("quality", "320"),
            metadata={"title": track.title, "artist": track.artist, "album": track.album},
        )
        local_path = self._context.services.media.cache_remote_track(request)
        self._context.services.media.add_online_track(request)
        self._status.setText(local_path or "download failed")
```

```python
# plugins/builtin/qqmusic/lib/provider.py
from harmony_plugin_api.online import PluginTrack

from .client import QQMusicPluginClient
from .root_view import QQMusicRootView


class QQMusicOnlineProvider:
    provider_id = "qqmusic"
    display_name = "QQ 音乐"

    def __init__(self, context):
        self._context = context
        self._client = QQMusicPluginClient(context)

    def create_page(self, context, parent=None):
        return QQMusicRootView(context, self, parent)

    def get_demo_track(self) -> PluginTrack:
        return PluginTrack(track_id="demo-mid", title="Demo Song", artist="Demo Artist", album="Demo Album")

    def get_playback_url_info(self, track_id: str, quality: str):
        return {"url": "https://example.com/demo.mp3", "quality": quality, "extension": ".mp3"}
```

```python
# app/bootstrap.py and ui/windows/main_window.py
@property
def online_download_service(self) -> "OnlineDownloadService":
    if self._online_download_service is None:
        from services.online import OnlineDownloadService
        self._online_download_service = OnlineDownloadService(
            config_manager=self.config,
            qqmusic_service=None,
            online_music_service=None,
        )
    return self._online_download_service
```

```python
# ui/windows/main_window.py
for page in (
    self._library_view,
    self._cloud_drive_view,
    self._playlist_view,
    self._queue_view,
    self._albums_view,
    self._artists_view,
    self._artist_view,
    self._album_view,
    self._genres_view,
    self._genre_view,
):
    self._stacked_widget.addWidget(page)
self._mount_plugin_pages()
```

```python
# ui/dialogs/settings_dialog.py
tab_widget.addTab(playback_tab, t("playback_tab"))
tab_widget.addTab(appearance_tab, t("theme_tab"))
tab_widget.addTab(cache_tab, t("cache_tab"))
tab_widget.addTab(covers_tab, t("covers_tab"))
tab_widget.addTab(repair_tab, t("repair_tab"))
tab_widget.addTab(ai_tab, t("ai_tab"))
tab_widget.addTab(acoustid_tab, t("acoustid_tab"))
tab_widget.addTab(PluginManagementTab(Bootstrap.instance().plugin_manager, self), t("plugins_tab"))
for spec in Bootstrap.instance().plugin_manager.registry.settings_tabs():
    tab_widget.addTab(spec.widget_factory(Bootstrap.instance().plugin_manager, self), spec.title)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ui/test_plugin_settings_tab.py tests/test_system/test_plugin_import_guard.py tests/test_plugins/test_qqmusic_plugin.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add plugins/builtin/qqmusic/lib/client.py plugins/builtin/qqmusic/lib/login_dialog.py plugins/builtin/qqmusic/lib/root_view.py plugins/builtin/qqmusic/lib/provider.py app/bootstrap.py ui/dialogs/settings_dialog.py ui/windows/main_window.py services/sources/lyrics_sources.py services/sources/cover_sources.py services/sources/artist_cover_sources.py services/sources/__init__.py tests/test_ui/test_plugin_settings_tab.py tests/test_system/test_plugin_import_guard.py
git commit -m "迁移QQ音乐宿主接线"
```

### Task 9: Package QQ Music as a Zip Plugin and Remove Host QQ Modules

**Files:**
- Create: `scripts/build_plugin_zip.py`
- Modify: `system/config.py:68-80,693-800`
- Delete: `services/lyrics/qqmusic_lyrics.py`
- Delete: `services/cloud/qqmusic/__init__.py`
- Delete: `services/cloud/qqmusic/client.py`
- Delete: `services/cloud/qqmusic/common.py`
- Delete: `services/cloud/qqmusic/crypto.py`
- Delete: `services/cloud/qqmusic/qr_login.py`
- Delete: `services/cloud/qqmusic/qqmusic_service.py`
- Delete: `services/cloud/qqmusic/tripledes.py`
- Test: `tests/test_system/test_plugin_packaging.py`
- Test: `tests/test_system/test_plugin_installer.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_system/test_plugin_packaging.py tests/test_system/test_plugin_installer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.build_plugin_zip'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/build_plugin_zip.py
from __future__ import annotations

import zipfile
from pathlib import Path


def build_plugin_zip(plugin_root: Path, output_zip: Path) -> Path:
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in plugin_root.rglob("*"):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(plugin_root))
    return output_zip
```

```python
# system/config.py
class ConfigManager:
    ...
    def get_plugin_setting(self, plugin_id: str, key: str, default=None):
        return self.get(f"plugins.{plugin_id}.{key}", default)

    def set_plugin_setting(self, plugin_id: str, key: str, value):
        self.set(f"plugins.{plugin_id}.{key}", value)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_system/test_plugin_packaging.py tests/test_system/test_plugin_installer.py tests/test_plugins/test_qqmusic_plugin.py tests/test_plugins/test_lrclib_plugin.py tests/test_ui/test_plugin_sidebar_integration.py tests/test_ui/test_plugin_settings_tab.py tests/test_services/test_plugin_lyrics_registry.py tests/test_services/test_plugin_cover_registry.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/build_plugin_zip.py system/config.py tests/test_system/test_plugin_packaging.py tests/test_system/test_plugin_installer.py tests/test_plugins/test_qqmusic_plugin.py tests/test_plugins/test_lrclib_plugin.py tests/test_ui/test_plugin_sidebar_integration.py tests/test_ui/test_plugin_settings_tab.py tests/test_services/test_plugin_lyrics_registry.py tests/test_services/test_plugin_cover_registry.py
git rm services/lyrics/qqmusic_lyrics.py services/cloud/qqmusic/__init__.py services/cloud/qqmusic/client.py services/cloud/qqmusic/common.py services/cloud/qqmusic/crypto.py services/cloud/qqmusic/qr_login.py services/cloud/qqmusic/qqmusic_service.py services/cloud/qqmusic/tripledes.py
git commit -m "完成QQ音乐插件化"
```
