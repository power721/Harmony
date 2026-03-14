"""
Repository module - Data access abstraction layer.
"""

from .interfaces import (
    TrackRepository,
    PlaylistRepository,
    CloudRepository,
    QueueRepository,
)
from .track_repository import SqliteTrackRepository
from .playlist_repository import SqlitePlaylistRepository
from .cloud_repository import SqliteCloudRepository
from .queue_repository import SqliteQueueRepository

__all__ = [
    'TrackRepository', 'PlaylistRepository', 'CloudRepository', 'QueueRepository',
    'SqliteTrackRepository', 'SqlitePlaylistRepository', 'SqliteCloudRepository', 'SqliteQueueRepository',
]
