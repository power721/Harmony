# QQ Music Phone Login Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add China mainland `+86` phone verification-code login to the existing QQ Music login dialog without adding a second dialog or requiring restart after successful login.

**Architecture:** Extend the existing QQ Music client with two phone-login API methods that mirror the upstream reference payloads. Rework the existing login dialog into two modes, `QR` and `Phone`, while keeping the existing `credentials_obtained` success path so settings persistence, nickname refresh, and online page refresh continue to flow through one code path.

**Tech Stack:** Python, PySide6, pytest, unittest.mock, existing QQ Music plugin runtime/context bridges.

---

### Task 1: Add Phone Login API Methods To QQMusicClient

**Files:**
- Modify: `plugins/builtin/qqmusic/lib/qqmusic_client.py`
- Create: `tests/test_services/test_qqmusic_phone_login.py`

- [ ] **Step 1: Write the failing client tests**

```python
from plugins.builtin.qqmusic.lib.qqmusic_client import QQMusicClient


def test_send_phone_auth_code_uses_reference_payload():
    client = QQMusicClient()
    captured = {}

    def fake_make_request(module, method, params, _retry=False, use_sign=False, comm=None, platform=None):
        captured["module"] = module
        captured["method"] = method
        captured["params"] = params
        captured["retry"] = _retry
        captured["use_sign"] = use_sign
        captured["comm"] = comm
        captured["platform"] = platform
        return {"code": 0}

    client._make_request = fake_make_request

    result = client.send_phone_auth_code("13000000000")

    assert result == {"code": 0}
    assert captured == {
        "module": "music.login.LoginServer",
        "method": "SendPhoneAuthCode",
        "params": {
            "tmeAppid": "qqmusic",
            "phoneNo": "13000000000",
            "areaCode": "86",
        },
        "retry": False,
        "use_sign": False,
        "comm": {"tmeLoginMethod": 3},
        "platform": "android",
    }


def test_phone_authorize_uses_reference_payload():
    client = QQMusicClient()
    captured = {}

    def fake_make_request(module, method, params, _retry=False, use_sign=False, comm=None, platform=None):
        captured["module"] = module
        captured["method"] = method
        captured["params"] = params
        captured["retry"] = _retry
        captured["use_sign"] = use_sign
        captured["comm"] = comm
        captured["platform"] = platform
        return {
            "musicid": 123,
            "musickey": "secret",
            "refresh_key": "refresh-key",
            "refresh_token": "refresh-token",
            "loginType": 0,
            "encryptUin": "enc-uin",
        }

    client._make_request = fake_make_request

    result = client.phone_authorize("13000000000", "123456")

    assert captured == {
        "module": "music.login.LoginServer",
        "method": "Login",
        "params": {
            "code": "123456",
            "phoneNo": "13000000000",
            "areaCode": "86",
            "loginMode": 1,
        },
        "retry": False,
        "use_sign": False,
        "comm": {"tmeLoginMethod": 3, "tmeLoginType": 0},
        "platform": "android",
    }
    assert result["musicid"] == "123"
    assert result["musickey"] == "secret"
    assert result["login_type"] == 0
    assert result["encrypt_uin"] == "enc-uin"
```

- [ ] **Step 2: Run the new client tests to verify they fail**

Run: `uv run pytest tests/test_services/test_qqmusic_phone_login.py -v`

Expected: FAIL because `QQMusicClient` does not yet expose `send_phone_auth_code()` or `phone_authorize()`, and `_make_request()` does not yet accept per-call `comm` / `platform` overrides.

- [ ] **Step 3: Add minimal client implementation**

```python
def _make_request(
    self,
    module: str,
    method: str,
    params: Dict,
    _retry: bool = False,
    use_sign: bool = False,
    comm: Optional[Dict[str, Any]] = None,
    platform: Optional[str] = None,
) -> Dict:
    common = self._build_common_params()
    if comm:
        common.update(comm)
    if platform == "android":
        common.update({
            "ct": "11",
            "cv": APIConfig.VERSION_CODE,
            "v": APIConfig.VERSION_CODE,
            "tmeAppID": "qqmusic",
        })
```

