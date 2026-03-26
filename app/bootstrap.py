"""
Bootstrap - Dependency injection container.
"""

import logging
from typing import Optional

from infrastructure import HttpClient
from infrastructure.database import DatabaseManager
from repositories.cloud_repository import SqliteCloudRepository
from repositories.favorite_repository import SqliteFavoriteRepository
from repositories.history_repository import SqliteHistoryRepository
from repositories.playlist_repository import SqlitePlaylistRepository
from repositories.queue_repository import SqliteQueueRepository
from repositories.track_repository import SqliteTrackRepository
from services.library import LibraryService
from services.library.favorites_service import FavoritesService
from services.library.play_history_service import PlayHistoryService
from services.library.playlist_service import PlaylistService
from services.library.file_organization_service import FileOrganizationService
from services.metadata import CoverService
from services.playback import PlaybackService, QueueService
from services.cloud import CloudAccountService, CloudFileService
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

    def __init__(self, db_path: str = "Harmony.db"):
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
        self._favorite_repo: Optional[SqliteFavoriteRepository] = None
        self._history_repo: Optional[SqliteHistoryRepository] = None

        # Services
        self._playback_service: Optional[PlaybackService] = None
        self._queue_service: Optional[QueueService] = None
        self._library_service: Optional[LibraryService] = None
        self._favorites_service: Optional[FavoritesService] = None
        self._play_history_service: Optional[PlayHistoryService] = None
        self._playlist_service: Optional[PlaylistService] = None
        self._cloud_account_service: Optional[CloudAccountService] = None
        self._cloud_file_service: Optional[CloudFileService] = None
        self._cover_service: Optional[CoverService] = None
        self._file_org_service: Optional["FileOrganizationService"] = None
        self._online_music_service: Optional["OnlineMusicService"] = None
        self._online_download_service: Optional["OnlineDownloadService"] = None

        # QQ Music client
        self._qqmusic_client: Optional["QQMusicClient"] = None

        # Services
        self._cache_cleaner_service: Optional["CacheCleanerService"] = None

    @classmethod
    def instance(cls, db_path: str = "Harmony.db") -> "Bootstrap":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls(db_path)
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
            self._config = ConfigManager(db_manager=self.db)
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
            self._track_repo = SqliteTrackRepository(self._db_path, db_manager=self.db)
        return self._track_repo

    @property
    def playlist_repo(self) -> SqlitePlaylistRepository:
        """Get playlist repository."""
        if self._playlist_repo is None:
            self._playlist_repo = SqlitePlaylistRepository(self._db_path, db_manager=self.db)
        return self._playlist_repo

    @property
    def cloud_repo(self) -> SqliteCloudRepository:
        """Get cloud repository."""
        if self._cloud_repo is None:
            self._cloud_repo = SqliteCloudRepository(self._db_path, db_manager=self.db)
        return self._cloud_repo

    @property
    def queue_repo(self) -> SqliteQueueRepository:
        """Get queue repository."""
        if self._queue_repo is None:
            self._queue_repo = SqliteQueueRepository(self._db_path, db_manager=self.db)
        return self._queue_repo

    @property
    def favorite_repo(self) -> SqliteFavoriteRepository:
        """Get favorite repository."""
        if self._favorite_repo is None:
            self._favorite_repo = SqliteFavoriteRepository(self._db_path, db_manager=self.db)
        return self._favorite_repo

    @property
    def history_repo(self) -> SqliteHistoryRepository:
        """Get history repository."""
        if self._history_repo is None:
            self._history_repo = SqliteHistoryRepository(self._db_path, db_manager=self.db)
        return self._history_repo

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
                db_manager=self.db,
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
            )
        return self._library_service

    @property
    def favorites_service(self) -> FavoritesService:
        """Get favorites service."""
        if self._favorites_service is None:
            self._favorites_service = FavoritesService(
                favorite_repo=self.favorite_repo,
                event_bus=self.event_bus,
            )
        return self._favorites_service

    @property
    def play_history_service(self) -> PlayHistoryService:
        """Get play history service."""
        if self._play_history_service is None:
            self._play_history_service = PlayHistoryService(
                history_repo=self.history_repo,
                event_bus=self.event_bus,
            )
        return self._play_history_service

    @property
    def playlist_service(self) -> PlaylistService:
        """Get playlist service."""
        if self._playlist_service is None:
            self._playlist_service = PlaylistService(
                playlist_repo=self.playlist_repo,
                event_bus=self.event_bus,
            )
        return self._playlist_service

    @property
    def cloud_account_service(self) -> CloudAccountService:
        """Get cloud account service."""
        if self._cloud_account_service is None:
            self._cloud_account_service = CloudAccountService(
                db_manager=self.db,
                event_bus=self.event_bus,
            )
        return self._cloud_account_service

    @property
    def cloud_file_service(self) -> CloudFileService:
        """Get cloud file service."""
        if self._cloud_file_service is None:
            self._cloud_file_service = CloudFileService(
                db_manager=self.db,
                event_bus=self.event_bus,
            )
        return self._cloud_file_service

    @property
    def cover_service(self) -> CoverService:
        """Get cover service."""
        if self._cover_service is None:
            self._cover_service = CoverService(http_client=self.http_client)
        return self._cover_service

    @property
    def file_org_service(self) -> FileOrganizationService:
        """Get file organization service."""
        if self._file_org_service is None:
            self._file_org_service = FileOrganizationService(
                track_repo=self.track_repo,
                event_bus=self.event_bus,
                db_manager=self.db,
            )
        return self._file_org_service

    # ===== QQ Music =====

    @property
    def qqmusic_client(self) -> "QQMusicClient":
        """Get QQ Music client."""
        if self._qqmusic_client is None:
            from services.lyrics.qqmusic_lyrics import QQMusicClient
            self._qqmusic_client = QQMusicClient()
        return self._qqmusic_client

    def refresh_qqmusic_client(self):
        """Refresh QQ Music client (call after login)."""
        from services.lyrics.qqmusic_lyrics import QQMusicClient
        self._qqmusic_client = QQMusicClient()
        logger.info("QQ Music client refreshed")
        return self._qqmusic_client

    # ===== Online Music =====

    @property
    def online_music_service(self) -> "OnlineMusicService":
        """Get online music service."""
        if self._online_music_service is None:
            from services.online import OnlineMusicService
            from services.cloud.qqmusic.qqmusic_service import QQMusicService

            # Try to create QQMusicService if credential is available
            qqmusic = None
            if self.config:
                # Use get_qqmusic_credential() to get full credential including refresh_token
                credential = self.config.get_qqmusic_credential()
                if credential and credential.get('musicid') and credential.get('musickey'):
                    try:
                        qqmusic = QQMusicService(credential)
                        logger.info(f"QQMusicService initialized for OnlineMusicService, "
                                   f"musicid={credential.get('musicid')}, "
                                   f"has_refresh_key={bool(credential.get('refresh_key'))}, "
                                   f"has_refresh_token={bool(credential.get('refresh_token'))}")
                    except Exception as e:
                        logger.debug(f"Failed to initialize QQMusicService: {e}")

            self._online_music_service = OnlineMusicService(
                config_manager=self.config,
                qqmusic_service=qqmusic
            )
        return self._online_music_service

    @property
    def online_download_service(self) -> "OnlineDownloadService":
        """Get online download service."""
        if self._online_download_service is None:
            from services.online import OnlineDownloadService
            self._online_download_service = OnlineDownloadService(
                config_manager=self.config,
                qqmusic_service=None,
                online_music_service=self.online_music_service
            )
        return self._online_download_service

    @property
    def cache_cleaner_service(self) -> "CacheCleanerService":
        """Get cache cleaner service."""
        if self._cache_cleaner_service is None:
            from services.online.cache_cleaner_service import CacheCleanerService
            self._cache_cleaner_service = CacheCleanerService(
                config_manager=self.config,
                download_service=self.online_download_service,
                event_bus=self.event_bus,
                queue_service=self.queue_service
            )
        return self._cache_cleaner_service

