from __future__ import annotations

from typing import Any

from .media_helpers import build_album_cover_url


def pick_section_cover(items: list[dict[str, Any]]) -> str:
    for item in items:
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("Track"), dict):
            track = item["Track"]
            album = track.get("album", {})
            if isinstance(album, dict):
                cover_url = build_album_cover_url(str(album.get("mid", "")), 300)
                if cover_url:
                    return cover_url
            cover_url = track.get("cover_url") or track.get("cover") or track.get("picurl") or track.get("pic")
            if isinstance(cover_url, dict):
                cover_url = cover_url.get("default_url") or cover_url.get("small_url")
            if cover_url:
                return str(cover_url)
        if isinstance(item.get("Playlist"), dict):
            playlist = item["Playlist"]
            basic = playlist.get("basic", {}) if isinstance(playlist.get("basic"), dict) else {}
            content = playlist.get("content", {}) if isinstance(playlist.get("content"), dict) else {}
            cover_url = (
                basic.get("cover_url")
                or basic.get("cover")
                or content.get("cover_url")
                or content.get("cover")
                or playlist.get("cover_url")
                or playlist.get("cover")
            )
            if isinstance(cover_url, dict):
                cover_url = cover_url.get("default_url") or cover_url.get("small_url")
            if cover_url:
                return str(cover_url)
        cover_url = item.get("cover_url") or item.get("cover") or item.get("picurl") or item.get("pic")
        if isinstance(cover_url, dict):
            cover_url = cover_url.get("default_url") or cover_url.get("small_url")
        if cover_url:
            return str(cover_url)
        album = item.get("album", {})
        if isinstance(album, dict) and album.get("mid"):
            built = build_album_cover_url(str(album.get("mid", "")), 300)
            if built:
                return built
        album_mid = item.get("album_mid")
        if album_mid:
            built = build_album_cover_url(str(album_mid), 300)
            if built:
                return built
    return ""


def build_section(
    *,
    card_id: str,
    title: str,
    entry_type: str,
    items: list[dict[str, Any]],
    include_count: bool = False,
) -> dict[str, Any]:
    section = {
        "id": card_id,
        "title": title,
        "subtitle": f"{len(items)} 项",
        "cover_url": pick_section_cover(items),
        "items": items,
        "entry_type": entry_type,
    }
    if include_count:
        section["count"] = len(items)
    return section
