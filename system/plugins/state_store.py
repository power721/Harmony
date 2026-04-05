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
        self._path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def set_enabled(
        self,
        plugin_id: str,
        enabled: bool,
        source: str,
        version: str,
        load_error: str | None = None,
    ) -> None:
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