```python
def send_phone_auth_code(self, phone: str, country_code: int = 86) -> Dict[str, Any]:
    return self._make_request(
        "music.login.LoginServer",
        "SendPhoneAuthCode",
        {
            "tmeAppid": "qqmusic",
            "phoneNo": str(phone),
            "areaCode": str(country_code),
        },
        comm={"tmeLoginMethod": 3},
        platform="android",
    )


def phone_authorize(self, phone: str, auth_code: str, country_code: int = 86) -> Dict[str, Any]:
    result = self._make_request(
        "music.login.LoginServer",
        "Login",
        {
            "code": str(auth_code),
            "phoneNo": str(phone),
            "areaCode": str(country_code),
            "loginMode": 1,
        },
        comm={"tmeLoginMethod": 3, "tmeLoginType": 0},
        platform="android",
    )
    if not result:
        return {}
    normalized = {
        **result,
        "musicid": str(result.get("musicid", "") or ""),
    }
    if "encryptUin" in result and "encrypt_uin" not in normalized:
        normalized["encrypt_uin"] = result["encryptUin"]
    if "loginType" in result and "login_type" not in normalized:
        normalized["login_type"] = result["loginType"]
    return normalized
```

- [ ] **Step 4: Run the client tests to verify they pass**

Run: `uv run pytest tests/test_services/test_qqmusic_phone_login.py -v`

Expected: PASS with 2 passed.

- [ ] **Step 5: Commit the client API work**

```bash
git add plugins/builtin/qqmusic/lib/qqmusic_client.py tests/test_services/test_qqmusic_phone_login.py
git commit -m "feat: add qqmusic phone login client methods"
```

### Task 2: Add Dialog Mode Switching And Phone Form Rendering

**Files:**
- Modify: `plugins/builtin/qqmusic/lib/login_dialog.py`
- Modify: `plugins/builtin/qqmusic/translations/zh.json`
- Modify: `plugins/builtin/qqmusic/translations/en.json`
- Create: `tests/test_ui/test_qqmusic_login_dialog.py`

- [ ] **Step 1: Write the failing dialog-mode tests**

```python
from unittest.mock import Mock

from plugins.builtin.qqmusic.lib.login_dialog import QQMusicLoginDialog


def test_login_dialog_defaults_to_qr_mode(qtbot):
    dialog = QQMusicLoginDialog(_build_plugin_context())
    qtbot.addWidget(dialog)

    assert dialog._login_mode == "qr"
    assert dialog._qr_mode_btn.isChecked() is True
    assert dialog._qr_panel.isVisible()
    assert not dialog._phone_panel.isVisible()


def test_login_dialog_can_switch_to_phone_mode(qtbot):
    dialog = QQMusicLoginDialog(_build_plugin_context())
    qtbot.addWidget(dialog)

    dialog._phone_mode_btn.click()

    assert dialog._login_mode == "phone"
    assert dialog._phone_panel.isVisible()
    assert not dialog._qr_panel.isVisible()
    assert dialog._country_code_label.text() == "+86"
```

- [ ] **Step 2: Run the dialog-mode tests to verify they fail**

Run: `uv run pytest tests/test_ui/test_qqmusic_login_dialog.py -k "defaults_to_qr_mode or switch_to_phone_mode" -v`

Expected: FAIL because the dialog has no `_login_mode`, `_qr_mode_btn`, `_phone_mode_btn`, `_qr_panel`, or `_phone_panel`.

- [ ] **Step 3: Add the minimal dialog structure**

```python
self._login_mode = "qr"
self._qr_mode_btn = QRadioButton(t("qqmusic_mode_qr"))
self._phone_mode_btn = QRadioButton(t("qqmusic_mode_phone"))
self._qr_mode_btn.setChecked(True)
self._qr_mode_btn.toggled.connect(self._on_login_mode_changed)
self._phone_mode_btn.toggled.connect(self._on_login_mode_changed)

self._qr_panel = QWidget()
self._phone_panel = QWidget()
self._country_code_label = QLabel("+86")
self._phone_input = QLineEdit()
self._phone_code_input = QLineEdit()
self._phone_send_code_btn = QPushButton(t("qqmusic_send_code"))
self._phone_submit_btn = QPushButton(t("qqmusic_login"))
self._phone_status_label = QLabel("")
```

```python
def _on_login_mode_changed(self):
    self._login_mode = "phone" if self._phone_mode_btn.isChecked() else "qr"
    self._qr_panel.setVisible(self._login_mode == "qr")
    self._phone_panel.setVisible(self._login_mode == "phone")
    if self._login_mode == "qr":
        self._restart_login()
    else:
        self._stop_qr_login_thread()
```

- [ ] **Step 4: Add the required translation keys**

```json
"qqmusic_mode_qr": "扫码登录",
"qqmusic_mode_phone": "手机验证码登录",
"qqmusic_phone_number": "手机号",
"qqmusic_phone_code": "验证码",
"qqmusic_send_code": "发送验证码",
"qqmusic_phone_hint": "仅支持中国大陆手机号 +86",
"qqmusic_phone_invalid": "请输入 11 位中国大陆手机号",
"qqmusic_code_invalid": "请输入 4 到 6 位数字验证码"
```

