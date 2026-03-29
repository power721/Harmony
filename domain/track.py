"""
Track domain model - Core track entity.
"""

import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

# Type alias for track ID
TrackId = int


class TrackSource(str, Enum):
    """Track source enumeration."""
    LOCAL = "Local"      # 本地歌曲
    QUARK = "QUARK"      # 夸克网盘
    BAIDU = "BAIDU"      # 百度网盘
    QQ = "QQ"            # QQ音乐（网络歌曲）


@dataclass
class Track:
    """
    Represents a music track in the library.

    This is a pure domain model with no external dependencies.
    """
    id: Optional[TrackId] = None
    path: str = ""
    title: str = ""
    artist: str = ""
    album: str = ""
    duration: float = 0.0
    cover_path: Optional[str] = None
    created_at: Optional[datetime] = None
    cloud_file_id: Optional[str] = None  # Cloud file ID if downloaded from cloud
    source: TrackSource = TrackSource.LOCAL  # Track source: Local, QUARK, BAIDU, QQ
    file_size: Optional[int] = None
    file_mtime: Optional[float] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

    @property
    def display_name(self) -> str:
        """Get display name for the track."""
        if self.title:
            return self.title
        return os.path.basename(self.path) if self.path else "Unknown"

    @property
    def artist_album(self) -> str:
        """Get artist and album string."""
        parts = []
        if self.artist:
            parts.append(self.artist)
        if self.album and self.album != self.artist:
            parts.append(self.album)
        return " - ".join(parts) if parts else "Unknown"
