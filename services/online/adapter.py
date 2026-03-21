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
                mid=item.get("mid", item.get("singer_mid", "")),
                name=item.get("name", item.get("singer_name", "")),
                song_count=item.get("song_count", 0),
                album_count=item.get("album_count", 0)
            )
            artists.append(artist)
        return artists

    @staticmethod
    def _parse_qqmusic_albums(items: List[Dict]) -> List[OnlineAlbum]:
        """Parse albums from QQ Music API format."""
        albums = []
        for item in items:
            album = OnlineAlbum(
                mid=item.get("mid", item.get("albummid", "")),
                name=item.get("name", item.get("albumname", "")),
                singer_mid=item.get("singer_mid", ""),
                singer_name=item.get("singer_name", ""),
                song_count=item.get("song_count", 0),
                publish_date=item.get("publish_date")
            )
            albums.append(album)
        return albums

    @staticmethod
    def _parse_qqmusic_playlists(items: List[Dict]) -> List[OnlinePlaylist]:
        """Parse playlists from QQ Music API format."""
        playlists = []
        for item in items:
            playlist = OnlinePlaylist(
                id=str(item.get("tid", item.get("id", ""))),
                mid=item.get("mid", ""),
                title=item.get("title", item.get("name", "")),
                creator=item.get("creator", {}).get("name", "") if isinstance(item.get("creator"), dict) else "",
                song_count=item.get("song_count", item.get("cur_song_num", 0)),
                play_count=item.get("play_count", item.get("access_num", 0))
            )
            playlists.append(playlist)
        return playlists
