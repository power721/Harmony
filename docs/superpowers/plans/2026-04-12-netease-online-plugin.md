# NetEase Online Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new built-in NetEase online music plugin under `plugins/builtin/netease` that matches the QQ Music plugin's baseline online-music capabilities, including anonymous browsing, three login flows, logged-in recommendations, playback, and downloads, without implementing cloud drive features.

**Architecture:** Keep the plugin self-contained under `plugins/builtin/netease` and only use `harmony_plugin_api` plus `PluginContext` bridges. Implement the work in layers: scaffold and plugin registration first, then shared foundations, then anonymous API/client behavior, then auth flows, then provider/media integration, then plugin-owned UI, and finally logged-in recommendation/favorite actions plus full regression checks.

**Tech Stack:** Python 3.11+, PySide6, pytest, Harmony plugin runtime, plugin-scoped settings/storage, host `OnlineDownloadGateway`, built-in NetEase lyrics/cover plugins.

---

## File Map

- `plugins/builtin/netease/plugin.json`
  - Plugin manifest with `sidebar`, `settings_tab`, and `online_music_provider`.
- `plugins/builtin/netease/plugin_main.py`
  - Plugin entry class that registers sidebar, settings tab, and online provider.
- `plugins/builtin/netease/lib/constants.py`
  - Provider id, source ids, default quality, default headers, settings keys.
- `plugins/builtin/netease/lib/errors.py`
  - `NeteaseRequestError`, `NeteaseLoginError`, `NeteaseAuthExpiredError`, `NeteaseRateLimitError`.
- `plugins/builtin/netease/lib/models.py`
  - Plugin-local dataclasses for auth state, tracks, artists, albums, playlists, and chart items.
- `plugins/builtin/netease/lib/i18n.py`
  - Plugin-local translation loader and lookup helpers.
- `plugins/builtin/netease/lib/auth_store.py`
  - Cookie/profile persistence and login-state invalidation using plugin-scoped settings.
- `plugins/builtin/netease/lib/api.py`
  - Raw HTTP calls to NetEase endpoints.
- `plugins/builtin/netease/lib/adapters.py`
  - Payload normalization helpers from NetEase JSON to plugin-local models / dicts.
- `plugins/builtin/netease/lib/client.py`
  - High-level NetEase operations, auth validation, and normalized error behavior.
- `plugins/builtin/netease/lib/provider.py`
  - Host-facing provider implementation and page creation.
- `plugins/builtin/netease/lib/login_dialog.py`
  - Cellphone/email login dialog.
- `plugins/builtin/netease/lib/qr_login.py`
  - QR key fetch, image generation, polling thread.
- `plugins/builtin/netease/lib/settings_tab.py`
  - Quality/download-dir settings plus login/logout controls.
- `plugins/builtin/netease/lib/online_music_view.py`
  - Main NetEase page shell with search, charts, recommendations, and navigation.
- `plugins/builtin/netease/lib/online_detail_view.py`
  - Artist/album/playlist detail page.
- `plugins/builtin/netease/lib/online_grid_view.py`
  - Reusable card grid for albums/playlists/artists.
- `plugins/builtin/netease/lib/online_tracks_list_view.py`
  - Reusable tracks list widget with play/queue/download/favorite actions.
- `plugins/builtin/netease/translations/zh.json`
  - Chinese plugin strings.
- `plugins/builtin/netease/translations/en.json`
  - English plugin strings.
- `tests/test_plugins/test_netease_plugin.py`
  - Plugin registration tests.
- `tests/test_services/test_netease_client.py`
  - Anonymous and auth client behavior tests.
- `tests/test_services/test_netease_provider.py`
  - Playback/download/provider-id tests.
- `tests/test_ui/test_netease_settings_tab.py`
  - Settings tab and login entrypoint tests.
- `tests/test_ui/test_netease_online_views.py`
  - Search/home/detail UI tests.
- `tests/test_system/test_plugin_import_guard.py`
  - Import-audit regression for the new built-in plugin.

### Task 1: Scaffold The Built-In Plugin

**Files:**
- Create: `plugins/builtin/netease/__init__.py`
- Create: `plugins/builtin/netease/plugin.json`
- Create: `plugins/builtin/netease/plugin_main.py`
- Create: `plugins/builtin/netease/lib/__init__.py`
- Create: `plugins/builtin/netease/lib/provider.py`
- Create: `plugins/builtin/netease/lib/settings_tab.py`
- Create: `plugins/builtin/netease/lib/online_music_view.py`
- Test: `tests/test_plugins/test_netease_plugin.py`
- Modify: `tests/test_system/test_plugin_import_guard.py`

- [ ] **Step 1: Write the failing registration and import-audit tests**

```python
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from plugins.builtin.netease.plugin_main import NetEasePlugin
from system.plugins.installer import audit_plugin_imports


def test_netease_plugin_registers_expected_capabilities():
    context = Mock()
    plugin = NetEasePlugin()

    plugin.register(context)

    assert context.ui.register_sidebar_entry.call_count == 1
    assert context.ui.register_settings_tab.call_count == 1
    assert context.services.register_online_music_provider.call_count == 1


def test_builtin_netease_plugin_passes_import_audit():
    audit_plugin_imports(Path("plugins/builtin/netease"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_plugins/test_netease_plugin.py tests/test_system/test_plugin_import_guard.py -k netease -v`

