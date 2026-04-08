from __future__ import annotations


class QQMusicConfigAdapter:
    def __init__(self, settings) -> None:
        self._settings = settings

    def get(self, key: str, default=None):
        return self._settings.get(key, default)

    def set(self, key: str, value) -> None:
        self._settings.set(key, value)

    def get_plugin_setting(self, _plugin_id: str, key: str, default=None):
        return self._settings.get(key, default)

    def set_plugin_setting(self, _plugin_id: str, key: str, value) -> None:
        self._settings.set(key, value)

    def get_plugin_secret(self, _plugin_id: str, key: str, default=""):
        return self._settings.get(key, default)

    def get_online_music_download_dir(self):
        return self._settings.get("online_music_download_dir", "")

    def add_search_history(self, keyword: str) -> None:
        keyword = str(keyword or "").strip()
        if not keyword:
            return
        history = self.get_search_history()
        history = [item for item in history if item != keyword]
        history.insert(0, keyword)
        self._settings.set("search_history", history[:10])

    def get_search_history(self) -> list[str]:
        history = self._settings.get("search_history", []) or []
        if not isinstance(history, list):
            return []
        return [str(item) for item in history if str(item).strip()]

    def clear_search_history(self) -> None:
        self._settings.set("search_history", [])

    def remove_search_history_item(self, keyword: str) -> None:
        history = [item for item in self.get_search_history() if item != keyword]
        self._settings.set("search_history", history)
