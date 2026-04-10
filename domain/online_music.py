"""
Online music domain models.
Entities for online music search results.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List


@dataclass(slots=True)
class OnlineSinger:
    """Singer info in online track."""

    mid: str = ""
    name: str = ""


@dataclass(slots=True)
class AlbumInfo:
    """Simple album info in online track."""

    mid: str = ""
    name: str = ""


@dataclass(slots=True)
class OnlineTrack:
    """
    Online track from search result.

    Unified format from different online API sources.
    """

    mid: str = ""  # Song MID (unique identifier)
    id: Optional[int] = None  # Song ID (optional)
    title: str = ""
    singer: List[OnlineSinger] = field(default_factory=list)
    album: Optional[AlbumInfo] = None
    duration: int = 0  # Duration in seconds
    pay_play: int = 0  # 1 if requires VIP/payment

    @property
    def singer_name(self) -> str:
        """Get singer names as string."""
        if not self.singer:
            return ""
        return ", ".join(s.name for s in self.singer if s.name)

    @property
    def album_name(self) -> str:
        """Get album name."""
        return self.album.name if self.album else ""

    @property
    def display_title(self) -> str:
        """Get display title."""
        return self.title or "Unknown"

    @property
    def is_vip(self) -> bool:
        """Check if track requires VIP."""
        return self.pay_play == 1


@dataclass(slots=True)
class OnlineArtist:
    """
    Online artist from search result.
    """

    mid: str = ""
    name: str = ""
    avatar_url: Optional[str] = None
    song_count: int = 0
    album_count: int = 0
    fan_count: int = 0


@dataclass(slots=True)
class OnlineAlbum:
    """
    Online album from search result.
    """

    mid: str = ""
    name: str = ""
    singer_mid: str = ""
    singer_name: str = ""
    cover_url: Optional[str] = None
    song_count: int = 0
    publish_date: Optional[str] = None
    description: Optional[str] = None
    company: Optional[str] = None
    genre: Optional[str] = None
    language: Optional[str] = None
    album_type: Optional[str] = None


@dataclass(slots=True)
class OnlinePlaylist:
    """
    Online playlist from search result.
    """

    id: str = ""
    mid: str = ""  # Some APIs use mid, some use id
    title: str = ""
    creator: str = ""
    cover_url: Optional[str] = None
    song_count: int = 0
    play_count: int = 0


@dataclass(slots=True)
class SearchResult:
    """
    Search result container.
    """

    keyword: str = ""
    search_type: str = "song"  # song, singer, album, playlist
    page: int = 1
    page_size: int = 20
    total: int = 0
    tracks: List[OnlineTrack] = field(default_factory=list)
    artists: List[OnlineArtist] = field(default_factory=list)
    albums: List[OnlineAlbum] = field(default_factory=list)
    playlists: List[OnlinePlaylist] = field(default_factory=list)


class SearchType(str, Enum):
    """Search type constants."""

    SONG = "song"
    SINGER = "singer"
    ALBUM = "album"
    PLAYLIST = "playlist"
