"""
Typed serialization helpers for settings storage.
"""

import json
from typing import Any

_SETTING_PREFIX = "__harmony_setting__:"


def encode_setting_value(value: Any) -> str:
    """Serialize a setting with explicit type metadata."""
    value_type = "tuple" if isinstance(value, tuple) else type(value).__name__
    payload_value = list(value) if isinstance(value, tuple) else value
    payload = {
        "type": value_type,
        "value": payload_value,
    }
    return _SETTING_PREFIX + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def decode_setting_value(raw_value: Any) -> Any:
    """Deserialize settings written with type metadata and keep legacy compatibility."""
    if not isinstance(raw_value, str):
        return raw_value

    if raw_value.startswith(_SETTING_PREFIX):
        payload = json.loads(raw_value[len(_SETTING_PREFIX):])
        value = payload.get("value")
        if payload.get("type") == "tuple" and isinstance(value, list):
            return tuple(value)
        return value

    try:
        return json.loads(raw_value)
    except (json.JSONDecodeError, TypeError):
        return raw_value