Expected: FAIL with `ModuleNotFoundError` for `plugins.builtin.netease` or missing built-in audit assertion.

- [ ] **Step 3: Add the minimal plugin scaffold**

`plugins/builtin/netease/plugin.json`

```json
{
  "id": "netease",
  "name": "NetEase",
  "version": "0.1.0",
  "api_version": "1",
  "entrypoint": "plugin_main.py",
  "entry_class": "NetEasePlugin",
  "capabilities": ["sidebar", "settings_tab", "online_music_provider"],
  "min_app_version": "0.1.0",
  "requires_restart_on_toggle": true
}
```

`plugins/builtin/netease/plugin_main.py`

```python
from __future__ import annotations

from harmony_plugin_api.registry_types import SettingsTabSpec, SidebarEntrySpec

from .lib.online_music_view import NetEaseOnlineMusicView
from .lib.provider import NetEaseOnlineProvider
from .lib.settings_tab import NetEaseSettingsTab


class NetEasePlugin:
    plugin_id = "netease"

    def register(self, context) -> None:
        provider = NetEaseOnlineProvider(context)
        context.ui.register_sidebar_entry(
            SidebarEntrySpec(
                plugin_id="netease",
                entry_id="netease.sidebar",
                title="NetEase",
                order=81,
                icon_name="music",
                icon_path=None,
                page_factory=lambda _context, parent: NetEaseOnlineMusicView(context, provider, parent),
            )
        )
        context.ui.register_settings_tab(
            SettingsTabSpec(
                plugin_id="netease",
                tab_id="netease.settings",
                title="NetEase",
                order=81,
                widget_factory=lambda _context, parent: NetEaseSettingsTab(context, provider, parent),
            )
        )
        context.services.register_online_music_provider(provider)

    def unregister(self, context) -> None:
        return None
```

`plugins/builtin/netease/lib/provider.py`

```python
from __future__ import annotations


class NetEaseOnlineProvider:
    provider_id = "netease"
    display_name = "NetEase"

    def __init__(self, context):
        self._context = context

    def create_page(self, context, parent=None):
        from .online_music_view import NetEaseOnlineMusicView
        return NetEaseOnlineMusicView(context, self, parent)
```

- [ ] **Step 4: Run tests to verify the scaffold passes**

Run: `uv run pytest tests/test_plugins/test_netease_plugin.py tests/test_system/test_plugin_import_guard.py -k netease -v`

Expected: PASS for the new NetEase registration and import-audit checks.

- [ ] **Step 5: Commit**

```bash
git add plugins/builtin/netease tests/test_plugins/test_netease_plugin.py tests/test_system/test_plugin_import_guard.py
git commit -m "新增网易云插件骨架"
```

### Task 2: Build Shared Plugin Foundations

**Files:**
- Create: `plugins/builtin/netease/lib/constants.py`
- Create: `plugins/builtin/netease/lib/errors.py`
- Create: `plugins/builtin/netease/lib/models.py`
- Create: `plugins/builtin/netease/lib/i18n.py`
- Create: `plugins/builtin/netease/lib/auth_store.py`
- Create: `plugins/builtin/netease/translations/zh.json`
- Create: `plugins/builtin/netease/translations/en.json`
- Test: `tests/test_services/test_netease_client.py`

- [ ] **Step 1: Write the failing auth-store and constants tests**

```python
from types import SimpleNamespace

from plugins.builtin.netease.lib.auth_store import NeteaseAuthStore
from plugins.builtin.netease.lib.constants import NETEASE_PROVIDER_ID


def test_auth_store_round_trips_cookie_and_profile():
    bucket = {}
    settings = SimpleNamespace(
        get=lambda key, default=None: bucket.get(key, default),
        set=lambda key, value: bucket.__setitem__(key, value),
    )
    store = NeteaseAuthStore(settings)

    store.save_login(cookie="MUSIC_U=abc;", profile={"userId": 7, "nickname": "neo"}, method="qr")

    assert store.cookie() == "MUSIC_U=abc;"
    assert store.profile()["nickname"] == "neo"
    assert store.last_login_method() == "qr"
    assert NETEASE_PROVIDER_ID == "netease"


def test_auth_store_clear_login_resets_all_fields():
    bucket = {
        "netease.cookie": "MUSIC_U=abc;",
        "netease.user_profile": {"userId": 7},
        "netease.last_login_method": "email",
    }
    settings = SimpleNamespace(
        get=lambda key, default=None: bucket.get(key, default),
        set=lambda key, value: bucket.__setitem__(key, value),
    )
    store = NeteaseAuthStore(settings)

    store.clear_login()

    assert store.cookie() == ""
    assert store.profile() == {}
    assert store.last_login_method() == ""
```

- [ ] **Step 2: Run the auth-store tests to verify they fail**

Run: `uv run pytest tests/test_services/test_netease_client.py -k auth_store -v`

