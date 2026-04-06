from __future__ import annotations

from harmony_plugin_api.media import PluginTrack

from .client import QQMusicPluginClient
from .root_view import QQMusicRootView


class QQMusicOnlineProvider:
    provider_id = "qqmusic"
    display_name = "QQ 音乐"

    def __init__(self, context):
        self._context = context
        self._client = QQMusicPluginClient(context)

    def create_page(self, context, parent=None):
        return QQMusicRootView(context, self, parent)

    def search_tracks(self, keyword: str) -> list[dict]:
        return self._client.search(keyword, limit=20)

    def get_demo_track(self) -> PluginTrack:
        return PluginTrack(
            track_id="demo-mid",
            title="Demo Song",
            artist="Demo Artist",
            album="Demo Album",
        )

    def get_playback_url_info(self, track_id: str, quality: str):
        return {"url": "https://example.com/demo.mp3", "quality": quality, "extension": ".mp3"}
