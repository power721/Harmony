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

        capabilities = tuple(str(item) for item in data["capabilities"])
        unknown = sorted(set(capabilities) - _ALLOWED_CAPABILITIES)
        if unknown:
            raise PluginManifestError(f"Unknown capabilities: {', '.join(unknown)}")

        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            version=str(data["version"]),
            api_version=str(data["api_version"]),
            entrypoint=str(data["entrypoint"]),
            entry_class=str(data["entry_class"]),
            capabilities=capabilities,
            min_app_version=str(data["min_app_version"]),
            max_app_version=str(data["max_app_version"])
            if data.get("max_app_version")
            else None,
        )