Expected: FAIL with missing module errors for `auth_store` and `constants`.

- [ ] **Step 3: Implement constants, errors, models, i18n, and auth store**

`plugins/builtin/netease/lib/constants.py`

```python
NETEASE_PROVIDER_ID = "netease"
NETEASE_SOURCE_ID = "netease"
DEFAULT_QUALITY = "320"
SETTING_COOKIE = "netease.cookie"
SETTING_PROFILE = "netease.user_profile"
SETTING_LAST_VERIFIED = "netease.last_verified_at"
SETTING_LAST_LOGIN_METHOD = "netease.last_login_method"
SETTING_QUALITY = "netease.quality"
SETTING_DOWNLOAD_DIR = "netease.download_dir"
```

`plugins/builtin/netease/lib/errors.py`

```python
class NeteaseRequestError(RuntimeError):
    pass


class NeteaseLoginError(NeteaseRequestError):
    pass


class NeteaseAuthExpiredError(NeteaseRequestError):
    pass


class NeteaseRateLimitError(NeteaseRequestError):
    pass
```

`plugins/builtin/netease/lib/auth_store.py`

```python
from __future__ import annotations

import time

from .constants import (
    SETTING_COOKIE,
    SETTING_LAST_LOGIN_METHOD,
    SETTING_LAST_VERIFIED,
    SETTING_PROFILE,
)


class NeteaseAuthStore:
    def __init__(self, settings):
        self._settings = settings

    def save_login(self, *, cookie: str, profile: dict, method: str) -> None:
        self._settings.set(SETTING_COOKIE, cookie)
        self._settings.set(SETTING_PROFILE, profile)
        self._settings.set(SETTING_LAST_LOGIN_METHOD, method)
        self._settings.set(SETTING_LAST_VERIFIED, int(time.time()))

    def clear_login(self) -> None:
        self._settings.set(SETTING_COOKIE, "")
        self._settings.set(SETTING_PROFILE, {})
        self._settings.set(SETTING_LAST_LOGIN_METHOD, "")
        self._settings.set(SETTING_LAST_VERIFIED, 0)

    def cookie(self) -> str:
        return str(self._settings.get(SETTING_COOKIE, "") or "")

    def profile(self) -> dict:
        return dict(self._settings.get(SETTING_PROFILE, {}) or {})

    def last_login_method(self) -> str:
        return str(self._settings.get(SETTING_LAST_LOGIN_METHOD, "") or "")
```

`plugins/builtin/netease/lib/models.py`

```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class NeteaseAuthState:
    cookie: str = ""
    profile: dict = field(default_factory=dict)
    login_method: str = ""
    last_verified_at: int = 0


@dataclass(slots=True)
class NeteaseTrack:
    mid: str
    title: str
    artist: str
    album: str = ""
    album_mid: str = ""
    duration: int = 0
    cover_url: str = ""
```

`plugins/builtin/netease/lib/i18n.py`

```python
from __future__ import annotations

import json
from pathlib import Path

_LANG = "zh"
_CACHE = {}


def set_language(language: str) -> None:
    global _LANG
    _LANG = language or "zh"


def t(key: str, default: str = "") -> str:
    path = Path(__file__).resolve().parent.parent / "translations" / f"{_LANG}.json"
    if path not in _CACHE:
        _CACHE[path] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return str(_CACHE[path].get(key, default or key))
```

`plugins/builtin/netease/translations/zh.json`

```json
{
  "netease_title": "网易云音乐",
  "login": "登录",
  "logout": "退出登录",
  "search": "搜索"
}
```

`plugins/builtin/netease/translations/en.json`

```json
{
  "netease_title": "NetEase",
  "login": "Login",
  "logout": "Logout",
  "search": "Search"
}
```

- [ ] **Step 4: Run the tests to verify the foundation passes**

Run: `uv run pytest tests/test_services/test_netease_client.py -k auth_store -v`

Expected: PASS for auth-store persistence and clear behavior.

- [ ] **Step 5: Commit**

```bash
git add plugins/builtin/netease/lib/constants.py plugins/builtin/netease/lib/errors.py plugins/builtin/netease/lib/models.py plugins/builtin/netease/lib/i18n.py plugins/builtin/netease/lib/auth_store.py plugins/builtin/netease/translations tests/test_services/test_netease_client.py
git commit -m "补充网易云插件基础层"
```

### Task 3: Implement Anonymous API And Client Flows

**Files:**
- Create: `plugins/builtin/netease/lib/api.py`
- Create: `plugins/builtin/netease/lib/adapters.py`
- Create: `plugins/builtin/netease/lib/client.py`
- Modify: `tests/test_services/test_netease_client.py`

- [ ] **Step 1: Write the failing anonymous search/detail client tests**

