from __future__ import annotations

from typing import Any, Mapping


def _join_artist_names(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(
            entry.get("name", "")
            for entry in value
            if isinstance(entry, Mapping) and entry.get("name")
        )
    if isinstance(value, Mapping):
        return str(value.get("name", ""))
    return str(value or "")


def normalize_song_item(song: Mapping[str, Any]) -> dict[str, Any]:
    singer_name = _join_artist_names(song.get("singer")) or str(song.get("singerName", ""))
    album_info = song.get("album", {})
    if isinstance(album_info, Mapping):
        album_name = album_info.get("name", "") or song.get("albumName", "")
        album_mid = album_info.get("mid", "") or song.get("albumMid", "")
    else:
        album_name = str(album_info or song.get("albumName", ""))
        album_mid = song.get("albumMid", "")
    title = song.get("name", "") or song.get("songname", "") or song.get("title", "")
    return {
        "mid": song.get("mid", "") or song.get("songmid", "") or song.get("songMid", ""),
        "name": title,
        "title": title,
        "artist": singer_name,
        "singer": singer_name,
        "album": album_name,
        "album_mid": album_mid,
        "duration": song.get("interval", 0) or song.get("duration", 0),
    }


def normalize_detail_song(item: Mapping[str, Any]) -> dict[str, Any]:
    singer_name = _join_artist_names(item.get("artist")) or _join_artist_names(item.get("singer"))
    album_value = item.get("album", {})
    if isinstance(album_value, Mapping):
        album_name = album_value.get("name", item.get("albumname", ""))
        album_mid = album_value.get("mid", item.get("album_mid", "")) or item.get("albummid", "")
    else:
        album_name = str(album_value or item.get("albumname", ""))
        album_mid = str(item.get("album_mid", item.get("albummid", "")) or "")
    return {
        "mid": item.get("mid", "") or item.get("songmid", ""),
        "title": item.get("title", item.get("name", "")),
        "artist": singer_name,
        "album": album_name,
        "album_mid": album_mid,
        "duration": item.get("interval", item.get("duration", 0)),
    }


def normalize_top_list_track(item: Any) -> dict[str, Any]:
    if isinstance(item, Mapping):
        normalized = normalize_detail_song(item)
        return {
            "mid": normalized["mid"],
            "title": normalized["title"],
            "artist": normalized["artist"],
            "album": normalized["album"],
            "album_mid": normalized["album_mid"],
            "duration": int(normalized["duration"] or 0),
        }
    return {
        "mid": getattr(item, "mid", ""),
        "title": getattr(item, "title", ""),
        "artist": getattr(item, "singer_name", ""),
        "album": getattr(item, "album_name", ""),
        "album_mid": getattr(getattr(item, "album", None), "mid", ""),
        "duration": getattr(item, "duration", 0),
    }


def normalize_artist_item(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "mid": str(item.get("singerMID", "") or item.get("mid", "")),
        "name": str(item.get("singerName", "") or item.get("name", "")),
        "avatar_url": item.get("singerPic", item.get("avatar", item.get("cover_url", ""))),
        "song_count": int(item.get("songNum", item.get("song_count", item.get("songnum", 0))) or 0),
        "album_count": int(item.get("albumNum", item.get("album_count", item.get("albumnum", 0))) or 0),
        "fan_count": int(item.get("fansNum", item.get("fan_count", item.get("FanNum", 0))) or 0),
    }


def normalize_album_item(item: Mapping[str, Any]) -> dict[str, Any]:
    singer_name = item.get("singer", "")
    if isinstance(singer_name, list):
        singer_name = _join_artist_names(singer_name)
    return {
        "mid": str(item.get("albummid", item.get("albumMID", item.get("mid", "")))),
        "name": item.get("name", item.get("albumname", "")),
        "singer_name": str(singer_name or item.get("singerName", "")),
        "cover_url": item.get("pic", item.get("cover", item.get("cover_url", ""))),
        "song_count": int(item.get("song_num", item.get("song_count", item.get("totalNum", 0))) or 0),
        "publish_date": item.get("publish_date", item.get("pubTime", item.get("publishDate", ""))),
    }


def normalize_playlist_item(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": str(item.get("dissid", item.get("id", ""))),
        "mid": item.get("dissMID", item.get("mid", "")),
        "title": item.get("dissname", item.get("title", "")),
        "creator": item.get("nickname", item.get("creator", "")),
        "cover_url": item.get("logo", item.get("imgurl", item.get("cover_url", item.get("cover", "")))),
        "song_count": item.get("songnum", item.get("song_count", 0)),
        "play_count": item.get("listennum", item.get("play_count", 0)),
    }
