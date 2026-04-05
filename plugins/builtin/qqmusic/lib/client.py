from __future__ import annotations


class QQMusicPluginClient:
    def __init__(self, context):
        self._context = context
        self._credential = context.settings.get("credential", None)

    def get_quality(self) -> str:
        return str(self._context.settings.get("quality", "320"))

    def set_credential(self, credential: dict) -> None:
        self._credential = credential
        self._context.settings.set("credential", credential)

    def clear_credential(self) -> None:
        self._credential = None
        self._context.settings.set("credential", None)
