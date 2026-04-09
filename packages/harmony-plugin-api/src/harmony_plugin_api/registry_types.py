from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class SidebarEntrySpec:
    plugin_id: str
    entry_id: str
    title: str
    order: int
    icon_name: str | None
    page_factory: Callable[[Any, Any], Any]
    icon_path: str | None = None
    title_provider: Callable[[], str] | None = None


@dataclass(frozen=True)
class SettingsTabSpec:
    plugin_id: str
    tab_id: str
    title: str
    order: int
    widget_factory: Callable[[Any, Any], Any]
    title_provider: Callable[[], str] | None = None
