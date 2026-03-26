"""
Repository module - Data access abstraction layer.
"""

from .cloud_repository import SqliteCloudRepository
from .favorite_repository import SqliteFavoriteRepository
from .history_repository import SqliteHistoryRepository
from .interfaces import (
    TrackRepository,
    PlaylistRepository,
    CloudRepository,
    QueueRepository,
)
from .playlist_repository import SqlitePlaylistRepository
from .queue_repository import SqliteQueueRepository
from .track_repository import SqliteTrackRepository

__all__ = [
    'TrackRepository', 'PlaylistRepository', 'CloudRepository', 'QueueRepository',
    'SqliteTrackRepository', 'SqlitePlaylistRepository', 'SqliteCloudRepository', 'SqliteQueueRepository',
    'SqliteFavoriteRepository', 'SqliteHistoryRepository',
]
