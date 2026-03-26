"""
Repository module - Data access abstraction layer.
"""

from .album_repository import SqliteAlbumRepository
from .artist_repository import SqliteArtistRepository
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
from .settings_repository import SqliteSettingsRepository
from .track_repository import SqliteTrackRepository

__all__ = [
    'TrackRepository', 'PlaylistRepository', 'CloudRepository', 'QueueRepository',
    'SqliteTrackRepository', 'SqlitePlaylistRepository', 'SqliteCloudRepository', 'SqliteQueueRepository',
    'SqliteFavoriteRepository', 'SqliteHistoryRepository',
    'SqliteAlbumRepository', 'SqliteArtistRepository', 'SqliteSettingsRepository',
]
