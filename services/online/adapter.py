"""
Online music API adapter.
Unifies response formats from different API sources.
"""

import logging
from typing import Dict, List, Any, Optional

from domain.online_music import (
    OnlineTrack, OnlineArtist, OnlineAlbum, OnlinePlaylist,
    AlbumInfo, OnlineSinger, SearchResult, SearchType
)

logger = logging.getLogger(__name__)


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
            # Parse singers
            singers = []
            for s in item.get("singer", []):
                singers.append(OnlineSinger(
                    mid=s.get("mid", ""),
                    name=s.get("name", "")
                ))

            # Parse album
            album_data = item.get("album", {})
            album = AlbumInfo(
                mid=album_data.get("mid", ""),
                name=album_data.get("name", "")
            ) if album_data else None

            # Parse pay info
            pay_info = item.get("pay", {})
            pay_play = pay_info.get("pay_play", 0) if pay_info else 0

            track = OnlineTrack(
                mid=item.get("mid", ""),
                id=item.get("id"),
                title=item.get("title", ""),
                singer=singers,
                album=album,
                duration=item.get("interval", 0),
                pay_play=pay_play
            )
            tracks.append(track)

        return tracks

    @staticmethod
    def _parse_ygking_artists(items: List[Dict]) -> List[OnlineArtist]:
        """Parse artists from YGKing API format."""
        artists = []
        for item in items:
            artist = OnlineArtist(
                mid=item.get("mid", ""),
                name=item.get("name", ""),
                avatar_url=item.get("avatar", ""),
                song_count=item.get("song_count", 0),
                album_count=item.get("album_count", 0)
            )
            artists.append(artist)
        return artists

    @staticmethod
    def _parse_ygking_albums(items: List[Dict]) -> List[OnlineAlbum]:
        """Parse albums from YGKing API format."""
        albums = []
        for item in items:
            album = OnlineAlbum(
                mid=item.get("mid", ""),
                name=item.get("name", ""),
                singer_mid=item.get("singer_mid", ""),
                singer_name=item.get("singer_name", ""),
                cover_url=item.get("cover", ""),
                song_count=item.get("song_count", 0),
                publish_date=item.get("publish_date")
            )
            albums.append(album)
        return albums

    @staticmethod
    def _parse_ygking_playlists(items: List[Dict]) -> List[OnlinePlaylist]:
        """Parse playlists from YGKing API format."""
        playlists = []
        for item in items:
            playlist = OnlinePlaylist(
                id=str(item.get("id", "")),
                mid=item.get("mid", ""),
                title=item.get("title", ""),
                creator=item.get("creator", ""),
                cover_url=item.get("cover", ""),
                song_count=item.get("song_count", 0),
                play_count=item.get("play_count", 0)
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
            if item.get("singerName"):
                singers.append(OnlineSinger(
                    mid=item.get("singerMid", ""),
                    name=item.get("singerName", "")
                ))

            # Album info
            album = AlbumInfo(
                mid=item.get("albumMid", ""),
                name=item.get("albumName", "")
            )

            track = OnlineTrack(
                mid=item.get("songMid", ""),
                id=item.get("songId"),
                title=item.get("title", ""),
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

        # Type keys for different search types
        type_keys = {
            SearchType.SONG: "item_song",
            SearchType.SINGER: "singer",
            SearchType.ALBUM: "item_album",
            SearchType.PLAYLIST: "item_songlist",
        }

        result_key = type_keys.get(search_type, "item_song")
        body = raw_data.get("body", {})
        items = body.get(result_key, [])

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
                singers.append(OnlineSinger(mid="", name=singer_data))
            elif isinstance(singer_data, list):
                for s in singer_data:
                    if isinstance(s, dict):
                        singers.append(OnlineSinger(
                            mid=s.get("mid", ""),
                            name=s.get("name", "")
                        ))
                    elif isinstance(s, str):
                        singers.append(OnlineSinger(mid="", name=s))
            elif isinstance(singer_data, dict):
                singers.append(OnlineSinger(
                    mid=singer_data.get("mid", ""),
                    name=singer_data.get("name", "")
                ))

            # Parse album - can be dict or string
            album_data = item.get("album")
            if isinstance(album_data, str):
                album = AlbumInfo(mid="", name=album_data)
            elif isinstance(album_data, dict):
                album = AlbumInfo(
                    mid=album_data.get("mid", ""),
                    name=album_data.get("name", "")
                )
            else:
                album = AlbumInfo(
                    mid=item.get("albummid", ""),
                    name=item.get("albumname", "")
                )

            track = OnlineTrack(
                mid=item.get("songmid", item.get("mid", "")),
                id=item.get("songid", item.get("id")),
                title=item.get("songname", item.get("title", "")),
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
            artist = OnlineArtist(
                mid=item.get("singerMID", item.get("mid", "")),
                name=item.get("singerName", ""),
                avatar_url=item.get("singerPic", ""),
                song_count=item.get("songNum", 0),
                album_count=item.get("albumNum", 0)
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

            # QQ Music API uses different field names
            album = OnlineAlbum(
                mid=item.get("albummid", ""),
                name=item.get("name", ""),
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
        import re
        playlists = []
        for item in items:
            # Clean HTML tags from title
            dissname = item.get("dissname", "")
            title = re.sub(r'<[^>]+>', '', dissname) if dissname else ""

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
        return {
            'mid': song.get('mid', song.get('songMid', '')),
            'id': song.get('id', song.get('songId')),
            'name': song.get('name', song.get('songName', song.get('title', ''))),
            'singer': song.get('singer', []),
            'album': song.get('album', {}),
            'albummid': song.get('albumMid', song.get('albummid', '')),
            'albumname': song.get('albumName', song.get('albumname', '')),
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
