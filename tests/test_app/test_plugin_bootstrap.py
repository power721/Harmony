from pathlib import Path
import logging
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


def test_linux_mpris_runtime_is_ready_when_qtdbus_is_available(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(
        bootstrap_module,
        "_can_import_linux_mpris_runtime",
        lambda: (True, None),
    )

    ready, reason = bootstrap_module._ensure_linux_mpris_runtime()

    assert ready is True
    assert reason is None


def test_linux_mpris_runtime_reports_qtdbus_failure(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(
        bootstrap_module,
        "_can_import_linux_mpris_runtime",
        lambda: (False, "QtDBus session bus unavailable"),
    )

    ready, reason = bootstrap_module._ensure_linux_mpris_runtime()

    assert ready is False
    assert reason == "QtDBus session bus unavailable"


def test_mpris_controller_logs_warning_when_linux_qtdbus_support_is_missing(monkeypatch, caplog):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(
        bootstrap_module,
        "_ensure_linux_mpris_runtime",
        lambda: (False, "QtDBus session bus unavailable"),
    )

    bootstrap = bootstrap_module.Bootstrap(":memory:")

    with caplog.at_level(logging.WARNING, logger="app.bootstrap"):
        controller = bootstrap.mpris_controller

    assert controller is None
    assert "Linux QtDBus runtime unavailable" in caplog.text
    assert "QtDBus session bus unavailable" in caplog.text
