from __future__ import annotations

from collections import defaultdict


class PluginRegistry:
    def __init__(self) -> None:
        self._sidebar_entries: list = []
        self._settings_tabs: list = []
        self._lyrics_sources: list = []
        self._cover_sources: list = []
        self._artist_cover_sources: list = []
        self._online_providers: list = []
        self._owned: dict[str, list[tuple[str, object]]] = defaultdict(list)

    def register_sidebar_entry(self, plugin_id: str, spec: object) -> None:
        self._sidebar_entries.append(spec)
        self._owned[plugin_id].append(("sidebar", spec))

    def register_settings_tab(self, plugin_id: str, spec: object) -> None:
        self._settings_tabs.append(spec)
        self._owned[plugin_id].append(("settings_tab", spec))

    def register_lyrics_source(self, plugin_id: str, source: object) -> None:
        self._lyrics_sources.append(source)
        self._owned[plugin_id].append(("lyrics_source", source))

    def register_cover_source(self, plugin_id: str, source: object) -> None:
        self._cover_sources.append(source)
        self._owned[plugin_id].append(("cover_source", source))

    def register_artist_cover_source(self, plugin_id: str, source: object) -> None:
        self._artist_cover_sources.append(source)
        self._owned[plugin_id].append(("artist_cover_source", source))

    def register_online_provider(self, plugin_id: str, provider: object) -> None:
        self._online_providers.append(provider)
        self._owned[plugin_id].append(("online_provider", provider))

    def unregister_plugin(self, plugin_id: str) -> None:
        owned_ids = {id(value) for _kind, value in self._owned.pop(plugin_id, [])}
        self._sidebar_entries[:] = [item for item in self._sidebar_entries if id(item) not in owned_ids]
        self._settings_tabs[:] = [item for item in self._settings_tabs if id(item) not in owned_ids]
        self._lyrics_sources[:] = [item for item in self._lyrics_sources if id(item) not in owned_ids]
        self._cover_sources[:] = [item for item in self._cover_sources if id(item) not in owned_ids]
        self._artist_cover_sources[:] = [
            item for item in self._artist_cover_sources if id(item) not in owned_ids
        ]
        self._online_providers[:] = [item for item in self._online_providers if id(item) not in owned_ids]

    def sidebar_entries(self) -> list:
        return sorted(self._sidebar_entries, key=lambda item: item.order)

    def settings_tabs(self) -> list:
        return sorted(self._settings_tabs, key=lambda item: item.order)

    def lyrics_sources(self) -> list:
        return list(self._lyrics_sources)

    def cover_sources(self) -> list:
        return list(self._cover_sources)

    def artist_cover_sources(self) -> list:
        return list(self._artist_cover_sources)

    def online_providers(self) -> list:
        return list(self._online_providers)
