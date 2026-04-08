"""
Playback domain models - PlayMode, PlaybackState, and PlayQueueItem.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class PlayMode(Enum):
    """Playback mode enumeration."""
    SEQUENTIAL = 0  # Play tracks in order
    LOOP = 1  # Loop the current track
    PLAYLIST_LOOP = 2  # Loop the entire playlist
    RANDOM = 3  # Random playback
    RANDOM_LOOP = 4  # Random playback with playlist loop
    RANDOM_TRACK_LOOP = 5  # Random playback with track loop


class PlaybackState(Enum):
    """Player state enumeration."""
    STOPPED = 0
    PLAYING = 1
    PAUSED = 2


@dataclass
class PlayQueueItem:
    """Represents an item in the persistent play queue."""

    id: Optional[int] = None
    position: int = 0  # Order in the queue (determines playback order)
    source: str = "Local"  # TrackSource value: "Local", "ONLINE", "QUARK", "BAIDU"
    track_id: Optional[int] = None  # Track ID in database
    cloud_file_id: Optional[str] = None  # Cloud file ID / Song MID
    online_provider_id: Optional[str] = None  # Plugin provider id for online tracks
    cloud_account_id: Optional[int] = None  # Cloud account ID
    local_path: str = ""  # Local file path
    title: str = ""
    artist: str = ""
    album: str = ""
    duration: float = 0.0
    download_failed: bool = False
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
