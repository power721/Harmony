from __future__ import annotations

from harmony_plugin_api.lyrics import PluginLyricsResult


def download_online_lyrics(song_id: str, provider_id: str) -> str:
    from app.bootstrap import Bootstrap

    normalized = (provider_id or "").strip().lower()
    if not normalized:
        return ""

    sources = Bootstrap.instance().plugin_manager.registry.lyrics_sources()
    for source in sources:
        source_name = getattr(source, "source", None) or getattr(source, "name", "")
        if str(source_name).lower() != normalized:
            continue
        if hasattr(source, "get_lyrics_by_song_id"):
            return source.get_lyrics_by_song_id(song_id) or ""
        if hasattr(source, "get_lyrics"):
            return source.get_lyrics(
                PluginLyricsResult(song_id=song_id, title="", artist="", source=normalized)
            ) or ""
    return ""