```json
"qqmusic_mode_qr": "QR Login",
"qqmusic_mode_phone": "Phone Login",
"qqmusic_phone_number": "Phone Number",
"qqmusic_phone_code": "Verification Code",
"qqmusic_send_code": "Send Code",
"qqmusic_phone_hint": "Only supports mainland China phone numbers (+86)",
"qqmusic_phone_invalid": "Enter an 11-digit mainland China phone number",
"qqmusic_code_invalid": "Enter a 4 to 6 digit verification code"
```

- [ ] **Step 5: Run the dialog-mode tests to verify they pass**

Run: `uv run pytest tests/test_ui/test_qqmusic_login_dialog.py -k "defaults_to_qr_mode or switch_to_phone_mode" -v`

Expected: PASS with 2 passed.

- [ ] **Step 6: Commit the dialog layout work**

```bash
git add plugins/builtin/qqmusic/lib/login_dialog.py plugins/builtin/qqmusic/translations/zh.json plugins/builtin/qqmusic/translations/en.json tests/test_ui/test_qqmusic_login_dialog.py
git commit -m "feat: add qqmusic phone login mode ui"
```

### Task 3: Implement Phone Auth Send And Submit Flow In The Dialog

**Files:**
- Modify: `plugins/builtin/qqmusic/lib/login_dialog.py`
- Modify: `tests/test_ui/test_qqmusic_login_dialog.py`

- [ ] **Step 1: Write the failing phone-flow tests**

```python
from unittest.mock import Mock


def test_phone_login_rejects_invalid_phone_inline(qtbot):
    dialog = QQMusicLoginDialog(_build_plugin_context())
    qtbot.addWidget(dialog)
    dialog._phone_mode_btn.click()
    dialog._phone_input.setText("123")

    dialog._send_phone_auth_code()

    assert dialog._phone_status_label.text() == "请输入 11 位中国大陆手机号"


def test_phone_login_emits_credentials_on_success(qtbot):
    context = _build_plugin_context()
    dialog = QQMusicLoginDialog(context)
    qtbot.addWidget(dialog)
    dialog._phone_mode_btn.click()
    dialog._phone_input.setText("13000000000")
    dialog._phone_code_input.setText("123456")
    dialog._phone_client = Mock()
    dialog._phone_client.phone_authorize.return_value = {"musicid": "1", "musickey": "secret"}
    captured = {}
    dialog.credentials_obtained.connect(lambda credential: captured.setdefault("credential", credential))

    dialog._submit_phone_login()

    assert captured["credential"]["musicid"] == "1"
    assert context.settings.get("credential", None)["musickey"] == "secret"


def test_phone_login_shows_frequency_error_inline(qtbot):
    dialog = QQMusicLoginDialog(_build_plugin_context())
    qtbot.addWidget(dialog)
    dialog._phone_mode_btn.click()
    dialog._phone_input.setText("13000000000")
    dialog._phone_client = Mock()
    dialog._phone_client.send_phone_auth_code.side_effect = ValueError("code=20276")

    dialog._send_phone_auth_code()

    assert "操作过于频繁" in dialog._phone_status_label.text()
```

- [ ] **Step 2: Run the phone-flow tests to verify they fail**

Run: `uv run pytest tests/test_ui/test_qqmusic_login_dialog.py -k "phone_login" -v`

Expected: FAIL because the dialog has no phone-submit helpers or inline status mapping.

- [ ] **Step 3: Implement validation, send-code, and submit helpers**

```python
def _validate_phone_number(self) -> bool:
    phone = str(self._phone_input.text() or "").strip()
    if not re.fullmatch(r"1\d{10}", phone):
        self._set_phone_status(t("qqmusic_phone_invalid"), error=True)
        return False
    return True


def _validate_auth_code(self) -> bool:
    code = str(self._phone_code_input.text() or "").strip()
    if not re.fullmatch(r"\d{4,6}", code):
        self._set_phone_status(t("qqmusic_code_invalid"), error=True)
        return False
    return True
```

```python
def _send_phone_auth_code(self):
    if not self._validate_phone_number():
        return
    try:
        result = self._phone_client.send_phone_auth_code(self._phone_input.text().strip(), 86)
    except Exception as exc:
        self._set_phone_status(self._map_phone_login_error(exc), error=True)
        return
    self._set_phone_status(t("qqmusic_code_sent"), error=False)


def _submit_phone_login(self):
    if not self._validate_phone_number() or not self._validate_auth_code():
        return
    try:
        credential = self._phone_client.phone_authorize(
            self._phone_input.text().strip(),
            self._phone_code_input.text().strip(),
            86,
        )
    except Exception as exc:
        self._set_phone_status(self._map_phone_login_error(exc), error=True)
        return
    self._finish_login_success(credential)
```

