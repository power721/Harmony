from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from harmony_plugin_api.media import PluginPlaybackRequest, PluginTrack


class QQMusicRootView(QWidget):
    def __init__(self, context, provider, parent=None):
        super().__init__(parent)
        self._context = context
        self._provider = provider
        self._status = QLabel(self._build_status_text(), self)
        self._search_input = QLineEdit(self)
        self._search_input.setPlaceholderText("Search QQ Music")
        self._search_btn = QPushButton("Search", self)
        self._search_btn.clicked.connect(self._run_search)
        self._results_list = QListWidget(self)
        layout = QVBoxLayout(self)
        layout.addWidget(self._status)
        search_row = QHBoxLayout()
        search_row.addWidget(self._search_input)
        search_row.addWidget(self._search_btn)
        layout.addLayout(search_row)
        layout.addWidget(self._results_list)

    def _build_status_text(self) -> str:
        nick = self._context.settings.get("nick", "")
        if nick:
            return f"Logged in as {nick}"
        return "Not logged in"

    def _run_search(self):
        keyword = self._search_input.text().strip()
        if not keyword:
            return
        results = self._provider.search_tracks(keyword)
        self._results_list.clear()
        for item in results:
            text = f"{item.get('title', '')} - {item.get('singer', item.get('artist', ''))}"
            row = QListWidgetItem(text)
            row.setData(0x0100, item)
            self._results_list.addItem(row)

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
