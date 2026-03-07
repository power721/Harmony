"""
Database models for the music player.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Track:
    """Represents a music track in the library."""

    id: Optional[int] = None
    path: str = ""
    title: str = ""
    artist: str = ""
    album: str = ""
    duration: float = 0.0
    cover_path: Optional[str] = None
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

    @property
    def display_name(self) -> str:
        """Get display name for the track."""
        if self.title:
            return self.title
        return self.path.split("/")[-1]

    @property
    def artist_album(self) -> str:
        """Get artist and album string."""
        parts = []
        if self.artist:
            parts.append(self.artist)
        if self.album and self.album != self.artist:
            parts.append(self.album)
        return " - ".join(parts) if parts else "Unknown"


@dataclass
class Playlist:
    """Represents a playlist."""

    id: Optional[int] = None
    name: str = ""
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class PlaylistItem:
    """Represents an item in a playlist."""

    id: Optional[int] = None
    playlist_id: int = 0
    track_id: int = 0
    position: int = 0


@dataclass
class PlayHistory:
    """Represents a play history entry."""

    id: Optional[int] = None
    track_id: int = 0
    played_at: Optional[datetime] = None
    play_count: int = 1

    def __post_init__(self):
        if self.played_at is None:
            self.played_at = datetime.now()


@dataclass
class Favorite:
    """Represents a favorite track."""

    id: Optional[int] = None
    track_id: int = 0
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class CloudAccount:
    """Represents a cloud storage account (Quark, OneDrive, etc.)"""

    id: Optional[int] = None
    provider: str = ""  # "quark", "onedrive", etc.
    account_name: str = ""  # User-defined name
    account_email: str = ""  # From provider
    access_token: str = ""  # Cookie or OAuth token
    refresh_token: str = ""  # For token refresh
    token_expires_at: Optional[datetime] = None
    is_active: bool = True
    last_folder_id: str = "0"  # Last opened folder ID
    last_folder_path: str = "/"  # Last opened folder path
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()


@dataclass
class CloudFile:
    """Cached metadata for cloud drive files"""

    id: Optional[int] = None
    account_id: int = 0
    file_id: str = ""  # Provider's file identifier
    parent_id: str = ""  # Parent folder ID (empty for root)
    name: str = ""
    file_type: str = ""  # "folder", "audio", "other"
    size: Optional[int] = None
    mime_type: Optional[str] = None
    duration: Optional[float] = None  # For audio files
    metadata: Optional[str] = None  # JSON for provider-specific data
    local_path: Optional[str] = None  # Downloaded local file path
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
