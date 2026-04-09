"""
Bootstrap - Dependency injection container.
"""

import importlib
import logging
import subprocess
import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from infrastructure import HttpClient
from infrastructure.database import DatabaseManager
from repositories.album_repository import SqliteAlbumRepository
from repositories.artist_repository import SqliteArtistRepository
from repositories.cloud_repository import SqliteCloudRepository
from repositories.favorite_repository import SqliteFavoriteRepository
from repositories.genre_repository import SqliteGenreRepository
from repositories.history_repository import SqliteHistoryRepository
from repositories.playlist_repository import SqlitePlaylistRepository
from repositories.queue_repository import SqliteQueueRepository
from repositories.settings_repository import SqliteSettingsRepository
from repositories.track_repository import SqliteTrackRepository
from services.cloud import CloudAccountService, CloudFileService
from services.library import LibraryService
from services.library.favorites_service import FavoritesService
from services.library.file_organization_service import FileOrganizationService
from services.library.play_history_service import PlayHistoryService
from services.library.playlist_service import PlaylistService
from services.metadata import CoverService
from services.playback import PlaybackService, QueueService
from system.config import ConfigManager
from system.event_bus import EventBus
from system.plugins.host_services import BootstrapPluginContextFactory
from system.plugins.manager import PluginManager
from system.plugins.state_store import PluginStateStore

if TYPE_CHECKING:
    from services.download.online_download_gateway import OnlineDownloadGateway
    from services.download.cache_cleaner_service import CacheCleanerService
    from services.playback.sleep_timer_service import SleepTimerService
    from system.mpris import MPRISController
    from system.theme import ThemeManager

logger = logging.getLogger(__name__)


def _can_import_linux_mpris_runtime() -> tuple[bool, Optional[str]]:
    try:
        import dbus
        import dbus.mainloop.glib
        import dbus.service
        from gi.repository import GLib

        _ = (dbus.mainloop.glib, dbus.service, GLib)
        return True, None
    except ImportError as exc:
        return False, str(exc)


