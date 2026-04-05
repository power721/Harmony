from pathlib import Path
from unittest.mock import MagicMock

import app.bootstrap as bootstrap_module
import services.online as online_module


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

    _, kwargs = manager_ctor.call_args
    assert kwargs["builtin_root"] == Path("plugins/builtin")
    assert kwargs["external_root"] == Path("data/plugins/external")
    assert kwargs["state_store"] is fake_state_store
    assert hasattr(kwargs["context_factory"], "build")
    fake_manager.load_enabled_plugins.assert_called_once()


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


def test_online_download_service_is_created_without_host_online_music_service(monkeypatch):
    fake_download_service = object()
    download_ctor = MagicMock(return_value=fake_download_service)

    monkeypatch.setattr(online_module, "OnlineDownloadService", download_ctor)

    bootstrap = bootstrap_module.Bootstrap(":memory:")
    bootstrap._config = object()

    service = bootstrap.online_download_service

    assert service is fake_download_service
    _, kwargs = download_ctor.call_args
    assert kwargs["config_manager"] is bootstrap._config
    assert kwargs["qqmusic_service"] is None
    assert kwargs["online_music_service"] is None