```python
from unittest.mock import Mock

from plugins.builtin.netease.lib.client import NeteaseClient


def test_client_search_tracks_maps_song_results():
    http = Mock()
    http.get.return_value = Mock(
        status_code=200,
        json=lambda: {
            "result": {
                "songs": [
                    {
                        "id": 1001,
                        "name": "Song A",
                        "duration": 180000,
                        "artists": [{"id": 77, "name": "Artist A"}],
                        "album": {"id": 88, "name": "Album A", "picUrl": "https://img/a.jpg"},
                    }
                ]
            }
        },
    )
    client = NeteaseClient(http_client=http, settings=Mock())

    result = client.search("Song A", search_type="song", page=1, page_size=20)

    assert result["total"] == 1
    assert result["tracks"][0]["mid"] == "1001"
    assert result["tracks"][0]["artist"] == "Artist A"
    assert result["tracks"][0]["album_mid"] == "88"


def test_client_get_top_lists_maps_playlist_rows():
    http = Mock()
    http.get.return_value = Mock(
        status_code=200,
        json=lambda: {
            "list": [{"id": 3, "name": "飙升榜", "coverImgUrl": "https://img/top.jpg", "trackCount": 100}]
        },
    )
    client = NeteaseClient(http_client=http, settings=Mock())

    top_lists = client.get_top_lists()

    assert top_lists[0]["id"] == "3"
    assert top_lists[0]["title"] == "飙升榜"
```

- [ ] **Step 2: Run tests to verify the anonymous client is not implemented yet**

Run: `uv run pytest tests/test_services/test_netease_client.py -k "search_tracks or top_lists" -v`

Expected: FAIL because `NeteaseClient` does not exist or returns empty/incorrect mappings.

- [ ] **Step 3: Implement low-level API wrappers and anonymous mapping helpers**

`plugins/builtin/netease/lib/api.py`

```python
from __future__ import annotations


class NeteaseApi:
    def __init__(self, http_client):
        self._http = http_client

    def search(self, keyword: str, *, search_type: str, page: int, page_size: int):
        type_map = {"song": 1, "artist": 100, "album": 10, "playlist": 1000}
        offset = max(page - 1, 0) * page_size
        return self._http.get(
            "https://music.163.com/api/search/get/web",
            params={"s": keyword, "type": str(type_map[search_type]), "limit": str(page_size), "offset": str(offset)},
            timeout=5,
        )

    def toplist(self):
        return self._http.get("https://music.163.com/api/toplist", timeout=5)

    def playlist_detail(self, playlist_id: str):
        return self._http.get("https://music.163.com/api/v6/playlist/detail", params={"id": playlist_id}, timeout=5)

    def album_detail(self, album_id: str):
        return self._http.get(f"https://music.163.com/api/v1/album/{album_id}", timeout=5)

    def artist_detail(self, artist_id: str):
        return self._http.get("https://music.163.com/api/artist/head/info/get", params={"id": artist_id}, timeout=5)
```

`plugins/builtin/netease/lib/client.py`

```python
from __future__ import annotations

from .adapters import map_album_detail, map_artist_detail, map_playlist_detail, map_search_payload, map_toplist_payload
from .api import NeteaseApi


class NeteaseClient:
    def __init__(self, http_client, settings):
        self._api = NeteaseApi(http_client)
        self._settings = settings

    def search(self, keyword: str, search_type: str = "song", *, page: int = 1, page_size: int = 30) -> dict:
        response = self._api.search(keyword, search_type=search_type, page=page, page_size=page_size)
        return map_search_payload(response.json(), search_type=search_type, keyword=keyword, page=page, page_size=page_size)

    def get_top_lists(self) -> list[dict]:
        return map_toplist_payload(self._api.toplist().json())

    def get_playlist_detail(self, playlist_id: str) -> dict | None:
        return map_playlist_detail(self._api.playlist_detail(playlist_id).json())
```

`plugins/builtin/netease/lib/adapters.py`

```python
from __future__ import annotations


def map_song_row(song: dict) -> dict:
    album = song.get("album") or song.get("al") or {}
    artists = song.get("artists") or song.get("ar") or []
    return {
        "mid": str(song.get("id", "")),
        "title": song.get("name", ""),
        "artist": artists[0].get("name", "") if artists else "",
        "album": album.get("name", ""),
        "album_mid": str(album.get("id", "")),
        "duration": int((song.get("duration") or song.get("dt") or 0) / 1000),
        "cover_url": album.get("picUrl", ""),
    }


def map_toplist_payload(payload: dict) -> list[dict]:
    return [
        {
            "id": str(item.get("id", "")),
            "title": item.get("name", ""),
            "cover_url": item.get("coverImgUrl", ""),
            "song_count": int(item.get("trackCount", 0) or 0),
        }
        for item in payload.get("list", [])
    ]
```

- [ ] **Step 4: Run the anonymous client tests**

Run: `uv run pytest tests/test_services/test_netease_client.py -k "search_tracks or top_lists" -v`

Expected: PASS for song search and top list mappings.

- [ ] **Step 5: Commit**

```bash
git add plugins/builtin/netease/lib/api.py plugins/builtin/netease/lib/adapters.py plugins/builtin/netease/lib/client.py tests/test_services/test_netease_client.py
git commit -m "实现网易云匿名接口"
```

### Task 4: Add Cellphone, Email, And QR Login Flows

