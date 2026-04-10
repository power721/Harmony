from __future__ import annotations

import json
import os
import time
from pathlib import Path
from threading import Lock


class PluginStateStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except (json.JSONDecodeError, OSError, ValueError):
            return {}

    def _write(self, payload: dict) -> None:
        tmp_path = self._path.with_name(f"{self._path.name}.tmp")
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        last_error = None
        for attempt in range(3):
            try:
                self._replace_file(tmp_path, self._path)
                return
            except OSError as exc:
                last_error = exc
                if attempt == 2:
                    raise
                time.sleep(0.05)
        if last_error is not None:
            raise last_error

    @staticmethod
    def _replace_file(tmp_path: Path, dest_path: Path) -> None:
        os.replace(tmp_path, dest_path)

    def set_enabled(
        self,
        plugin_id: str,
        enabled: bool,
        source: str,
        version: str,
        load_error: str | None = None,
    ) -> None:
        with self._lock:
            payload = self._read()
            payload[plugin_id] = {
                "enabled": enabled,
                "source": source,
                "version": version,
                "load_error": load_error,
            }
            self._write(payload)

    def get(self, plugin_id: str) -> dict | None:
        with self._lock:
            return self._read().get(plugin_id)
