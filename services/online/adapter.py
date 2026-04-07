"""
Online music API adapter.
Unifies response formats from different API sources.
"""

import re
import logging
from typing import Dict, List, Any, Optional

from domain.online_music import (
    OnlineTrack, OnlineArtist, OnlineAlbum, OnlinePlaylist,
    AlbumInfo, OnlineSinger, SearchResult, SearchType
)

logger = logging.getLogger(__name__)

# Pre-compiled regex pattern for HTML tag stripping
_RE_HTML_TAG = re.compile(r'<[^>]+>')


class ApiSource:
    """API source constants."""

    YGKING = "ygking"  # api.ygking.top
    QQMUSIC = "qqmusic"  # QQ Music local API


class OnlineMusicAdapter:
    """
    Adapter to unify API response formats.

    Supports:
    - api.ygking.top format
    - QQ Music local API format
    """

    @staticmethod
    def normalize_search_result(
        source: str,
        raw_data: Dict[str, Any],
        search_type: str = "song",
        keyword: str = "",
        page: int = 1,
        page_size: int = 20
    ) -> SearchResult:
        """
        Normalize search result from different API sources.

        Args:
            source: API source (ApiSource.YGKING or ApiSource.QQMUSIC)
            raw_data: Raw API response data
            search_type: Search type (song/singer/album/playlist)
            keyword: Search keyword
            page: Page number
            page_size: Page size

        Returns:
            Normalized SearchResult object
        """
        if source == ApiSource.YGKING:
            return OnlineMusicAdapter._normalize_ygking(
                raw_data, search_type, keyword, page, page_size
            )
        elif source == ApiSource.QQMUSIC:
            return OnlineMusicAdapter._normalize_qqmusic(
                raw_data, search_type, keyword, page, page_size
            )
        else:
            logger.warning(f"Unknown API source: {source}")
            return SearchResult(
                keyword=keyword,
                search_type=search_type,
                page=page,
                page_size=page_size
            )

    @staticmethod
    def _normalize_ygking(
        raw_data: Dict[str, Any],
        search_type: str,
        keyword: str,
        page: int,
        page_size: int
    ) -> SearchResult:
        """Normalize api.ygking.top response format."""
        result = SearchResult(
            keyword=keyword,
            search_type=search_type,
            page=page,
            page_size=page_size
        )

        if raw_data.get("code") != 0:
            logger.error(f"YGKing API error: {raw_data.get('code')}")
            return result

        data = raw_data.get("data", {})
        result.total = data.get("total", 0)
        items = data.get("list", [])

        if search_type == SearchType.SONG:
            result.tracks = OnlineMusicAdapter._parse_ygking_tracks(items)
        elif search_type == SearchType.SINGER:
            result.artists = OnlineMusicAdapter._parse_ygking_artists(items)
        elif search_type == SearchType.ALBUM:
            result.albums = OnlineMusicAdapter._parse_ygking_albums(items)
        elif search_type == SearchType.PLAYLIST:
            result.playlists = OnlineMusicAdapter._parse_ygking_playlists(items)

        return result

    @staticmethod
    def _parse_ygking_tracks(items: List[Dict]) -> List[OnlineTrack]:
        """Parse tracks from YGKing API format."""
        tracks = []
        for item in items:
            # Parse singers - handle different formats
            singers = []
            singer_data = item.get("singer", [])
            if isinstance(singer_data, list):
                for s in singer_data:
                    if isinstance(s, dict):
                        name = s.get("name", "")
                        # Strip HTML tags
                        if name:
                            name = _RE_HTML_TAG.sub('', name)
                        singers.append(OnlineSinger(
                            mid=s.get("mid", ""),
                            name=name
                        ))
                    elif isinstance(s, str):
                        # Strip HTML tags
                        name = _RE_HTML_TAG.sub('', s)
                        singers.append(OnlineSinger(mid="", name=name))
            elif isinstance(singer_data, dict):
                name = singer_data.get("name", "")
                if name:
                    name = _RE_HTML_TAG.sub('', name)
                singers.append(OnlineSinger(
                    mid=singer_data.get("mid", ""),
                    name=name
                ))
            elif isinstance(singer_data, str):
                name = _RE_HTML_TAG.sub('', singer_data)
                singers.append(OnlineSinger(mid="", name=name))

            # Parse album - handle different formats
            album_data = item.get("album")
            if isinstance(album_data, dict):
                album_name = album_data.get("name", album_data.get("albumname", ""))
                if album_name:
                    album_name = _RE_HTML_TAG.sub('', album_name)
                album = AlbumInfo(
                    mid=album_data.get("mid", album_data.get("albummid", "")),
                    name=album_name
                )
            elif isinstance(album_data, str):
                album_name = _RE_HTML_TAG.sub('', album_data)
                album = AlbumInfo(mid="", name=album_name)
            else:
                album_name = item.get("albumname", item.get("albumName", ""))
                if album_name:
                    album_name = _RE_HTML_TAG.sub('', album_name)
                album = AlbumInfo(
                    mid=item.get("albummid", item.get("albumMid", "")),
                    name=album_name
                )

            # Parse pay info
            pay_info = item.get("pay", {}) or {}
            pay_play = pay_info.get("pay_play", 0) if isinstance(pay_info, dict) else 0

            # Get song mid - try multiple field names
            mid = item.get("mid", item.get("songmid", item.get("songMid", "")))

            # Get song id
            song_id = item.get("id", item.get("songid", item.get("songId")))

            # Get title - try multiple field names
            title = item.get("title", item.get("name", item.get("songname", item.get("songName", ""))))
            if title:
                title = _RE_HTML_TAG.sub('', title)

            track = OnlineTrack(
                mid=mid,
                id=song_id,
                title=title,
                singer=singers,
                album=album,
                duration=item.get("interval", item.get("duration", 0)),
                pay_play=pay_play
            )
            tracks.append(track)

        return tracks

    @staticmethod
    def _parse_ygking_artists(items: List[Dict]) -> List[OnlineArtist]:
        """Parse artists from YGKing API format."""
        artists = []
        for item in items:
            # Strip HTML tags from name
            name = item.get("singerName", item.get("name", ""))
            if name:
                name = _RE_HTML_TAG.sub('', name)

            artist = OnlineArtist(
                mid=item.get("singerMID", item.get("mid", "")),
                name=name,
                avatar_url=item.get("singerPic", item.get("avatar", "")),
                song_count=item.get("songNum", item.get("song_count", 0)),
                album_count=item.get("albumNum", item.get("album_count", 0))
            )
            artists.append(artist)
        return artists

    @staticmethod
    def _parse_ygking_albums(items: List[Dict]) -> List[OnlineAlbum]:
        """Parse albums from YGKing API format."""
        albums = []
        for item in items:
            # Extract singer info from singer_list
            singer_list = item.get("singer_list", [])
            if singer_list and isinstance(singer_list, list):
                singer_mid = singer_list[0].get("mid", "")
                singer_name = singer_list[0].get("name", "")
                # Strip HTML tags
                if singer_name:
                    singer_name = _RE_HTML_TAG.sub('', singer_name)
            else:
                singer_mid = item.get("singer_id", "")
                singer_name = item.get("singer", "")
                # Strip HTML tags
                if singer_name:
                    singer_name = _RE_HTML_TAG.sub('', singer_name)

            # Strip HTML tags from album name
            album_name = item.get("name", "")
            if album_name:
                album_name = _RE_HTML_TAG.sub('', album_name)

            album = OnlineAlbum(
                mid=item.get("albummid", item.get("mid", "")),
                name=album_name,
                singer_mid=singer_mid,
                singer_name=singer_name,
                cover_url=item.get("pic", item.get("cover", "")),
                song_count=item.get("song_num", item.get("song_count", 0)),
                publish_date=item.get("publish_date", "")
            )
            albums.append(album)
        return albums

    @staticmethod
    def _parse_ygking_playlists(items: List[Dict]) -> List[OnlinePlaylist]:
        """Parse playlists from YGKing API format."""
        playlists = []
        for item in items:
            # Strip HTML tags from title
            title = item.get("dissname", item.get("title", ""))
            if title:
                title = _RE_HTML_TAG.sub('', title)

            playlist = OnlinePlaylist(
                id=str(item.get("dissid", item.get("id", ""))),
                mid=item.get("dissMID", item.get("mid", "")),
                title=title,
                creator=item.get("nickname", item.get("creator", "")),
                cover_url=item.get("logo", item.get("cover", "")),
                song_count=item.get("songnum", item.get("song_count", 0)),
                play_count=item.get("listennum", item.get("play_count", 0))
            )
            playlists.append(playlist)
        return playlists

    @staticmethod
    def _parse_ygking_top_songs(items: List[Dict]) -> List[OnlineTrack]:
        """Parse top list songs from YGKing API format."""
        tracks = []
        for item in items:
            # YGKing top songs format: singerName, albumMid, songId
            singers = []
            singer_name = item.get("singerName", "")
            if singer_name:
                singer_name = _RE_HTML_TAG.sub('', singer_name)
                singers.append(OnlineSinger(
                    mid=item.get("singerMid", ""),
                    name=singer_name
                ))

            # Album info - strip HTML tags
            album_name = item.get("albumName", "")
            if album_name:
                album_name = _RE_HTML_TAG.sub('', album_name)
            album = AlbumInfo(
                mid=item.get("albumMid", ""),
                name=album_name
            )

            # Title - strip HTML tags
            title = item.get("title", "")
            if title:
                title = _RE_HTML_TAG.sub('', title)

            track = OnlineTrack(
                mid=item.get("songMid", ""),
                id=item.get("songId"),
                title=title,
                singer=singers,
                album=album,
                duration=item.get("interval", 0)
            )
            tracks.append(track)

        return tracks

    @staticmethod
    def _parse_ygking_song_info_list(items: List[Dict]) -> List[OnlineTrack]:
        """Parse songInfoList from YGKing API (has full album and duration info)."""
        tracks = []
        for item in items:
            # Singer info - array of objects
            singers = []
            singer_list = item.get("singer", [])
            if isinstance(singer_list, list):
                singers.extend(OnlineSinger(
                        mid=s.get("mid", ""),
                        name=s.get("name", "")
                    ) for s in singer_list)

            # Album info
            album_data = item.get("album", {})
            album = AlbumInfo(
                mid=album_data.get("mid", "") if isinstance(album_data, dict) else "",
                name=album_data.get("name", "") if isinstance(album_data, dict) else ""
            )

            track = OnlineTrack(
                mid=item.get("mid", ""),
                id=item.get("id"),
                title=item.get("title", "") or item.get("name", ""),
                singer=singers,
                album=album,
                duration=item.get("interval", 0)
            )
            tracks.append(track)

        return tracks

    @staticmethod
    def _normalize_qqmusic(
        raw_data: Dict[str, Any],
        search_type: str,
        keyword: str,
        page: int,
        page_size: int
    ) -> SearchResult:
        """Normalize QQ Music local API response format."""
        result = SearchResult(
            keyword=keyword,
            search_type=search_type,
            page=page,
            page_size=page_size
        )

        # QQ Music API returns empty dict on error
        if not raw_data:
            return result

        # Get total count
        result.total = raw_data.get("meta", {}).get("sum", 0)

        body = raw_data.get("body", {})
        type_keys = {
            SearchType.SONG: ("item_song", "song"),
            SearchType.SINGER: ("item_singer", "singer"),
            SearchType.ALBUM: ("item_album", "album"),
            SearchType.PLAYLIST: ("item_songlist", "songlist", "playlist"),
        }

        items: list[dict] = []
        for key in type_keys.get(search_type, ("item_song", "song")):
            payload = body.get(key, [])
            if isinstance(payload, list) and payload:
                items = payload
                break
            if isinstance(payload, dict):
                for nested_key in ("list", "itemlist", "items", "data"):
                    nested_payload = payload.get(nested_key, [])
                    if isinstance(nested_payload, list) and nested_payload:
                        items = nested_payload
                        break
                if items:
                    break

        if search_type == SearchType.SONG:
            result.tracks = OnlineMusicAdapter._parse_qqmusic_tracks(items)
        elif search_type == SearchType.SINGER:
            result.artists = OnlineMusicAdapter._parse_qqmusic_artists(items)
        elif search_type == SearchType.ALBUM:
            result.albums = OnlineMusicAdapter._parse_qqmusic_albums(items)
        elif search_type == SearchType.PLAYLIST:
            result.playlists = OnlineMusicAdapter._parse_qqmusic_playlists(items)

        return result

    @staticmethod
    def _parse_qqmusic_tracks(items: List[Dict]) -> List[OnlineTrack]:
        """Parse tracks from QQ Music API format."""
        tracks = []
        for item in items:
            # Parse singers - can be dict, list, or string
            singers = []
            singer_data = item.get("singer", [])
            if isinstance(singer_data, str):
                # Singer is just a name string
                name = _RE_HTML_TAG.sub('', singer_data) if singer_data else ""
                singers.append(OnlineSinger(mid="", name=name))
            elif isinstance(singer_data, list):
                for s in singer_data:
                    if isinstance(s, dict):
                        name = s.get("name", "")
                        if name:
                            name = _RE_HTML_TAG.sub('', name)
                        singers.append(OnlineSinger(
                            mid=s.get("mid", ""),
                            name=name
                        ))
                    elif isinstance(s, str):
                        name = _RE_HTML_TAG.sub('', s) if s else ""
                        singers.append(OnlineSinger(mid="", name=name))
            elif isinstance(singer_data, dict):
                name = singer_data.get("name", "")
                if name:
                    name = _RE_HTML_TAG.sub('', name)
                singers.append(OnlineSinger(
                    mid=singer_data.get("mid", ""),
                    name=name
                ))

            # Parse album - can be dict or string
            album_data = item.get("album")
            if isinstance(album_data, str):
                album_name = _RE_HTML_TAG.sub('', album_data) if album_data else ""
                album_mid = item.get("album_mid", item.get("albummid", ""))
                album = AlbumInfo(mid=album_mid, name=album_name)
            elif isinstance(album_data, dict):
                album_name = album_data.get("name", "")
                if album_name:
                    album_name = _RE_HTML_TAG.sub('', album_name)
                album = AlbumInfo(
                    mid=album_data.get("mid", ""),
                    name=album_name
                )
            else:
                album_name = item.get("albumname", "")
                if album_name:
                    album_name = _RE_HTML_TAG.sub('', album_name)
                album = AlbumInfo(
                    mid=item.get("albummid", ""),
                    name=album_name
                )

            # Get title and strip HTML tags
            title = item.get("songname", item.get("title", ""))
            if title:
                title = _RE_HTML_TAG.sub('', title)

            track = OnlineTrack(
                mid=item.get("songmid", item.get("mid", "")),
                id=item.get("songid", item.get("id")),
                title=title,
                singer=singers,
                album=album,
                duration=item.get("interval", item.get("duration", 0))
            )
            tracks.append(track)

        return tracks

    @staticmethod
    def _parse_qqmusic_artists(items: List[Dict]) -> List[OnlineArtist]:
        """Parse artists from QQ Music API format."""
        artists = []
        for item in items:
            mid = item.get("singerMID", item.get("mid", ""))
            avatar_url = (
                item.get("singerPic")
                or item.get("avatar")
                or item.get("cover")
                or item.get("cover_url")
                or item.get("pic")
                or ""
            )
            if not avatar_url and mid:
                avatar_url = f"https://y.gtimg.cn/music/photo_new/T001R300x300M000{mid}.jpg"
            artist = OnlineArtist(
                mid=mid,
                name=item.get("singerName", item.get("name", "")),
                avatar_url=avatar_url,
                song_count=item.get("songNum", item.get("song_count", item.get("songnum", 0))),
                album_count=item.get("albumNum", item.get("album_count", item.get("albumnum", 0))),
                fan_count=item.get("fan_count", item.get("FanNum", 0)),
            )
            artists.append(artist)
        return artists

    @staticmethod
    def _parse_qqmusic_albums(items: List[Dict]) -> List[OnlineAlbum]:
        """Parse albums from QQ Music API format."""
        albums = []
        for item in items:
            # Extract singer info from singer_list
            singer_list = item.get("singer_list", [])
            if singer_list and isinstance(singer_list, list):
                singer_mid = singer_list[0].get("mid", "")
                singer_name = singer_list[0].get("name", "")
            else:
                singer_mid = ""
                singer_name = item.get("singer", "")

            # Strip HTML tags from album name
            album_name = item.get("name", "")
            if album_name:
                album_name = _RE_HTML_TAG.sub('', album_name)

            # QQ Music API uses different field names
            album = OnlineAlbum(
                mid=item.get("albummid", ""),
                name=album_name,
                singer_mid=singer_mid,
                singer_name=singer_name,
                cover_url=item.get("pic", ""),
                song_count=item.get("song_num", 0),
                publish_date=item.get("publish_date", "")
            )
            albums.append(album)
        return albums

    @staticmethod
    def _parse_qqmusic_playlists(items: List[Dict]) -> List[OnlinePlaylist]:
        """Parse playlists from QQ Music API format."""
        playlists = []
        for item in items:
            # Clean HTML tags from title
            dissname = item.get("dissname", "")
            title = _RE_HTML_TAG.sub('', dissname) if dissname else ""

            # Get creator nickname
            creator = item.get("nickname", "")

            playlist = OnlinePlaylist(
                id=str(item.get("dissid", "")),
                mid=item.get("dissMID", item.get("mid", "")),
                title=title,
                creator=creator,
                cover_url=item.get("logo", ""),
                song_count=item.get("songnum", 0),
                play_count=item.get("listennum", 0)
            )
            playlists.append(playlist)
        return playlists

    # ========== Detail parsing methods ==========

    @staticmethod
    def parse_album_detail(raw_data: Dict[str, Any], songs_data: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """
        Parse album detail from QQ Music API response.

        Args:
            raw_data: Raw album basic info response
            songs_data: Raw album songs response (optional)

        Returns:
            Normalized album detail dictionary
        """
        if not raw_data:
            return None

        # Parse basic info
        basic_info = raw_data.get('basicInfo', {})
        singer_list = raw_data.get('singer', {}).get('singerList', [])
        company_info = raw_data.get('company', {})

        # Get singer names
        singer_names = ', '.join([s.get('name', '') for s in singer_list]) if singer_list else ''
        singer_mids = [s.get('mid', '') for s in singer_list] if singer_list else []

        # Build album detail
        album_mid = basic_info.get('albumMid', '')

        result = {
            'mid': album_mid,
            'name': basic_info.get('albumName', ''),
            'singer': singer_names,
            'singer_mid': singer_mids[0] if singer_mids else '',
            'cover_url': f"https://y.gtimg.cn/music/photo_new/T002R300x300M000{album_mid}.jpg" if album_mid else '',
            'publish_date': basic_info.get('publishDate', ''),
            'description': basic_info.get('desc', ''),
            'company': company_info.get('name', ''),
            'genre': basic_info.get('genre', ''),
            'language': basic_info.get('language', ''),
            'album_type': basic_info.get('albumType', ''),
            'songs': [],
            'total': 0,
        }

        # Parse songs if provided
        if songs_data:
            song_list = songs_data.get('songList', [])
            songs = [OnlineMusicAdapter._parse_album_song(item) for item in song_list]
            result['songs'] = songs
            result['total'] = songs_data.get('totalNum', len(songs))

        return result

    @staticmethod
    def _parse_album_song(item: Dict) -> Dict:
        """Parse a single song from album song list."""
        song = item.get('songInfo', item)

        # Strip HTML tags from name
        name = song.get('title', song.get('name', song.get('songName', '')))
        if name:
            name = _RE_HTML_TAG.sub('', name)

        # Strip HTML tags from album name
        album_name = song.get('albumName', song.get('albumname', ''))
        if album_name:
            album_name = _RE_HTML_TAG.sub('', album_name)

        # Strip HTML tags from singer names
        singers = song.get('singer', [])
        if isinstance(singers, list):
            singers = [
                {'mid': s.get('mid', ''), 'name': _RE_HTML_TAG.sub('', s.get('name', ''))} if isinstance(s, dict) else s
                for s in singers
            ]

        return {
            'mid': song.get('mid', song.get('songMid', '')),
            'id': song.get('id', song.get('songId')),
            'name': name,
            'singer': singers,
            'album': song.get('album', {}),
            'albummid': song.get('albumMid', song.get('albummid', '')),
            'albumname': album_name,
            'interval': song.get('interval', song.get('duration', 0)),
        }

    @staticmethod
    def parse_artist_detail(raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse artist detail from QQ Music API response.

        Args:
            raw_data: Raw artist info response

        Returns:
            Normalized artist detail dictionary
        """
        if not raw_data:
            return None

        singer_list = raw_data.get('singer_list', [])
        if not singer_list:
            return None

        singer_data = singer_list[0]
        basic_info = singer_data.get('basic_info', {})
        ex_info = singer_data.get('ex_info', {})
        pic_info = singer_data.get('pic', {})

        # Get avatar URL
        avatar = pic_info.get('pic') or pic_info.get('big') or pic_info.get('big_black') or ''
        singer_mid = basic_info.get('singer_mid', '')
        has_photo = basic_info.get('has_photo', 0)

        if not avatar and singer_mid and has_photo:
            avatar = f"http://y.gtimg.cn/music/photo_new/T001R300x300M000{singer_mid}_{has_photo}.jpg"

        return {
            'mid': singer_mid,
            'name': basic_info.get('name', ''),
            'avatar': avatar,
            'description': ex_info.get('desc', ''),
            'song_count': basic_info.get('song_total', 0),
            'album_count': basic_info.get('album_total', 0),
        }

    @staticmethod
    def parse_playlist_detail(raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse playlist detail from QQ Music API response.

        Args:
            raw_data: Raw playlist info response

        Returns:
            Normalized playlist detail dictionary
        """
        if not raw_data:
            return None

        # Get playlist basic info
        playlist_id = raw_data.get('tid') or raw_data.get('dissid') or raw_data.get('dirid')
        name = raw_data.get('title') or raw_data.get('dissname', '')

        # Get creator info
        creator_data = raw_data.get('creator', {})
        if isinstance(creator_data, dict):
            creator = creator_data.get('name', '')
        else:
            creator = raw_data.get('nick', '') or str(creator_data)

        # Get cover
        cover = raw_data.get('logo') or raw_data.get('cover', '')

        # Get songs
        songs = raw_data.get('songlist', []) or raw_data.get('songs', [])

        return {
            'id': str(playlist_id) if playlist_id else '',
            'name': name,
            'creator': creator,
            'cover_url': cover,
            'description': raw_data.get('desc', ''),
            'play_count': raw_data.get('listennum', 0),
            'songs': songs,
            'total': len(songs),
        }

    # ========== YGKing Detail parsing methods ==========

    @staticmethod
    def parse_ygking_singer_detail(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse singer detail from YGKing API response.

        Args:
            data: Response from /api/singer endpoint

        Returns:
            Normalized singer detail dictionary
        """
        if data.get("code") != 0:
            return None

        data_obj = data.get("data", {})
        if not data_obj:
            return None

        # YGKing returns singer_list array (same as QQ Music API)
        singer_list = data_obj.get("singer_list", [])
        if not singer_list:
            return None

        singer_data = singer_list[0]
        basic_info = singer_data.get("basic_info", {}) or {}
        ex_info = singer_data.get("ex_info", {}) or {}
        pic_info = singer_data.get("pic", {}) or {}

        singer_mid = basic_info.get("singer_mid", "") or ""
        has_photo = basic_info.get("has_photo", 0)

        # Build avatar URL - try multiple sources
        avatar = pic_info.get("pic") or pic_info.get("big_black") or pic_info.get("big_white") or ""
        if not avatar and singer_mid:
            if has_photo:
                avatar = f"http://y.gtimg.cn/music/photo_new/T001R300x300M000{singer_mid}_{has_photo}.jpg"
            else:
                avatar = f"https://y.gtimg.cn/music/photo_new/T001R300x300M000{singer_mid}.jpg"

        return {
            'mid': singer_mid,
            'name': basic_info.get("name", "") or "",
            'avatar': avatar,
            'desc': ex_info.get("desc", "") or "",
            'songs': [],  # YGKing singer API doesn't return songs, need to search separately
            'total': 0,
        }

    @staticmethod
    def parse_ygking_album_detail(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse album detail from YGKing API response.

        Args:
            data: Response from /api/album endpoint

        Returns:
            Normalized album detail dictionary
        """
        if data.get("code") != 0:
            return None

        album_data = data.get("data", {})
        if not album_data:
            return None

        # YGKing returns QQ Music style format with basicInfo, singer.singerList, company
        basic_info = album_data.get("basicInfo", {})
        singer_data = album_data.get("singer", {})
        company_info = album_data.get("company", {})

        # Get singer list from singer.singerList
        singer_list = []
        if isinstance(singer_data, dict):
            singer_list = singer_data.get("singerList", [])
        singer_names = ", ".join([s.get("name", "") for s in singer_list]) if singer_list else ""
        singer_mid = singer_list[0].get("mid", "") if singer_list else ""

        # Build cover URL from albumMid
        album_mid = basic_info.get("albumMid", "") or album_data.get("mid", "")
        cover_url = f"https://y.gtimg.cn/music/photo_new/T002R300x300M000{album_mid}.jpg" if album_mid else ""

        # Parse songs (YGKing album API may not return songs, need separate call)
        songs_data = album_data.get("songs") or album_data.get("songList") or []
        songs = [OnlineMusicAdapter._parse_ygking_detail_song(item) for item in songs_data]

        return {
            'mid': album_mid,
            'name': basic_info.get("albumName", "") or album_data.get("name", ""),
            'singer': singer_names,
            'singer_mid': singer_mid,
            'cover_url': cover_url,
            'publish_date': basic_info.get("publishDate", "") or album_data.get("publish_date", ""),
            'description': basic_info.get("desc", "") or album_data.get("description", ""),
            'company': company_info.get("name", "") if isinstance(company_info, dict) else (company_info or ""),
            'language': basic_info.get("language", "") or album_data.get("language", ""),
            'genre': basic_info.get("genre", "") or album_data.get("genre", ""),
            'album_type': basic_info.get("albumType", "") or album_data.get("album_type", ""),
            'songs': songs,
            'total': album_data.get("totalNum") or album_data.get("song_count") or len(songs),
        }

    @staticmethod
    def parse_ygking_playlist_detail(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse playlist detail from YGKing API response.

        Args:
            data: Response from /api/playlist endpoint

        Returns:
            Normalized playlist detail dictionary
        """
        if data.get("code") != 0:
            return None

        playlist_data = data.get("data", {})
        if not playlist_data:
            return None

        # Get dirinfo (contains playlist metadata)
        dirinfo = playlist_data.get("dirinfo", {})

        # Get playlist name - try multiple locations
        name = ""
        if dirinfo:
            name = dirinfo.get("title", "")
        if not name:
            name = playlist_data.get("dissname", "") or playlist_data.get("title", "") or playlist_data.get("name", "")
        if name:
            name = _RE_HTML_TAG.sub('', name)  # Remove HTML tags

        # Get creator info - try multiple locations
        creator = ""
        if dirinfo:
            creator_data = dirinfo.get("creator", {})
            if isinstance(creator_data, dict):
                creator = creator_data.get("nick", "") or creator_data.get("name", "")
        if not creator:
            creator_info = playlist_data.get("creator", {}) or {}
            if isinstance(creator_info, dict):
                creator = creator_info.get("name", "") or creator_info.get("nick", "")
            elif isinstance(creator_info, str):
                creator = creator_info
        if not creator:
            creator = playlist_data.get("nick", "") or playlist_data.get("nickname", "")

        # Get cover URL - try multiple field names
        cover = ""
        if dirinfo:
            cover = dirinfo.get("picurl", "") or dirinfo.get("picurl2", "")
        if not cover:
            cover = playlist_data.get("logo", "") or playlist_data.get("cover", "") or playlist_data.get("cover_url", "")

        # Get playlist ID
        playlist_id = ""
        if dirinfo:
            playlist_id = str(dirinfo.get("id", ""))
        if not playlist_id:
            playlist_id = str(playlist_data.get("tid", "") or playlist_data.get("dissid", "") or playlist_data.get("id", ""))

        # Get description
        description = ""
        if dirinfo:
            description = dirinfo.get("desc", "")
        if not description:
            description = playlist_data.get("desc", "") or playlist_data.get("description", "")

        # Get songs - songlist is the primary field name
        songlist = playlist_data.get("songlist", []) or playlist_data.get("songs", [])
        songs = [OnlineMusicAdapter._parse_ygking_detail_song(item) for item in songlist]

        # Get total song count
        total = playlist_data.get("total_song_num", 0) or playlist_data.get("songlist_size", 0) or len(songs)

        return {
            'id': playlist_id,
            'name': name,
            'creator': creator,
            'cover_url': cover,
            'cover': cover,
            'description': description,
            'song_count': total,
            'songs': songs,
            'total': total,
        }

    @staticmethod
    def _parse_ygking_detail_song(item: Dict) -> Dict:
        """Parse a single song from YGKing detail API response."""
        # Parse singers - strip HTML tags from names
        singers = []
        for s in (item.get("singer") or []):
            if isinstance(s, dict):
                name = s.get("name", "") or ""
                if name:
                    name = _RE_HTML_TAG.sub('', name)
                singers.append({
                    'mid': s.get("mid", "") or "",
                    'name': name
                })
            elif isinstance(s, str):
                name = _RE_HTML_TAG.sub('', s) if s else ""
                singers.append({'mid': "", 'name': name})

        # Parse album - strip HTML tags from name
        album_data = item.get("album")
        if isinstance(album_data, dict):
            album_name = album_data.get("name", "") or ""
            if album_name:
                album_name = _RE_HTML_TAG.sub('', album_name)
            album = {
                'mid': album_data.get("mid", "") or "",
                'name': album_name
            }
        elif isinstance(album_data, str):
            album_name = _RE_HTML_TAG.sub('', album_data) if album_data else ""
            album = {'mid': "", 'name': album_name}
        else:
            album_name = item.get("albumname", "") or item.get("albumName", "") or ""
            if album_name:
                album_name = _RE_HTML_TAG.sub('', album_name)
            album = {
                'mid': item.get("albummid", "") or item.get("albumMid", "") or "",
                'name': album_name
            }

        # Get song name - strip HTML tags
        name = item.get("title", "") or item.get("name", "") or ""
        if name:
            name = _RE_HTML_TAG.sub('', name)

        return {
            'mid': item.get("mid", "") or "",
            'id': item.get("id"),
            'name': name,
            'title': name,
            'singer': singers,
            'album': album,
            'albummid': album.get("mid", ""),
            'albumname': album.get("name", ""),
            'interval': item.get("duration") or item.get("interval", 0) or 0,
        }
