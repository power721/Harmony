"""Playlist folder domain models."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .playlist import Playlist


@dataclass(slots=True)
class PlaylistFolder:
    """Represents a top-level playlist folder."""

    id: Optional[int] = None
    name: str = ""
    position: int = 0
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass(slots=True)
class PlaylistFolderGroup:
    """Folder plus its nested playlists."""

    folder: PlaylistFolder
    playlists: list[Playlist] = field(default_factory=list)


@dataclass(slots=True)
class PlaylistTree:
    """Playlist tree with root playlists and folder groups."""

    root_playlists: list[Playlist] = field(default_factory=list)
    folders: list[PlaylistFolderGroup] = field(default_factory=list)
