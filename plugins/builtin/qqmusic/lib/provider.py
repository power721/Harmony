from __future__ import annotations

from PySide6.QtWidgets import QLabel


class QQMusicOnlineProvider:
    provider_id = "qqmusic"
    display_name = "QQ 音乐"

    def __init__(self, context):
        self._context = context

    def create_page(self, context, parent=None):
        return QLabel("QQ Music", parent)

    def get_playback_url_info(self, track_id: str, quality: str):
        return None
