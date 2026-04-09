from pathlib import Path
import builtins
import logging
import os
import sys
from unittest.mock import MagicMock

import app.bootstrap as bootstrap_module


def test_bootstrap_exposes_plugin_manager(monkeypatch):
    fake_state_store = object()
    fake_manager = MagicMock()
    state_store_ctor = MagicMock(return_value=fake_state_store)
    manager_ctor = MagicMock(return_value=fake_manager)

    monkeypatch.setattr(bootstrap_module, "PluginStateStore", state_store_ctor, raising=False)
    monkeypatch.setattr(bootstrap_module, "PluginManager", manager_ctor, raising=False)

    bootstrap = bootstrap_module.Bootstrap(":memory:")
    bootstrap._config = object()
    bootstrap._event_bus = object()
    bootstrap._http_client = object()

    manager = bootstrap.plugin_manager

    assert manager is fake_manager
    assert bootstrap.plugin_manager is fake_manager

    project_root = Path(bootstrap_module.__file__).resolve().parent.parent
    _, kwargs = manager_ctor.call_args
    assert kwargs["builtin_root"] == project_root / "plugins" / "builtin"
    assert kwargs["external_root"] == project_root / "data" / "plugins" / "external"
    assert kwargs["state_store"] is fake_state_store
    assert hasattr(kwargs["context_factory"], "build")
    fake_manager.load_enabled_plugins.assert_called_once()


def test_bootstrap_resolves_plugin_paths_for_frozen_runtime(monkeypatch, tmp_path):
    fake_state_store = object()
    fake_manager = MagicMock()
    state_store_ctor = MagicMock(return_value=fake_state_store)
    manager_ctor = MagicMock(return_value=fake_manager)
    bundle_root = tmp_path / "bundle"
    user_data_root = tmp_path / "user-data"

    monkeypatch.setattr(bootstrap_module, "PluginStateStore", state_store_ctor, raising=False)
    monkeypatch.setattr(bootstrap_module, "PluginManager", manager_ctor, raising=False)
    monkeypatch.setattr(bootstrap_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(bootstrap_module.sys, "_MEIPASS", str(bundle_root), raising=False)
    monkeypatch.setitem(
        sys.modules,
        "platformdirs",
        MagicMock(user_data_dir=MagicMock(return_value=str(user_data_root))),
    )

    bootstrap = bootstrap_module.Bootstrap(":memory:")
    bootstrap._config = object()
    bootstrap._event_bus = object()
    bootstrap._http_client = object()

    _ = bootstrap.plugin_manager

    _, kwargs = manager_ctor.call_args
    assert kwargs["builtin_root"] == bundle_root / "plugins" / "builtin"
    assert kwargs["external_root"] == user_data_root / "plugins" / "external"
    state_store_ctor.assert_called_once_with(user_data_root / "plugins" / "state.json")


def test_bootstrap_only_loads_plugins_once(monkeypatch):
    fake_state_store = object()
    fake_manager = MagicMock()
    state_store_ctor = MagicMock(return_value=fake_state_store)
    manager_ctor = MagicMock(return_value=fake_manager)

    monkeypatch.setattr(bootstrap_module, "PluginStateStore", state_store_ctor, raising=False)
    monkeypatch.setattr(bootstrap_module, "PluginManager", manager_ctor, raising=False)

    bootstrap = bootstrap_module.Bootstrap(":memory:")
    bootstrap._config = object()
    bootstrap._event_bus = object()
    bootstrap._http_client = object()

    _ = bootstrap.plugin_manager
    _ = bootstrap.plugin_manager

    fake_manager.load_enabled_plugins.assert_called_once()


def test_online_download_service_is_created_with_plugin_agnostic_gateway(monkeypatch):
    fake_download_service = object()
    download_ctor = MagicMock(return_value=fake_download_service)
    monkeypatch.setattr(
        "services.download.online_download_gateway.OnlineDownloadGateway",
        download_ctor,
    )

    bootstrap = bootstrap_module.Bootstrap(":memory:")
    bootstrap._config = object()

    service = bootstrap.online_download_service

    assert service is fake_download_service
    _, kwargs = download_ctor.call_args
    assert kwargs["config_manager"] is bootstrap._config
    assert callable(kwargs["plugin_manager"])
    assert kwargs["event_bus"] is bootstrap.event_bus


def test_bootstrap_no_longer_exposes_qqmusic_client_helpers():
    bootstrap = bootstrap_module.Bootstrap(":memory:")

    assert not hasattr(bootstrap_module.Bootstrap, "qqmusic_client")
    assert not hasattr(bootstrap_module.Bootstrap, "refresh_qqmusic_client")


def test_mpris_controller_logs_warning_when_linux_dbus_support_is_missing(monkeypatch, caplog):
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "dbus" or name.startswith("dbus."):
            raise ImportError("dbus unavailable")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(builtins, "__import__", fake_import)

    bootstrap = bootstrap_module.Bootstrap(":memory:")

    with caplog.at_level(logging.WARNING, logger="app.bootstrap"):
        controller = bootstrap.mpris_controller

    assert controller is None
    assert "MPRIS disabled" in caplog.text
    assert "dbus unavailable" in caplog.text


def test_enable_linux_mpris_runtime_adds_system_module_roots(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(
        bootstrap_module,
        "_discover_linux_python_module_roots",
        lambda: [os.fspath(tmp_path)],
    )
    monkeypatch.setattr(sys, "path", [p for p in sys.path if p != os.fspath(tmp_path)])

    def fake_can_import():
        if os.fspath(tmp_path) in sys.path:
            return True, None
        return False, "gi unavailable"

    monkeypatch.setattr(
        bootstrap_module,
        "_can_import_linux_mpris_runtime",
        fake_can_import,
    )

    ready, reason = bootstrap_module._ensure_linux_mpris_runtime()

    assert ready is True
    assert reason is None
    assert sys.path[0] == os.fspath(tmp_path)


def test_enable_linux_mpris_runtime_reports_missing_modules_when_recovery_fails(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(
        bootstrap_module,
        "_discover_linux_python_module_roots",
        lambda: [],
    )

    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "dbus" or name.startswith("dbus.") or name == "gi" or name.startswith("gi."):
            raise ImportError(f"{name} unavailable")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    ready, reason = bootstrap_module._ensure_linux_mpris_runtime()

    assert ready is False
    assert reason is not None
    assert "unavailable" in reason


def test_enable_linux_mpris_runtime_reports_host_binding_loading_failure(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(
        bootstrap_module,
        "_discover_linux_python_module_roots",
        lambda: ["/usr/lib/python3/dist-packages"],
    )
    monkeypatch.setattr(sys, "path", [p for p in sys.path if p != "/usr/lib/python3/dist-packages"])

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
    assert reason is not None
    assert "host D-Bus Python bindings" in reason
    assert "_dbus_bindings" in reason
