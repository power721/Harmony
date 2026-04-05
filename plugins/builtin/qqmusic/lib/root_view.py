from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from harmony_plugin_api.media import PluginPlaybackRequest, PluginTrack


class QQMusicRootView(QWidget):
    def __init__(self, context, provider, parent=None):
        super().__init__(parent)
        self._context = context
        self._provider = provider
        self._status = QLabel("QQ Music", self)
        self._play_btn = QPushButton("Play first track", self)
        self._play_btn.clicked.connect(self._play_demo_track)
        layout = QVBoxLayout(self)
        layout.addWidget(self._status)
        layout.addWidget(self._play_btn)

    def _play_demo_track(self):
        track = self._provider.get_demo_track()
        request = PluginPlaybackRequest(
            provider_id="qqmusic",
            track_id=track.track_id,
            title=track.title,
            quality=self._context.settings.get("quality", "320"),
            metadata={
                "title": track.title,
                "artist": track.artist,
                "album": track.album,
            },
        )
        local_path = self._context.services.media.cache_remote_track(request)
        self._context.services.media.add_online_track(request)
        self._status.setText(local_path or "download failed")
