from __future__ import annotations

from typing import Protocol

from .context import PluginContext


class HarmonyPlugin(Protocol):
    plugin_id: str

    def register(self, context: PluginContext) -> None:
        ...

    def unregister(self, context: PluginContext) -> None:
        ...