**Files:**
- Modify: `plugins/builtin/netease/lib/api.py`
- Modify: `plugins/builtin/netease/lib/client.py`
- Create: `plugins/builtin/netease/lib/login_dialog.py`
- Create: `plugins/builtin/netease/lib/qr_login.py`
- Modify: `plugins/builtin/netease/lib/settings_tab.py`
- Modify: `tests/test_services/test_netease_client.py`
- Create: `tests/test_ui/test_netease_settings_tab.py`

- [ ] **Step 1: Write the failing auth and settings-tab tests**

```python
from unittest.mock import Mock

from plugins.builtin.netease.lib.client import NeteaseClient


def test_client_login_with_phone_saves_cookie_and_profile():
    http = Mock()
    http.get.return_value = Mock(status_code=200, json=lambda: {"profile": {"userId": 7, "nickname": "neo"}})
    http.post.return_value = Mock(status_code=200, json=lambda: {"code": 200, "profile": {"userId": 7, "nickname": "neo"}}, cookies={"MUSIC_U": "abc"})
    settings = Mock()
    client = NeteaseClient(http_client=http, settings=settings)

    profile = client.login_with_phone(phone="13800138000", password="secret")

    assert profile["nickname"] == "neo"
    settings.set.assert_any_call("netease.cookie", "MUSIC_U=abc")


def test_settings_tab_logout_clears_auth_state(qtbot):
    context = Mock()
    provider = Mock()
    tab = NetEaseSettingsTab(context, provider)
    tab._auth_store = Mock()

    tab._logout()

    tab._auth_store.clear_login.assert_called_once()
```

- [ ] **Step 2: Run the login/settings tests to verify failure**

Run: `uv run pytest tests/test_services/test_netease_client.py -k "login_with_phone or login_with_email or qr" tests/test_ui/test_netease_settings_tab.py -v`

Expected: FAIL because login helpers, QR flow, and settings tab behavior are not implemented.

- [ ] **Step 3: Implement login endpoints, auth persistence, and UI hooks**

`plugins/builtin/netease/lib/api.py`

```python
    def login_phone(self, phone: str, password_md5: str, country_code: str = "86"):
        return self._http.post(
            "https://music.163.com/api/w/login/cellphone",
            data={"phone": phone, "countrycode": country_code, "password": password_md5, "remember": "true"},
            timeout=8,
        )

    def login_email(self, email: str, password_md5: str):
        return self._http.post(
            "https://music.163.com/api/w/login",
            data={"username": email, "password": password_md5, "rememberLogin": "true"},
            timeout=8,
        )

    def qr_key(self):
        return self._http.get("https://music.163.com/api/login/qrcode/unikey", timeout=8)

    def qr_create(self, key: str):
        return self._http.get("https://music.163.com/api/login/qrcode/create", params={"key": key, "qrimg": "true"}, timeout=8)

    def qr_check(self, key: str):
        return self._http.get("https://music.163.com/api/login/qrcode/client/login", params={"key": key, "type": "3"}, timeout=8)
```

`plugins/builtin/netease/lib/client.py`

```python
import hashlib

from .auth_store import NeteaseAuthStore
from .errors import NeteaseLoginError


    def __init__(self, http_client, settings):
        self._api = NeteaseApi(http_client)
        self._settings = settings
        self._auth_store = NeteaseAuthStore(settings)

    @staticmethod
    def _md5(text: str) -> str:
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def login_with_phone(self, *, phone: str, password: str, country_code: str = "86") -> dict:
        response = self._api.login_phone(phone, self._md5(password), country_code=country_code)
        payload = response.json()
        if payload.get("code") != 200:
            raise NeteaseLoginError(payload.get("message", "phone login failed"))
        cookie = ";".join(f"{name}={value}" for name, value in response.cookies.items())
        profile = dict(payload.get("profile", {}) or {})
        self._auth_store.save_login(cookie=cookie, profile=profile, method="phone")
        return profile
```

`plugins/builtin/netease/lib/login_dialog.py`

```python
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLineEdit, QPushButton, QVBoxLayout, QWidget


class NetEaseLoginDialog(QDialog):
    def __init__(self, client, parent=None):
        super().__init__(parent)
        self._client = client
        self._phone_input = QLineEdit(self)
        self._email_input = QLineEdit(self)
        self._password_input = QLineEdit(self)
        self._phone_login_btn = QPushButton("Phone Login", self)
        self._email_login_btn = QPushButton("Email Login", self)
        layout = QVBoxLayout(self)
        layout.addWidget(self._phone_input)
        layout.addWidget(self._email_input)
        layout.addWidget(self._password_input)
        layout.addWidget(self._phone_login_btn)
        layout.addWidget(self._email_login_btn)
        self._phone_login_btn.clicked.connect(self._login_phone)
        self._email_login_btn.clicked.connect(self._login_email)

    def _login_phone(self):
        self._client.login_with_phone(phone=self._phone_input.text().strip(), password=self._password_input.text())

    def _login_email(self):
        self._client.login_with_email(email=self._email_input.text().strip(), password=self._password_input.text())
```

`plugins/builtin/netease/lib/qr_login.py`

