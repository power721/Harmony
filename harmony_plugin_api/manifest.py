from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


Capability = Literal[
    "sidebar",
    "settings_tab",
    "lyrics_source",
    "cover",
    "online_music_provider",
]

_ALLOWED_CAPABILITIES = {
    "sidebar",
    "settings_tab",
    "lyrics_source",
    "cover",
    "online_music_provider",
}


class PluginManifestError(ValueError):
    pass


def _require_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise PluginManifestError(f"Manifest field '{key}' must be a string")
    return value


@dataclass(frozen=True)
class PluginManifest:
    id: str
    name: str
    version: str
    api_version: str
    entrypoint: str
    entry_class: str
    capabilities: tuple[str, ...]
    min_app_version: str
    max_app_version: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PluginManifest":
        required = (
            "id",
            "name",
            "version",
            "api_version",
            "entrypoint",
            "entry_class",
            "capabilities",
            "min_app_version",
        )
        missing = [key for key in required if key not in data]
        if missing:
            raise PluginManifestError(f"Missing manifest keys: {', '.join(missing)}")

        capabilities_raw = data["capabilities"]
        if isinstance(capabilities_raw, str) or not isinstance(
            capabilities_raw, (list, tuple)
        ):
            raise PluginManifestError(
                "Manifest field 'capabilities' must be a list/tuple of strings"
            )
        if not all(isinstance(item, str) for item in capabilities_raw):
            raise PluginManifestError(
                "Manifest field 'capabilities' must be a list/tuple of strings"
            )
        capabilities = tuple(capabilities_raw)
        unknown = sorted(set(capabilities) - _ALLOWED_CAPABILITIES)
        if unknown:
            raise PluginManifestError(f"Unknown capabilities: {', '.join(unknown)}")

        max_app_version = data.get("max_app_version")
        if max_app_version is not None and not isinstance(max_app_version, str):
            raise PluginManifestError(
                "Manifest field 'max_app_version' must be a string if provided"
            )

        return cls(
            id=_require_str(data, "id"),
            name=_require_str(data, "name"),
            version=_require_str(data, "version"),
            api_version=_require_str(data, "api_version"),
            entrypoint=_require_str(data, "entrypoint"),
            entry_class=_require_str(data, "entry_class"),
            capabilities=capabilities,
            min_app_version=_require_str(data, "min_app_version"),
            max_app_version=max_app_version,
        )
