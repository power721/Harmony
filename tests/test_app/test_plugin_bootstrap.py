from pathlib import Path
from unittest.mock import MagicMock

import app.bootstrap as bootstrap_module


def test_bootstrap_exposes_plugin_manager(monkeypatch):
    fake_state_store = object()
    fake_manager = object()
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