```python
from __future__ import annotations

from PySide6.QtCore import QThread, Signal


class NetEaseQrLoginThread(QThread):
    qr_ready = Signal(str)
    login_success = Signal(dict)
    login_failed = Signal(str)

    def __init__(self, client):
        super().__init__()
        self._client = client

    def run(self):
        key = self._client.get_qr_key()
        qr = self._client.get_qr_image(key)
        self.qr_ready.emit(qr)
        profile = self._client.poll_qr_login(key)
        self.login_success.emit(profile)
```

`plugins/builtin/netease/lib/settings_tab.py`

```python
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class NetEaseSettingsTab(QWidget):
    def __init__(self, context, provider, parent=None):
        super().__init__(parent)
        self._context = context
        self._provider = provider
        self._auth_store = provider._client._auth_store
        self._status_label = QLabel(self)
        self._logout_btn = QPushButton("Logout", self)
        layout = QVBoxLayout(self)
        layout.addWidget(self._status_label)
        layout.addWidget(self._logout_btn)
        self._logout_btn.clicked.connect(self._logout)

    def _logout(self):
        self._auth_store.clear_login()
        self._status_label.setText("Logged out")
```

- [ ] **Step 4: Run auth and settings-tab tests**

Run: `uv run pytest tests/test_services/test_netease_client.py -k "login_with_phone or login_with_email or qr" tests/test_ui/test_netease_settings_tab.py -v`

Expected: PASS for login persistence, logout behavior, and basic QR polling state transitions.

- [ ] **Step 5: Commit**

```bash
git add plugins/builtin/netease/lib/api.py plugins/builtin/netease/lib/client.py plugins/builtin/netease/lib/login_dialog.py plugins/builtin/netease/lib/qr_login.py plugins/builtin/netease/lib/settings_tab.py tests/test_services/test_netease_client.py tests/test_ui/test_netease_settings_tab.py
git commit -m "实现网易云登录流程"
```

### Task 5: Implement The Provider And Media Integration

**Files:**
- Modify: `plugins/builtin/netease/lib/provider.py`
- Modify: `plugins/builtin/netease/lib/client.py`
- Create: `tests/test_services/test_netease_provider.py`

- [ ] **Step 1: Write the failing provider playback/download tests**

```python
from unittest.mock import Mock

from plugins.builtin.netease.lib.provider import NetEaseOnlineProvider


def test_provider_get_playback_url_info_reads_client_result():
    context = Mock()
    provider = NetEaseOnlineProvider(context)
    provider._client = Mock()
    provider._client.get_playback_url_info.return_value = {"url": "https://cdn/song.mp3", "quality": "320"}

    info = provider.get_playback_url_info("1001", "320")

    assert info["url"] == "https://cdn/song.mp3"


def test_provider_download_track_returns_local_path_payload():
    context = Mock()
    provider = NetEaseOnlineProvider(context)
    provider._download_gateway = Mock()
    provider._download_gateway.download.return_value = "/tmp/netease/1001.mp3"

    result = provider.download_track("1001", "320", target_dir="/tmp/netease")

    assert result["local_path"] == "/tmp/netease/1001.mp3"
    assert result["quality"] == "320"
```

- [ ] **Step 2: Run the provider tests to verify failure**

Run: `uv run pytest tests/test_services/test_netease_provider.py -v`

Expected: FAIL because playback URL lookup and download methods are still placeholders.

- [ ] **Step 3: Implement provider and playback/download hooks**

`plugins/builtin/netease/lib/provider.py`

```python
from __future__ import annotations

from .client import NeteaseClient
from .constants import DEFAULT_QUALITY


class NetEaseOnlineProvider:
    provider_id = "netease"
    display_name = "NetEase"

    def __init__(self, context):
        self._context = context
        self._client = NeteaseClient(context.http, context.settings)
        self._download_gateway = context.runtime.bootstrap().online_download_service

    def get_playback_url_info(self, track_id: str, quality: str):
        return self._client.get_playback_url_info(track_id, quality or DEFAULT_QUALITY)

    def get_download_qualities(self, track_id: str):
        del track_id
        return [{"value": "320", "label": "320K"}, {"value": "flac", "label": "FLAC"}]

    def download_track(self, track_id: str, quality: str, target_dir: str | None = None, progress_callback=None, force: bool = False):
        if target_dir and hasattr(self._download_gateway, "set_download_dir"):
            self._download_gateway.set_download_dir(target_dir)
        local_path = self._download_gateway.download(track_id, provider_id=self.provider_id, quality=quality, progress_callback=progress_callback, force=force)
        if not local_path:
            return None
        return {"local_path": local_path, "quality": quality}

    def redownload_track(self, track_id: str, quality: str, target_dir: str | None = None, progress_callback=None):
        return self.download_track(track_id, quality, target_dir=target_dir, progress_callback=progress_callback, force=True)
```

- [ ] **Step 4: Run the provider tests**

Run: `uv run pytest tests/test_services/test_netease_provider.py -v`

Expected: PASS for playback info, provider id, download, and redownload behavior.

- [ ] **Step 5: Commit**

```bash
git add plugins/builtin/netease/lib/provider.py plugins/builtin/netease/lib/client.py tests/test_services/test_netease_provider.py
git commit -m "接通网易云provider能力"
```

