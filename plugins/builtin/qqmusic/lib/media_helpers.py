from __future__ import annotations

from typing import Any, Mapping


def build_album_cover_url(album_mid: str, size: int) -> str | None:
    if not album_mid:
        return None
    return f"https://y.gtimg.cn/music/photo_new/T002R{size}x{size}M000{album_mid}.jpg"


def build_artist_cover_url(singer_mid: str, size: int) -> str | None:
    if not singer_mid:
        return None
    return f"https://y.gtimg.cn/music/photo_new/T001R{size}x{size}M000{singer_mid}.jpg"


def extract_album_mid(detail: Mapping[str, Any] | None) -> str:
    if not isinstance(detail, Mapping):
        return ""
    track = detail.get("track_info", detail.get("data", detail))
    if not isinstance(track, Mapping):
        return ""
    album = track.get("album", {})
    if isinstance(album, Mapping):
        album_mid = album.get("mid") or album.get("albumMid") or album.get("albummid")
        if album_mid:
            return str(album_mid)
    return str(track.get("album_mid") or track.get("albummid") or track.get("albumMid") or "")


def pick_lyric_text(lyric_data: Mapping[str, Any] | None) -> str | None:
    if not isinstance(lyric_data, Mapping):
        return None
    qrc = lyric_data.get("qrc")
    if qrc:
        return str(qrc)
    lyric = lyric_data.get("lyric")
    if lyric:
        return str(lyric)
    return None
