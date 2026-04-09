from __future__ import annotations

import re
from typing import Any, Dict, Optional

_RE_HTML_TAG = re.compile(r"<[^>]+>")


def _parse_album_song(item: Dict) -> Dict:
    song = item.get("songInfo", item)

    name = song.get("title", song.get("name", song.get("songName", "")))
    if name:
        name = _RE_HTML_TAG.sub("", name)

    album_name = song.get("albumName", song.get("albumname", ""))
    if album_name:
        album_name = _RE_HTML_TAG.sub("", album_name)

    singers = song.get("singer", [])
    if isinstance(singers, list):
        singers = [
            {
                "mid": singer.get("mid", ""),
                "name": _RE_HTML_TAG.sub("", singer.get("name", "")),
            }
            if isinstance(singer, dict)
            else singer
            for singer in singers
        ]

    return {
        "mid": song.get("mid", song.get("songMid", "")),
        "id": song.get("id", song.get("songId")),
        "name": name,
        "singer": singers,
        "album": song.get("album", {}),
        "albummid": song.get("albumMid", song.get("albummid", "")),
        "albumname": album_name,
        "interval": song.get("interval", song.get("duration", 0)),
    }


def parse_album_detail(
    raw_data: Dict[str, Any],
    songs_data: Optional[Dict] = None,
) -> Optional[Dict[str, Any]]:
    if not raw_data:
        return None

    basic_info = raw_data.get("basicInfo", {})
    singer_list = raw_data.get("singer", {}).get("singerList", [])
    company_info = raw_data.get("company", {})

    singer_names = ", ".join([s.get("name", "") for s in singer_list]) if singer_list else ""
    singer_mids = [s.get("mid", "") for s in singer_list] if singer_list else []
    album_mid = basic_info.get("albumMid", "")

    result = {
        "mid": album_mid,
        "name": basic_info.get("albumName", ""),
        "singer": singer_names,
        "singer_mid": singer_mids[0] if singer_mids else "",
        "cover_url": f"https://y.gtimg.cn/music/photo_new/T002R300x300M000{album_mid}.jpg" if album_mid else "",
        "publish_date": basic_info.get("publishDate", ""),
        "description": basic_info.get("desc", ""),
        "company": company_info.get("name", ""),
        "genre": basic_info.get("genre", ""),
        "language": basic_info.get("language", ""),
        "album_type": basic_info.get("albumType", ""),
        "songs": [],
        "total": 0,
    }

    if songs_data:
        song_list = songs_data.get("songList", [])
        songs = [_parse_album_song(item) for item in song_list]
        result["songs"] = songs
        result["total"] = songs_data.get("totalNum", len(songs))

    return result