### Task 6: Build The Main Page And Detail UI

**Files:**
- Modify: `plugins/builtin/netease/lib/online_music_view.py`
- Create: `plugins/builtin/netease/lib/online_detail_view.py`
- Create: `plugins/builtin/netease/lib/online_grid_view.py`
- Create: `plugins/builtin/netease/lib/online_tracks_list_view.py`
- Create: `tests/test_ui/test_netease_online_views.py`

- [ ] **Step 1: Write the failing online-view tests**

```python
from unittest.mock import Mock

from plugins.builtin.netease.lib.online_music_view import NetEaseOnlineMusicView


def test_online_view_search_button_loads_song_results(qtbot):
    context = Mock()
    provider = Mock()
    provider.search.return_value = {"tracks": [{"mid": "1001", "title": "Song A", "artist": "Artist A"}], "total": 1}

    view = NetEaseOnlineMusicView(context, provider)
    qtbot.addWidget(view)
    view._search_input.setText("Song A")

    view._do_search()

    assert view._tracks_list.count() == 1


def test_online_view_logged_out_hides_recommendation_sections(qtbot):
    context = Mock()
    provider = Mock(is_logged_in=Mock(return_value=False))
    view = NetEaseOnlineMusicView(context, provider)
    qtbot.addWidget(view)

    assert view._recommend_section.isHidden() is True
    assert view._my_playlists_section.isHidden() is True
```

- [ ] **Step 2: Run the view tests to verify failure**

Run: `uv run pytest tests/test_ui/test_netease_online_views.py -v`

Expected: FAIL because the main page widgets and search flow are not implemented.

- [ ] **Step 3: Implement the page shell and detail shell**

`plugins/builtin/netease/lib/online_music_view.py`

```python
from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QListWidget, QPushButton, QVBoxLayout, QWidget


class NetEaseOnlineMusicView(QWidget):
    def __init__(self, context, provider, parent=None):
        super().__init__(parent)
        self._context = context
        self._provider = provider
        self._search_input = QLineEdit(self)
        self._search_btn = QPushButton("Search", self)
        self._tracks_list = QListWidget(self)
        self._recommend_section = QWidget(self)
        self._my_playlists_section = QWidget(self)
        self._build_ui()
        self._refresh_login_state()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        header.addWidget(self._search_input)
        header.addWidget(self._search_btn)
        layout.addLayout(header)
        layout.addWidget(self._recommend_section)
        layout.addWidget(self._my_playlists_section)
        layout.addWidget(self._tracks_list)
        self._search_btn.clicked.connect(self._do_search)

    def _refresh_login_state(self):
        logged_in = bool(getattr(self._provider, "is_logged_in", lambda: False)())
        self._recommend_section.setHidden(not logged_in)
        self._my_playlists_section.setHidden(not logged_in)

    def _do_search(self):
        payload = self._provider.search(self._search_input.text().strip(), search_type="song", page=1, page_size=30)
        self._tracks_list.clear()
        for item in payload.get("tracks", []):
            self._tracks_list.addItem(f"{item['title']} - {item['artist']}")
```

`plugins/builtin/netease/lib/online_tracks_list_view.py`

```python
from __future__ import annotations

from PySide6.QtWidgets import QListWidget


class NetEaseOnlineTracksListView(QListWidget):
    def set_tracks(self, tracks: list[dict]) -> None:
        self.clear()
        for track in tracks:
            self.addItem(f"{track['title']} - {track['artist']}")
```

`plugins/builtin/netease/lib/online_grid_view.py`

```python
from __future__ import annotations

from PySide6.QtWidgets import QListWidget


class NetEaseOnlineGridView(QListWidget):
    def set_cards(self, items: list[dict]) -> None:
        self.clear()
        for item in items:
            self.addItem(item.get("title") or item.get("name", ""))
```

`plugins/builtin/netease/lib/online_detail_view.py`

```python
from __future__ import annotations

from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget


class NetEaseOnlineDetailView(QWidget):
    def __init__(self, context, provider, parent=None):
        super().__init__(parent)
        self._context = context
        self._provider = provider
        self._detail_type = ""
        self._detail_id = ""
        self._follow_btn = QPushButton("Follow", self)
        self._favorite_btn = QPushButton("Favorite", self)
        layout = QVBoxLayout(self)
        layout.addWidget(self._follow_btn)
        layout.addWidget(self._favorite_btn)
        self._follow_btn.clicked.connect(self._on_follow_clicked)
        self._favorite_btn.clicked.connect(self._on_favorite_clicked)
```

- [ ] **Step 4: Run the UI tests**

Run: `uv run pytest tests/test_ui/test_netease_online_views.py -v`

Expected: PASS for the initial search and logged-out visibility behaviors.

- [ ] **Step 5: Commit**

```bash
git add plugins/builtin/netease/lib/online_music_view.py plugins/builtin/netease/lib/online_detail_view.py plugins/builtin/netease/lib/online_grid_view.py plugins/builtin/netease/lib/online_tracks_list_view.py tests/test_ui/test_netease_online_views.py
git commit -m "搭建网易云在线页面"
```

