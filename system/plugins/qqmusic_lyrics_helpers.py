from __future__ import annotations

from harmony_plugin_api.lyrics import PluginLyricsResult


def download_qqmusic_lyrics(song_mid: str) -> str:
    from app.bootstrap import Bootstrap

    sources = Bootstrap.instance().plugin_manager.registry.lyrics_sources()
    for source in sources:
        if getattr(source, "source", None) == "qqmusic" or getattr(source, "name", "").lower() == "qqmusic":
            if hasattr(source, "get_lyrics_by_song_id"):
                return source.get_lyrics_by_song_id(song_mid) or ""
            if hasattr(source, "get_lyrics"):
                return source.get_lyrics(
                    PluginLyricsResult(song_id=song_mid, title="", artist="", source="qqmusic")
                ) or ""
    return ""
