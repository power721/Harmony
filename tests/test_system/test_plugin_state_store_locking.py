import json
import threading

from system.plugins.state_store import PluginStateStore


def test_set_enabled_serializes_read_modify_write(monkeypatch, tmp_path):
    store = PluginStateStore(tmp_path / "state.json")
    real_write = store._write
    first_write_started = threading.Event()
    allow_first_write = threading.Event()
    write_count = 0

    def controlled_write(payload: dict) -> None:
        nonlocal write_count
        write_count += 1
        if write_count == 1:
            first_write_started.set()
            assert allow_first_write.wait(timeout=1)
        real_write(payload)

    monkeypatch.setattr(store, "_write", controlled_write)

    thread_one = threading.Thread(
        target=store.set_enabled,
        args=("plugin-a", True, "builtin", "1.0.0"),
    )
    thread_two = threading.Thread(
        target=store.set_enabled,
        args=("plugin-b", True, "external", "1.0.0"),
    )

    thread_one.start()
    assert first_write_started.wait(timeout=1)
    thread_two.start()
    allow_first_write.set()

    thread_one.join(timeout=2)
    thread_two.join(timeout=2)

    payload = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert set(payload) == {"plugin-a", "plugin-b"}
