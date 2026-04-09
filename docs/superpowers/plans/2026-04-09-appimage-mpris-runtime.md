# AppImage MPRIS Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore AppImage MPRIS startup by initializing the D-Bus session bus in `AppRun` and surfacing clearer diagnostics when host Python D-Bus bindings cannot satisfy the frozen runtime.

**Architecture:** Keep the existing MPRIS controller and Linux runtime fallback path, but harden the packaging boundary. `release.sh` should generate an `AppRun` that mirrors `start.sh`'s D-Bus environment setup, while `app/bootstrap.py` should classify host runtime import failures with actionable messages instead of treating all `ImportError` cases as generic missing packages.

**Tech Stack:** Bash, Python 3.12, PyInstaller/AppImage, pytest

---

### Task 1: Add packaging regression tests for AppImage D-Bus setup and clearer diagnostics

**Files:**
- Modify: `tests/test_release_build.py`
- Modify: `tests/test_app/test_plugin_bootstrap.py`

- [ ] **Step 1: Write the failing release packaging test**

```python
def test_release_script_apprun_initializes_dbus_session():
    repo_root = Path(__file__).resolve().parents[1]
    content = (repo_root / "release.sh").read_text(encoding="utf-8")

    assert "DBUS_SESSION_BUS_ADDRESS" in content
    assert "dbus-launch --sh-syntax" in content
    assert "/run/user/$uid/bus" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_release_build.py::test_release_script_apprun_initializes_dbus_session -v`
Expected: FAIL because `release.sh` `AppRun` currently has no D-Bus session initialization.

- [ ] **Step 3: Write the failing bootstrap diagnostic test**

```python
def test_enable_linux_mpris_runtime_reports_host_binding_loading_failure(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(
        bootstrap_module,
        "_discover_linux_python_module_roots",
        lambda: ["/usr/lib/python3/dist-packages"],
    )

    attempts = iter([
        (False, "No module named 'dbus'"),
        (False, "No module named '_dbus_bindings'"),
    ])

    monkeypatch.setattr(
        bootstrap_module,
        "_can_import_linux_mpris_runtime",
        lambda: next(attempts),
    )

    ready, reason = bootstrap_module._ensure_linux_mpris_runtime()

    assert ready is False
    assert "host D-Bus Python bindings" in reason
    assert "_dbus_bindings" in reason
```

- [ ] **Step 4: Run test to verify it fails**

Run: `uv run pytest tests/test_app/test_plugin_bootstrap.py::test_enable_linux_mpris_runtime_reports_host_binding_loading_failure -v`
Expected: FAIL because `_ensure_linux_mpris_runtime()` currently returns the raw import error string.

### Task 2: Update AppImage `AppRun` to initialize D-Bus before launching the frozen binary

**Files:**
- Modify: `release.sh`
- Reference: `start.sh`
- Test: `tests/test_release_build.py`

- [ ] **Step 1: Implement D-Bus session initialization inside the generated `AppRun`**

```bash
check_dbus() {
    [ -n "$DBUS_SESSION_BUS_ADDRESS" ]
}

setup_system_dbus() {
    local uid=$(id -u)
    local bus_path="/run/user/$uid/bus"
    if [ -S "$bus_path" ]; then
        export DBUS_SESSION_BUS_ADDRESS="unix:path=$bus_path"
        return 0
    fi
    return 1
}

setup_dbus_launch() {
    if command -v dbus-launch >/dev/null 2>&1; then
        eval "$(dbus-launch --sh-syntax)"
        export DBUS_SESSION_BUS_ADDRESS
        export DBUS_SESSION_BUS_PID
        return 0
    fi
    return 1
}

init_dbus() {
    check_dbus || setup_system_dbus || setup_dbus_launch || true
}

init_dbus
exec "${HERE}/usr/bin/Harmony" "$@"
```

- [ ] **Step 2: Run release packaging test to verify it passes**

Run: `uv run pytest tests/test_release_build.py::test_release_script_apprun_initializes_dbus_session -v`
Expected: PASS

### Task 3: Clarify frozen-runtime fallback diagnostics for host D-Bus extension failures

**Files:**
- Modify: `app/bootstrap.py`
- Modify: `tests/test_app/test_plugin_bootstrap.py`

- [ ] **Step 1: Normalize host binding failure reasons after fallback**

```python
ready, reason = _can_import_linux_mpris_runtime()
if ready:
    return True, None

if added and reason and "_dbus_bindings" in reason:
    return False, (
        "host D-Bus Python bindings were discovered but could not be loaded "
        f"by the frozen runtime ({reason})"
    )
```

- [ ] **Step 2: Run bootstrap diagnostic tests**

Run: `uv run pytest tests/test_app/test_plugin_bootstrap.py::test_enable_linux_mpris_runtime_reports_missing_modules_when_recovery_fails tests/test_app/test_plugin_bootstrap.py::test_enable_linux_mpris_runtime_reports_host_binding_loading_failure -v`
Expected: PASS

### Task 4: Run focused regression verification

**Files:**
- Test: `tests/test_release_build.py`
- Test: `tests/test_app/test_plugin_bootstrap.py`

- [ ] **Step 1: Run the focused regression suite**

Run: `uv run pytest tests/test_release_build.py tests/test_app/test_plugin_bootstrap.py -v`
Expected: PASS with the new AppImage D-Bus setup and bootstrap diagnostics covered.
