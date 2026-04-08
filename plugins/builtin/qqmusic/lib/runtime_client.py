from __future__ import annotations

import json

from .qqmusic_client import QQMusicClient

_shared_client = None


def get_shared_client() -> QQMusicClient:
    global _shared_client
    if _shared_client is None:
        _shared_client = QQMusicClient()
    return _shared_client


def refresh_shared_client() -> QQMusicClient:
    global _shared_client
    _shared_client = QQMusicClient()
    return _shared_client


def get_credential_from_config(config):
    if hasattr(config, "get_plugin_secret"):
        raw = config.get_plugin_secret("qqmusic", "credential", "")
        if raw:
            try:
                return raw if isinstance(raw, dict) else json.loads(raw)
            except Exception:
                return None
    return None


def save_credential_to_config(config, credential: dict) -> None:
    if hasattr(config, "set_plugin_secret"):
        config.set_plugin_secret(
            "qqmusic",
            "credential",
            json.dumps(credential, ensure_ascii=False),
        )
