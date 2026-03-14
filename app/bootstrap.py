"""
Bootstrap - Dependency injection container.
"""

import logging
from typing import Optional

from infrastructure import HttpClient
from infrastructure.database import DatabaseManager
from repositories.cloud_repository import SqliteCloudRepository
from repositories.playlist_repository import SqlitePlaylistRepository
from repositories.queue_repository import SqliteQueueRepository
from repositories.track_repository import SqliteTrackRepository
from services.library import LibraryService
from services.metadata import CoverService
from services.playback import PlaybackService, QueueService
from system.config import ConfigManager
from system.event_bus import EventBus

logger = logging.getLogger(__name__)


class Bootstrap:
    """
    Dependency injection container.

    Creates and manages all application components with proper
    dependency injection for loose coupling.
    """

    _instance: Optional["Bootstrap"] = None

    def __init__(self, db_path: str = "music_player.db"):
        """Initialize bootstrap container."""
        self._db_path = db_path

        # Core infrastructure
        self._db: Optional[DatabaseManager] = None
        self._config: Optional[ConfigManager] = None
        self._event_bus: Optional[EventBus] = None
        self._http_client: Optional[HttpClient] = None

        # Repositories
        self._track_repo: Optional[SqliteTrackRepository] = None
        self._playlist_repo: Optional[SqlitePlaylistRepository] = None
        self._cloud_repo: Optional[SqliteCloudRepository] = None
        self._queue_repo: Optional[SqliteQueueRepository] = None

        # Services
        self._playback_service: Optional[PlaybackService] = None
        self._queue_service: Optional[QueueService] = None
        self._library_service: Optional[LibraryService] = None
        self._cover_service: Optional[CoverService] = None

    @classmethod
    def instance(cls) -> "Bootstrap":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ===== Infrastructure =====

    @property
    def db(self) -> DatabaseManager:
        """Get database manager."""
        if self._db is None:
            self._db = DatabaseManager(self._db_path)
        return self._db

    @property
    def config(self) -> ConfigManager:
        """Get config manager."""
        if self._config is None:
            self._config = ConfigManager()
        return self._config

    @property
    def event_bus(self) -> EventBus:
        """Get event bus."""
        if self._event_bus is None:
            self._event_bus = EventBus.instance()
        return self._event_bus

    @property
    def http_client(self) -> HttpClient:
        """Get HTTP client."""
        if self._http_client is None:
            self._http_client = HttpClient()
        return self._http_client

    # ===== Repositories =====

    @property
    def track_repo(self) -> SqliteTrackRepository:
        """Get track repository."""
        if self._track_repo is None:
            self._track_repo = SqliteTrackRepository(self._db_path)
        return self._track_repo

    @property
    def playlist_repo(self) -> SqlitePlaylistRepository:
        """Get playlist repository."""
        if self._playlist_repo is None:
            self._playlist_repo = SqlitePlaylistRepository(self._db_path)
        return self._playlist_repo

    @property
    def cloud_repo(self) -> SqliteCloudRepository:
        """Get cloud repository."""
        if self._cloud_repo is None:
            self._cloud_repo = SqliteCloudRepository(self._db_path)
        return self._cloud_repo

    @property
    def queue_repo(self) -> SqliteQueueRepository:
        """Get queue repository."""
        if self._queue_repo is None:
            self._queue_repo = SqliteQueueRepository(self._db_path)
        return self._queue_repo

    # ===== Services =====

    @property
    def playback_service(self) -> PlaybackService:
        """Get playback service."""
        if self._playback_service is None:
            self._playback_service = PlaybackService(
                db_manager=self.db,
                config_manager=self.config,
                cover_service=self.cover_service,
            )
        return self._playback_service

    @property
    def queue_service(self) -> QueueService:
        """Get queue service."""
        if self._queue_service is None:
            self._queue_service = QueueService(
                queue_repo=self.queue_repo,
                config_manager=self.config,
                engine=self.playback_service.engine,
            )
        return self._queue_service

    @property
    def library_service(self) -> LibraryService:
        """Get library service."""
        if self._library_service is None:
            self._library_service = LibraryService(
                track_repo=self.track_repo,
                playlist_repo=self.playlist_repo,
                event_bus=self.event_bus,
                cover_service=self.cover_service,
                db_manager=self.db,
            )
            # Initialize albums/artists tables if needed
            self._library_service.init_albums_artists()
        return self._library_service

    @property
    def cover_service(self) -> CoverService:
        """Get cover service."""
        if self._cover_service is None:
            self._cover_service = CoverService(http_client=self.http_client)
        return self._cover_service
