# QQMusic Nick Profile Link Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render only the QQ Music `nick` text in the header login status as a clickable profile link that opens `https://y.qq.com/n/ryqq_v2/profile/`.

**Architecture:** Keep the existing `QLabel` in the QQ Music header and switch only the nickname branch to rich-text output. Centralize the login-status text formatting in one helper, add a fixed profile-link handler in `OnlineMusicView`, and preserve the plain-text paths for logged-in-without-nick and logged-out states.

**Tech Stack:** Python 3.12, PySide6 widgets/signals, pytest, pytest-qt

---

## File Map

- Modify: `plugins/builtin/qqmusic/lib/online_music_view.py`
  - Add the fixed profile URL constant and Qt imports needed for URL opening.
  - Configure the existing `_login_status_label` for rich-text link interaction in `_create_header()`.
  - Add one helper that formats login status text with an escaped anchor when `nick` exists.
  - Add one helper that opens the fixed QQ Music profile URL.
  - Reuse the formatting helper in both `_update_login_status()` and `_refresh_login_status()`.
- Modify: `tests/test_ui/test_online_music_view_async.py`
  - Add focused tests for rich-text label output in `_update_login_status()` and `_refresh_login_status()`.
  - Add a focused test for the fixed-profile URL opener.

### Task 1: Lock the rich-text nickname rendering with tests and minimal implementation

**Files:**
- Modify: `tests/test_ui/test_online_music_view_async.py`
- Modify: `plugins/builtin/qqmusic/lib/online_music_view.py`
- Test: `tests/test_ui/test_online_music_view_async.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_update_login_status_renders_nick_as_profile_link():
    view = OnlineMusicView.__new__(OnlineMusicView)
    view._service = Mock()
    view._service._has_qqmusic_credential.return_value = True
    view._refresh_qqmusic_service = Mock()
    view._config = Mock()
    view._config.get_plugin_setting.return_value = 'A&B<Nick>'
    view._login_status_label = Mock()
    view._login_btn = Mock()
    view._recommend_section = Mock()
    view._load_recommendations = Mock()

    OnlineMusicView._update_login_status(view)

    view._login_status_label.setText.assert_called_once_with(
        'Logged in as <a href="https://y.qq.com/n/ryqq_v2/profile/">A&amp;B&lt;Nick&gt;</a>'
    )


def test_refresh_login_status_renders_nick_as_profile_link():
    view = OnlineMusicView.__new__(OnlineMusicView)
    view._service = Mock()
    view._service._has_qqmusic_credential.return_value = True
    view._config = Mock()
    view._config.get_plugin_setting.return_value = "Tester"
    view._login_status_label = Mock()
    view._login_btn = Mock()

    OnlineMusicView._refresh_login_status(view)

    view._login_status_label.setText.assert_called_once_with(
        'Logged in as <a href="https://y.qq.com/n/ryqq_v2/profile/">Tester</a>'
    )
```

Notes:

- Keep `plugin_i18n.set_language("en")` at the start of each test or use `plugin_i18n.t("qqmusic_logged_in_as")` in the expected string so the assertion is locale-stable.
- Leave the existing empty-nick behavior test in place; this task only adds positive coverage for the linked-nick branch.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_ui/test_online_music_view_async.py -k "update_login_status or refresh_login_status" -vv`

Expected:

- `test_update_login_status_renders_nick_as_profile_link` fails because `_update_login_status()` still writes plain text like `Logged in as A&B<Nick>`.
- `test_refresh_login_status_renders_nick_as_profile_link` fails for the same reason.

- [ ] **Step 3: Write the minimal implementation**

```python
import html
from PySide6.QtCore import Qt, Signal, QThread, QTimer, QStringListModel, QPoint, QEvent, QUrl
from PySide6.QtGui import QColor, QBrush, QDesktopServices


class OnlineMusicView(QWidget):
    _QQMUSIC_PROFILE_URL = "https://y.qq.com/n/ryqq_v2/profile/"

    def _format_login_status_text(self, nick: str) -> str:
        if nick:
            safe_nick = html.escape(str(nick))
            return (
                f'{t("qqmusic_logged_in_as")} '
                f'<a href="{self._QQMUSIC_PROFILE_URL}">{safe_nick}</a>'
            )
        return t("qqmusic_logged_in")

    def _update_login_status(self):
        has_credential = self._service._has_qqmusic_credential()
        if has_credential:
            self._refresh_qqmusic_service()
            if self._config and hasattr(self._config, "get_plugin_setting"):
                nick = self._config.get_plugin_setting("qqmusic", "nick", "")
            else:
                nick = ""
            self._login_status_label.setText(self._format_login_status_text(nick))
            self._login_btn.setText(t("logout"))
            if hasattr(self, "_recommend_section"):
                self._load_recommendations()
        else:
            self._login_status_label.setText(t("qqmusic_not_logged_in"))
            self._login_btn.setText(t("login"))

    def _refresh_login_status(self):
        has_credential = self._service._has_qqmusic_credential()
        if has_credential:
            if self._config and hasattr(self._config, "get_plugin_setting"):
                nick = self._config.get_plugin_setting("qqmusic", "nick", "")
            else:
                nick = ""
            self._login_status_label.setText(self._format_login_status_text(nick))
            self._login_btn.setText(t("logout"))
        else:
            self._login_status_label.setText(t("qqmusic_not_logged_in"))
            self._login_btn.setText(t("login"))