### Task 7: Add Logged-In Recommendations, Detail Actions, And Final Regression Coverage

**Files:**
- Modify: `plugins/builtin/netease/lib/client.py`
- Modify: `plugins/builtin/netease/lib/online_music_view.py`
- Modify: `plugins/builtin/netease/lib/online_detail_view.py`
- Modify: `tests/test_services/test_netease_client.py`
- Modify: `tests/test_ui/test_netease_online_views.py`
- Modify: `tests/test_system/test_plugin_import_guard.py`

- [ ] **Step 1: Write the failing recommendation/detail-action tests**

```python
from unittest.mock import Mock

from plugins.builtin.netease.lib.client import NeteaseClient


def test_client_get_recommendations_requires_login_and_maps_tracks():
    http = Mock()
    settings = Mock()
    client = NeteaseClient(http_client=http, settings=settings)
    client._auth_store = Mock(cookie=Mock(return_value="MUSIC_U=abc;"))
    client._api.recommend_songs = Mock(return_value=Mock(status_code=200, json=lambda: {"data": {"dailySongs": [{"id": 1001, "name": "Song A", "ar": [{"name": "Artist A"}], "al": {"id": 88, "name": "Album A"}}]}}))

    items = client.get_recommendations()

    assert items[0]["mid"] == "1001"
    assert items[0]["artist"] == "Artist A"


def test_detail_view_follow_button_calls_provider(qtbot):
    context = Mock()
    provider = Mock()
    view = NetEaseOnlineDetailView(context, provider)
    qtbot.addWidget(view)
    view._detail_type = "artist"
    view._detail_id = "77"

    view._on_follow_clicked()

    provider.follow_artist.assert_called_once_with("77")
```

- [ ] **Step 2: Run recommendation/detail tests to verify failure**

Run: `uv run pytest tests/test_services/test_netease_client.py -k "recommendations or user_playlists or liked" tests/test_ui/test_netease_online_views.py -k "follow_button or favorite_button" -v`

Expected: FAIL because logged-in sections and detail actions are not wired.

- [ ] **Step 3: Implement logged-in data loaders and detail actions**

`plugins/builtin/netease/lib/client.py`

```python
from .errors import NeteaseAuthExpiredError


    def _require_login(self) -> None:
        if not self._auth_store.cookie():
            raise NeteaseAuthExpiredError("login required")

    def get_recommendations(self) -> list[dict]:
        self._require_login()
        payload = self._api.recommend_songs().json()
        songs = payload.get("data", {}).get("dailySongs", [])
        return [map_song_row(song) for song in songs]

    def get_user_playlists(self, user_id: str) -> list[dict]:
        self._require_login()
        return map_user_playlists(self._api.user_playlist(user_id).json())

    def get_liked_playlist(self, user_id: str) -> dict | None:
        playlists = self.get_user_playlists(user_id)
        return playlists[0] if playlists else None
```

`plugins/builtin/netease/lib/online_detail_view.py`

```python
    def _on_follow_clicked(self):
        if self._detail_type == "artist" and self._detail_id:
            self._provider.follow_artist(self._detail_id)

    def _on_favorite_clicked(self):
        if self._detail_type == "album" and self._detail_id:
            self._provider.fav_album(self._detail_id)
        elif self._detail_type == "playlist" and self._detail_id:
            self._provider.fav_playlist(self._detail_id)
```

- [ ] **Step 4: Run focused tests and then the full changed-area suite**

Run: `uv run pytest tests/test_plugins/test_netease_plugin.py tests/test_services/test_netease_client.py tests/test_services/test_netease_provider.py tests/test_ui/test_netease_settings_tab.py tests/test_ui/test_netease_online_views.py tests/test_system/test_plugin_import_guard.py -k netease -v`

Expected: PASS across plugin registration, client behavior, provider behavior, settings tab, UI flows, and import-audit coverage.

- [ ] **Step 5: Commit**

```bash
git add plugins/builtin/netease/lib/client.py plugins/builtin/netease/lib/online_music_view.py plugins/builtin/netease/lib/online_detail_view.py tests/test_services/test_netease_client.py tests/test_ui/test_netease_online_views.py tests/test_system/test_plugin_import_guard.py
git commit -m "完善网易云登录态功能"
```

## Self-Review

- Spec coverage:
  - Plugin location and future external-plugin boundary are covered by Tasks 1-2 and Task 7 import-audit regression.
  - Anonymous search/toplists/details are covered by Task 3.
  - Phone/email/QR login plus logout and login status are covered by Task 4.
  - Playback/download/provider integration are covered by Task 5.
  - Sidebar page, search tabs, and detail shells are covered by Task 6.
  - Logged-in recommendations, liked songs, user playlists, and favorite/follow actions are covered by Task 7.
- Placeholder scan:
  - No `TODO`, `TBD`, or cross-task “similar to previous task” placeholders remain.
- Type consistency:
  - The plan consistently uses `provider_id = "netease"`, plugin id `netease`, settings keys prefixed with `netease.`, and host-facing methods `get_playback_url_info`, `download_track`, and `redownload_track`.