def _discover_linux_python_module_roots() -> list[str]:
    python_bin = Path("/usr/bin/python3")
    if not python_bin.exists():
        return []

    try:
        result = subprocess.run(
            [
                str(python_bin),
                "-c",
                (
                    "import importlib, os\n"
                    "roots = []\n"
                    "for name in ('dbus', 'gi'):\n"
                    "    try:\n"
                    "        module = importlib.import_module(name)\n"
                    "    except Exception:\n"
                    "        continue\n"
                    "    path = getattr(module, '__file__', None)\n"
                    "    if not path:\n"
                    "        continue\n"
                    "    root = os.path.dirname(os.path.dirname(path))\n"
                    "    if root not in roots:\n"
                    "        roots.append(root)\n"
                    "print('\\n'.join(roots))\n"
                ),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return []

    roots = []
    for line in result.stdout.splitlines():
        root = line.strip()
        if root and root not in roots:
            roots.append(root)
    return roots


def _ensure_linux_mpris_runtime() -> tuple[bool, Optional[str]]:
    if sys.platform != "linux":
        return True, None

    ready, reason = _can_import_linux_mpris_runtime()
    if ready:
        return True, None

    added = False
    for root in reversed(_discover_linux_python_module_roots()):
        if root and root not in sys.path:
            sys.path.insert(0, root)
            added = True

    if added:
        importlib.invalidate_caches()

    return _can_import_linux_mpris_runtime()


class Bootstrap:
    """
    Dependency injection container.

    Creates and manages all application components with proper
    dependency injection for loose coupling.
    """

    _instance: Optional["Bootstrap"] = None
    _lock = threading.Lock()

    def __init__(self, db_path: str = "Harmony.db"):
        """Initialize bootstrap container."""
        self._db_path = db_path

        # Core infrastructure
        self._db: Optional[DatabaseManager] = None
        self._config: Optional[ConfigManager] = None
        self._event_bus: Optional[EventBus] = None
        self._http_client: Optional[HttpClient] = None
        self._theme: Optional["ThemeManager"] = None

        # Repositories
        self._track_repo: Optional[SqliteTrackRepository] = None
        self._playlist_repo: Optional[SqlitePlaylistRepository] = None
        self._cloud_repo: Optional[SqliteCloudRepository] = None
        self._queue_repo: Optional[SqliteQueueRepository] = None
        self._favorite_repo: Optional[SqliteFavoriteRepository] = None
        self._history_repo: Optional[SqliteHistoryRepository] = None
        self._album_repo: Optional[SqliteAlbumRepository] = None
        self._artist_repo: Optional[SqliteArtistRepository] = None
        self._genre_repo: Optional[SqliteGenreRepository] = None
        self._settings_repo: Optional[SqliteSettingsRepository] = None

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
        self._online_download_service: Optional["OnlineDownloadGateway"] = None

        # Services
        self._cache_cleaner_service: Optional["CacheCleanerService"] = None
        self._sleep_timer_service: Optional["SleepTimerService"] = None
        self._mpris_controller: Optional["MPRISController"] = None
        self._mpris_disabled_reason: Optional[str] = None
        self._plugin_manager: Optional[PluginManager] = None
        self._plugins_loaded = False

    @classmethod
    def instance(cls, db_path: str = "Harmony.db") -> "Bootstrap":
        """Get singleton instance."""
        with cls._lock:
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
            self._config = ConfigManager(settings_repo=self.settings_repo)
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

    @property
    def theme(self) -> "ThemeManager":
        """Get theme manager."""
        if self._theme is None:
            from system.theme import ThemeManager
            self._theme = ThemeManager.instance(self.config)
        return self._theme

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

    @property
    def album_repo(self) -> SqliteAlbumRepository:
        """Get album repository."""
        if self._album_repo is None:
            self._album_repo = SqliteAlbumRepository(self._db_path, db_manager=self.db)
        return self._album_repo

    @property
    def artist_repo(self) -> SqliteArtistRepository:
        """Get artist repository."""
        if self._artist_repo is None:
            self._artist_repo = SqliteArtistRepository(self._db_path, db_manager=self.db)
        return self._artist_repo

    @property
    def genre_repo(self) -> SqliteGenreRepository:
        """Get genre repository."""
        if self._genre_repo is None:
            self._genre_repo = SqliteGenreRepository(self._db_path, db_manager=self.db)
        return self._genre_repo

    @property
    def settings_repo(self) -> SqliteSettingsRepository:
        """Get settings repository."""
        if self._settings_repo is None:
            self._settings_repo = SqliteSettingsRepository(self._db_path, db_manager=self.db)
        return self._settings_repo

    # ===== Services =====

    @property
    def playback_service(self) -> PlaybackService:
        """Get playback service."""
        if self._playback_service is None:
            self._playback_service = PlaybackService(
                config_manager=self.config,
                cover_service=self.cover_service,
                online_download_service=self.online_download_service,
                event_bus=self.event_bus,
                track_repo=self.track_repo,
                favorite_repo=self.favorite_repo,
                queue_repo=self.queue_repo,
                cloud_repo=self.cloud_repo,
                history_repo=self.history_repo,
                album_repo=self.album_repo,
                artist_repo=self.artist_repo,
            )
            from services.download.download_manager import DownloadManager
            DownloadManager.instance().set_dependencies(
                config=self.config,
                playback_service=self._playback_service,
                cloud_repo=self.cloud_repo,
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
                track_repo=self.track_repo,
            )
        return self._queue_service

    @property
    def library_service(self) -> LibraryService:
        """Get library service."""
        if self._library_service is None:
            self._library_service = LibraryService(
                track_repo=self.track_repo,
                playlist_repo=self.playlist_repo,
                album_repo=self.album_repo,
                artist_repo=self.artist_repo,
                genre_repo=self.genre_repo,
                event_bus=self.event_bus,
                cover_service=self.cover_service,
            )
            # Initialize albums/artists tables if needed
            self._library_service.init_albums_artists()
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
                track_repo=self.track_repo,
                event_bus=self.event_bus,
            )
        return self._playlist_service

    @property
    def cloud_account_service(self) -> CloudAccountService:
        """Get cloud account service."""
        if self._cloud_account_service is None:
            self._cloud_account_service = CloudAccountService(
                cloud_repo=self.cloud_repo,
                event_bus=self.event_bus,
            )
        return self._cloud_account_service

    @property
    def cloud_file_service(self) -> CloudFileService:
        """Get cloud file service."""
        if self._cloud_file_service is None:
            self._cloud_file_service = CloudFileService(
                cloud_repo=self.cloud_repo,
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
                cloud_repo=self.cloud_repo,
                event_bus=self.event_bus,
                queue_repo=self.queue_repo,
            )
        return self._file_org_service

    @property
    def plugin_manager(self) -> PluginManager:
        """Get plugin manager."""
        if self._plugin_manager is None:
            logger.info("[Bootstrap] Initializing plugin manager")
            self._plugin_manager = PluginManager(
                builtin_root=Path("plugins/builtin"),
                external_root=Path("data/plugins/external"),
                state_store=PluginStateStore(Path("data/plugins/state.json")),
                context_factory=BootstrapPluginContextFactory(
                    self,
                    storage_root=Path("data/plugins/storage"),
                ),
            )
        if not self._plugins_loaded:
            logger.info("[Bootstrap] Loading enabled plugins")
            self._plugin_manager.load_enabled_plugins()
            self._plugins_loaded = True
            logger.info("[Bootstrap] Plugin loading finished")
        return self._plugin_manager

    def refresh_online_download_service(self) -> "OnlineDownloadGateway":
        """Force refresh of host online download gateway."""
        self._online_download_service = None
        return self.online_download_service

    # ===== Online Music =====

    @property
    def online_download_service(self) -> "OnlineDownloadGateway":
        """Get host online download gateway."""
        if self._online_download_service is None:
            from services.download.online_download_gateway import OnlineDownloadGateway
            self._online_download_service = OnlineDownloadGateway(
                config_manager=self.config,
                plugin_manager=lambda: self._plugin_manager,
                event_bus=self.event_bus,
            )
        return self._online_download_service

    @property
    def cache_cleaner_service(self) -> "CacheCleanerService":
        """Get cache cleaner service."""
        if self._cache_cleaner_service is None:
            from services.download.cache_cleaner_service import CacheCleanerService
            self._cache_cleaner_service = CacheCleanerService(
                config_manager=self.config,
                download_service=self.online_download_service,
                event_bus=self.event_bus,
                queue_service=self.queue_service
            )
        return self._cache_cleaner_service

    @property
    def sleep_timer_service(self) -> "SleepTimerService":
        """Get sleep timer service."""
        if self._sleep_timer_service is None:
            from services.playback.sleep_timer_service import SleepTimerService
            self._sleep_timer_service = SleepTimerService(
                playback_service=self.playback_service,
                event_bus=self.event_bus
            )
        return self._sleep_timer_service

    @property
    def mpris_controller(self) -> "MPRISController":
        """Get MPRIS D-Bus controller (Linux only)."""
        if self._mpris_controller is None:
            if sys.platform == "linux":
                if self._mpris_disabled_reason is not None:
                    return None
                ready, reason = _ensure_linux_mpris_runtime()
                if not ready:
                    self._mpris_disabled_reason = reason or "unknown import error"
                    logger.warning(
                        "MPRIS disabled: missing Linux D-Bus runtime (%s). "
                        "Install the optional 'linux' dependencies and ensure system "
                        "PyGObject bindings are available to the application.",
                        self._mpris_disabled_reason,
                    )

                if ready:
                    from system.mpris import MPRISController
                    self._mpris_controller = MPRISController(
                        playback_service=self.playback_service,
                    )
        return self._mpris_controller

    def start_mpris(self, main_window=None, ui_dispatcher=None):
        """
        Start MPRIS D-Bus service (Linux only).

        Args:
            main_window: Main window instance for Raise/Quit support
        """
        import sys
        if sys.platform == "linux":
            controller = self.mpris_controller  # Access property to trigger lazy init
            if controller is not None:
                controller._main_window = main_window
                controller.ui_dispatcher = ui_dispatcher
                controller.start()

    def stop_mpris(self):
        """Stop MPRIS D-Bus service."""
        if self._mpris_controller is not None:
            self._mpris_controller.stop()

    def shutdown_database(self):
        """Flush and close the shared database manager if it has been initialized."""
        db = self._db
        if db is None:
            return

        write_worker = getattr(db, "_write_worker", None)
        if write_worker is not None:
            try:
                write_worker.wait_idle()
            except Exception:
                logger.exception("[Bootstrap] Failed waiting for DB write worker to go idle")

        try:
            db.close()
        except Exception:
            logger.exception("[Bootstrap] Failed closing database manager")