```

Implementation notes:

- Keep the helper name and constant exactly the same everywhere in this plan to avoid type drift.
- Do not change the empty-nick path to rich text; it should stay on the existing generic logged-in text.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_ui/test_online_music_view_async.py -k "update_login_status or refresh_login_status" -vv`

Expected:

- PASS for the two new linked-nick tests.
- PASS for the existing `test_update_login_status_prefers_plugin_namespaced_nick`.

- [ ] **Step 5: Commit**

```bash
git add tests/test_ui/test_online_music_view_async.py plugins/builtin/qqmusic/lib/online_music_view.py docs/superpowers/specs/2026-04-09-qqmusic-nick-profile-link-design.md docs/superpowers/plans/2026-04-09-qqmusic-nick-profile-link.md
git commit -m "添加QQ昵称资料链接"
```

### Task 2: Wire the label link click to the fixed QQ Music profile URL

**Files:**
- Modify: `tests/test_ui/test_online_music_view_async.py`
- Modify: `plugins/builtin/qqmusic/lib/online_music_view.py`
- Test: `tests/test_ui/test_online_music_view_async.py`

- [ ] **Step 1: Write the failing test**

```python
def test_open_qqmusic_profile_link_uses_fixed_profile_url(monkeypatch):
    opened_urls = []

    def _fake_open_url(url):
        opened_urls.append(url.toString())
        return True

    monkeypatch.setattr(online_music_view.QDesktopServices, "openUrl", _fake_open_url)
    view = OnlineMusicView.__new__(OnlineMusicView)

    OnlineMusicView._open_qqmusic_profile_link(view, "https://ignored.example/")

    assert opened_urls == ["https://y.qq.com/n/ryqq_v2/profile/"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_ui/test_online_music_view_async.py -k "profile_link_uses_fixed_profile_url" -vv`

Expected:

- FAIL with `AttributeError` because `_open_qqmusic_profile_link()` does not exist yet.

- [ ] **Step 3: Write the minimal implementation**

```python
def _create_header(self) -> QWidget:
    widget = QWidget()
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)

    self._online_music_title = QLabel(t("qqmusic_page_title"))
    layout.addWidget(self._online_music_title)

    layout.addStretch()

    self._login_status_label = QLabel()
    self._login_status_label.setTextFormat(Qt.RichText)
    self._login_status_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
    self._login_status_label.setOpenExternalLinks(False)
    self._login_status_label.linkActivated.connect(self._open_qqmusic_profile_link)
    layout.addWidget(self._login_status_label)

    self._login_btn = QPushButton()
    self._login_btn.setCursor(Qt.PointingHandCursor)
    self._login_btn.clicked.connect(self._on_login_clicked)
    layout.addWidget(self._login_btn)

    self._update_login_status()
    return widget


def _open_qqmusic_profile_link(self, _: str) -> None:
    QDesktopServices.openUrl(QUrl(self._QQMUSIC_PROFILE_URL))
```

Implementation notes:

- Keep `setOpenExternalLinks(False)` so the view controls the destination instead of trusting the emitted href.
- Ignore the activated-link argument and always open the fixed profile URL from the class constant.

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_ui/test_online_music_view_async.py -k "profile_link_uses_fixed_profile_url" -vv`

Expected:

- PASS, with `opened_urls` containing only `https://y.qq.com/n/ryqq_v2/profile/`.

- [ ] **Step 5: Run focused regression coverage**

Run: `uv run pytest tests/test_ui/test_online_music_view_async.py -k "login_status or profile_link" -vv`

Expected:

- PASS for the two rich-text rendering tests.
- PASS for the fixed-profile URL opener test.
- PASS for the existing namespaced-nick regression test.

- [ ] **Step 6: Commit**

```bash
git add tests/test_ui/test_online_music_view_async.py plugins/builtin/qqmusic/lib/online_music_view.py docs/superpowers/specs/2026-04-09-qqmusic-nick-profile-link-design.md docs/superpowers/plans/2026-04-09-qqmusic-nick-profile-link.md
git commit -m "接入QQ昵称资料页跳转"
```

### Task 3: Final verification before handoff

**Files:**
- Modify: `plugins/builtin/qqmusic/lib/online_music_view.py`
- Modify: `tests/test_ui/test_online_music_view_async.py`
- Test: `tests/test_ui/test_online_music_view_async.py`

- [ ] **Step 1: Run the complete targeted test file**

Run: `uv run pytest tests/test_ui/test_online_music_view_async.py -vv`

Expected:

- PASS for the new nickname-link coverage.
- PASS for unrelated async coordination tests in the same file, proving the refactor did not disturb surrounding behavior.

- [ ] **Step 2: Run lint on the touched files**

Run: `uv run ruff check plugins/builtin/qqmusic/lib/online_music_view.py tests/test_ui/test_online_music_view_async.py`

Expected:

- PASS with no import-order, unused-import, or formatting-related issues from the new helper and Qt imports.

- [ ] **Step 3: Commit**

```bash
git add tests/test_ui/test_online_music_view_async.py plugins/builtin/qqmusic/lib/online_music_view.py docs/superpowers/specs/2026-04-09-qqmusic-nick-profile-link-design.md docs/superpowers/plans/2026-04-09-qqmusic-nick-profile-link.md
git commit -m "完成QQ昵称链接交互"
```