- [ ] **Step 4: Extract the shared success path**

```python
def _finish_login_success(self, credential: dict):
    self._context.settings.set("credential", credential)
    nick = credential.get("nick") or credential.get("nickname") or ""
    if not nick:
        service = QQMusicService(credential, http_client=self._context.http)
        verify_result = service.client.verify_login()
        if isinstance(verify_result, dict) and verify_result.get("valid"):
            nick = str(verify_result.get("nick", "") or "")
    if nick:
        self._context.settings.set("nick", nick)
    self.credentials_obtained.emit(credential)
    self.accept()
```

- [ ] **Step 5: Run the phone-flow tests to verify they pass**

Run: `uv run pytest tests/test_ui/test_qqmusic_login_dialog.py -k "phone_login" -v`

Expected: PASS with all phone-login tests green.

- [ ] **Step 6: Commit the phone login behavior**

```bash
git add plugins/builtin/qqmusic/lib/login_dialog.py tests/test_ui/test_qqmusic_login_dialog.py
git commit -m "feat: add qqmusic phone verification login flow"
```

### Task 4: Verify End-To-End Plugin Integration And Regression Coverage

**Files:**
- Modify: `tests/test_ui/test_online_music_view_async.py`
- Modify: `tests/test_ui/test_plugin_settings_tab.py`

- [ ] **Step 1: Add regression tests that phone login reuses the existing success path**

```python
def test_phone_login_success_refreshes_online_view_without_restart():
    view = OnlineMusicView.__new__(OnlineMusicView)
    view._plugin_context = Mock()
    view._config = Mock()
    view._config.get_plugin_setting.return_value = ""
    view._service = Mock()
    view._download_service = Mock()
    view._detail_view = None
    view._update_login_status = Mock()
    view._load_favorites = Mock()
    view._fav_loaded = True

    fresh_service = Mock()
    fresh_service.client.verify_login.return_value = {"valid": True, "nick": "Tester", "uin": 1}
    view._refresh_qqmusic_service = Mock(return_value=fresh_service)

    OnlineMusicView._on_credentials_obtained(view, {"musicid": "1", "musickey": "secret", "login_type": 0})

    view._refresh_qqmusic_service.assert_called_once_with({"musicid": "1", "musickey": "secret", "login_type": 0})
    view._load_favorites.assert_called_once_with()
```

```python
def test_settings_tab_login_dialog_still_updates_status_after_credentials_obtained(qtbot):
    context = _build_plugin_context(PluginSettingsBridgeImpl("qqmusic", Mock()))
    widget = QQMusicSettingsTab(context)
    qtbot.addWidget(widget)
    widget._update_qqmusic_status = Mock()
    dialog = Mock()
    dialog.credentials_obtained = _Signal()

    # assert connect callback and manual signal execution still refresh UI
```

- [ ] **Step 2: Run focused regression tests to verify they fail**

Run: `uv run pytest tests/test_ui/test_online_music_view_async.py tests/test_ui/test_plugin_settings_tab.py -k "phone_login_success_refreshes_online_view_without_restart or credentials_obtained" -v`

Expected: FAIL until the new regression coverage is updated for the phone-login path.

- [ ] **Step 3: Make any minimal test-only adjustments required by the new dialog structure**

```python
# Keep the existing callback wiring:
dialog.credentials_obtained.connect(self._on_credentials_obtained)

# Keep settings tab refresh behavior:
dialog.credentials_obtained.connect(lambda _credential: self._update_qqmusic_status())
```

- [ ] **Step 4: Run the full targeted verification suite**

Run: `uv run pytest tests/test_services/test_qqmusic_phone_login.py tests/test_ui/test_qqmusic_login_dialog.py tests/test_ui/test_online_music_view_async.py tests/test_ui/test_plugin_settings_tab.py tests/test_plugins/test_qqmusic_login_dialog_performance.py -v`

Expected: PASS with all targeted login-related tests green.

- [ ] **Step 5: Run syntax verification**

Run: `uv run python -m py_compile plugins/builtin/qqmusic/lib/qqmusic_client.py plugins/builtin/qqmusic/lib/login_dialog.py tests/test_services/test_qqmusic_phone_login.py tests/test_ui/test_qqmusic_login_dialog.py`

Expected: exit code 0 and no output.

- [ ] **Step 6: Commit the integration and regression work**

```bash
git add tests/test_ui/test_online_music_view_async.py tests/test_ui/test_plugin_settings_tab.py
git commit -m "test: cover qqmusic phone login integration"
```
