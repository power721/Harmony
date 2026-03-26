"""
Abstract base classes for source providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class SourceResult:
    """Base class for search results from online sources."""
    id: str
    title: str
    artist: str
    album: str = ""
    source: str = ""
    duration: Optional[float] = None  # Duration in seconds


@dataclass
class CoverSearchResult(SourceResult):
    """Search result for cover art."""
    cover_url: Optional[str] = None
    album_mid: Optional[str] = None  # For QQ Music lazy cover fetch


@dataclass
class ArtistCoverSearchResult:
    """Search result for artist cover (avatar)."""
    id: str
    name: str
    cover_url: Optional[str] = None
    album_count: Optional[int] = None
    source: str = ""
    singer_mid: Optional[str] = None  # For QQ Music lazy cover fetch


@dataclass
class LyricsSearchResult(SourceResult):
    """Search result for lyrics."""
    cover_url: Optional[str] = None
    lyrics: Optional[str] = None  # Pre-fetched lyrics (e.g., from LRCLIB)
    accesskey: Optional[str] = None  # For Kugou
    supports_yrc: bool = False  # Whether source supports word-by-word lyrics


class CoverSource(ABC):
    """
    Abstract base class for cover art sources.

    Each source (NetEase, QQ Music, iTunes, etc.) should implement
    this interface to provide cover art search functionality.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the source name for display and logging."""
        pass

    @abstractmethod
    def search(
        self,
        title: str,
        artist: str,
        album: str = "",
        duration: Optional[float] = None
    ) -> List[CoverSearchResult]:
        """
        Search for cover art.

        Args:
            title: Track title
            artist: Track artist
            album: Album name (optional)
            duration: Track duration in seconds (optional, for better matching)

        Returns:
            List of CoverSearchResult objects
        """
        pass

    def is_available(self) -> bool:
        """
        Check if this source is available.

        Override this method to check for API keys or other requirements.

        Returns:
            True if the source can be used
        """
        return True

    def get_timeout(self) -> int:
        """Return the timeout in seconds for this source."""
        return 5


class ArtistCoverSource(ABC):
    """
    Abstract base class for artist cover (avatar) sources.

    Each source should implement this interface to provide
    artist avatar search functionality.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the source name for display and logging."""
        pass

    @abstractmethod
    def search(
        self,
        artist_name: str,
        limit: int = 10
    ) -> List[ArtistCoverSearchResult]:
        """
        Search for artist cover (avatar).

        Args:
            artist_name: Artist name to search
            limit: Maximum number of results

        Returns:
            List of ArtistCoverSearchResult objects
        """
        pass

    def is_available(self) -> bool:
        """
        Check if this source is available.

        Returns:
            True if the source can be used
        """
        return True

    def get_timeout(self) -> int:
        """Return the timeout in seconds for this source."""
        return 5


class LyricsSource(ABC):
    """
    Abstract base class for lyrics sources.

    Each source (NetEase, QQ Music, Kugou, LRCLIB, etc.) should implement
    this interface to provide lyrics search functionality.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the source name for display and logging."""
        pass

    @abstractmethod
    def search(
        self,
        title: str,
        artist: str,
        limit: int = 10
    ) -> List[LyricsSearchResult]:
        """
        Search for lyrics.

        Args:
            title: Track title
            artist: Track artist
            limit: Maximum number of results

        Returns:
            List of LyricsSearchResult objects
        """
        pass

    @abstractmethod
    def get_lyrics(self, result: LyricsSearchResult) -> Optional[str]:
        """
        Download lyrics for a search result.

        Args:
            result: Search result to get lyrics for

        Returns:
            Lyrics content or None if failed
        """
        pass

    def is_available(self) -> bool:
        """
        Check if this source is available.

        Returns:
            True if the source can be used
        """
        return True

    def get_timeout(self) -> int:
        """Return the timeout in seconds for this source."""
        return 6
