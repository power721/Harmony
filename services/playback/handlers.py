"""
Playback handlers - Internal classes for handling different track sources.

These classes are used internally by PlaybackService and should not be
imported directly. They handle the specific logic for local, cloud, and
online track playback.
"""

import logging
import threading
from pathlib import Path
from typing import Optional, List, TYPE_CHECKING

from PySide6.QtCore import QObject, Signal, Qt, QThread

from domain import PlaylistItem
from domain.playback import PlayMode
from domain.track import Track, TrackSource

if TYPE_CHECKING:
    from domain import CloudFile, CloudAccount
    from infrastructure.audio import PlayerEngine
    from infrastructure.database import DatabaseManager
    from system.config import ConfigManager
    from services.metadata import CoverService
    from services.online import OnlineDownloadService

logger = logging.getLogger(__name__)


class LocalTrackHandler:
    """
    Handles local track playback operations.

    This class encapsulates all logic for playing local files,
    including playlists and favorites.
    """

    def __init__(
        self,
        engine: "PlayerEngine",
        db_manager: "DatabaseManager",
        config_manager: "ConfigManager",
        set_source_callback,
        save_queue_callback,
    ):
        """
        Initialize local track handler.

        Args:
            engine: Player engine for playback control
            db_manager: Database manager for track data
            config_manager: Configuration manager for settings
            set_source_callback: Callback to set playback source
            save_queue_callback: Callback to save queue
        """
        self._engine = engine
        self._db = db_manager
        self._config = config_manager
        self._set_source = set_source_callback
        self._save_queue = save_queue_callback

    def play_track(self, track_id: int):
        """
        Play a local track by ID.

        Handles both local files and online tracks (QQ Music).
        Online tracks (empty path) will be downloaded before playback.

        Args:
            track_id: Database track ID
        """
        track = self._db.get_track(track_id)
        if not track:
            logger.error(f"[LocalTrackHandler] Track not found: {track_id}")
            return

        # Check if this is an online track (empty path)
        is_online_track = not track.path or track.source == TrackSource.QQ

        # For local tracks with path, verify file exists
        if not is_online_track and not Path(track.path).exists():
            logger.error(f"[LocalTrackHandler] File not found: {track.path}")
            return

        self._set_source("local")

        # Clear playlist and load library
        self._engine.clear_playlist()
        self._engine.cleanup_temp_files()

        tracks = self._db.get_all_tracks()
        items = []
        start_index = 0

        for t in tracks:
            if t.id and t.id > 0:
                # Include online tracks (empty path) and existing local files
                t_is_online = not t.path or t.source == TrackSource.QQ
                if t_is_online or Path(t.path).exists():
                    item = PlaylistItem.from_track(t)
                    if t.id == track_id:
                        start_index = len(items)
                    items.append(item)

        self._engine.load_playlist_items(items)

        # If in shuffle mode, shuffle the playlist with the target track at front
        if self._engine.is_shuffle_mode() and 0 <= start_index < len(items):
            self._engine.shuffle_and_play(items[start_index])
            self._engine.play_at(0)
        else:
            self._engine.play_at(start_index)

        # Save queue and state
        self._save_queue()
        self._config.set_current_track_id(track_id)
        self._config.set_playback_source("local")

    def play_tracks(self, track_ids: List[int], start_index: int = 0):
        """
        Play multiple local tracks.

        Handles both local files and online tracks.

        Args:
            track_ids: List of track IDs
            start_index: Index to start playback from
        """
        self._set_source("local")
        self._engine.clear_playlist()

        items = []
        for track_id in track_ids:
            track = self._db.get_track(track_id)
            if track:
                # Include online tracks (empty path) and existing local files
                is_online = not track.path or track.source == TrackSource.QQ
                if is_online or Path(track.path).exists():
                    items.append(PlaylistItem.from_track(track))

        self._engine.load_playlist_items(items)

        if self._engine.is_shuffle_mode() and 0 <= start_index < len(items):
            self._engine.shuffle_and_play(items[start_index])
            self._engine.play_at(0)
        elif items:
            self._engine.play_at(min(start_index, len(items) - 1))

        self._save_queue()
        self._config.set_playback_source("local")

    def play_library(self):
        """Play all tracks in the library."""
        self._set_source("local")

        tracks = self._db.get_all_tracks()
        items = []

        for t in tracks:
            if t.id and t.id > 0:
                # Include online tracks (empty path) and existing local files
                is_online = not t.path or t.source == TrackSource.QQ
                if is_online or Path(t.path).exists():
                    items.append(PlaylistItem.from_track(t))

        self._engine.load_playlist_items(items)

        if self._engine.is_shuffle_mode() and items:
            self._engine.shuffle_and_play()
            self._engine.play_at(0)
        else:
            self._engine.play()

    def load_playlist(self, playlist_id: int):
        """
        Load a playlist from the database.

        Args:
            playlist_id: Playlist ID
        """
        logger.debug(f"[LocalTrackHandler] Loading playlist: {playlist_id}")

        tracks = self._db.get_playlist_tracks(playlist_id)
        items = []

        for track in tracks:
            if track.id and track.id > 0:
                # Include online tracks (empty path) and existing local files
                is_online = not track.path or track.source == TrackSource.QQ
                if is_online or Path(track.path).exists():
                    items.append(PlaylistItem.from_track(track))

        self._engine.load_playlist_items(items)

        if self._engine.is_shuffle_mode() and items:
            self._engine.shuffle_and_play()

    def play_playlist_track(self, playlist_id: int, track_id: int):
        """
        Play a specific track from a playlist.

        Args:
            playlist_id: Playlist ID
            track_id: Track ID to play
        """
        self._set_source("local")

        tracks = self._db.get_playlist_tracks(playlist_id)
        items = []
        start_index = 0

        for track in tracks:
            if track.id and track.id > 0:
                # Include online tracks (empty path) and existing local files
                is_online = not track.path or track.source == TrackSource.QQ
                if is_online or Path(track.path).exists():
                    item = PlaylistItem.from_track(track)
                    if track.id == track_id:
                        start_index = len(items)
                    items.append(item)

        self._engine.load_playlist_items(items)

        if self._engine.is_shuffle_mode() and 0 <= start_index < len(items):
            self._engine.shuffle_and_play(items[start_index])
            self._engine.play_at(0)
        else:
            self._engine.play_at(start_index)

        self._save_queue()
        self._config.set_current_track_id(track_id)
        self._config.set_playback_source("local")

    def load_favorites(self):
        """Load all favorite tracks."""
        tracks = self._db.get_favorites()
        items = []

        for track in tracks:
            if track.id:
                # Include online tracks (empty path) and existing local files
                is_online = not track.path or track.source == TrackSource.QQ
                if is_online or Path(track.path).exists():
                    items.append(PlaylistItem.from_track(track))

        self._engine.load_playlist_items(items)

        if self._engine.is_shuffle_mode() and items:
            self._engine.shuffle_and_play()


class CloudTrackHandler:
    """
    Handles cloud track playback operations.

    This class encapsulates all logic for playing files from
    cloud storage (Quark, Baidu).
    """

    def __init__(
        self,
        engine: "PlayerEngine",
        db_manager: "DatabaseManager",
        config_manager: "ConfigManager",
        cover_service: Optional["CoverService"],
        set_source_callback,
        save_queue_callback,
        metadata_processed_signal,
    ):
        """
        Initialize cloud track handler.

        Args:
            engine: Player engine for playback control
            db_manager: Database manager for track data
            config_manager: Configuration manager for settings
            cover_service: Cover service for album art
            set_source_callback: Callback to set playback source
            save_queue_callback: Callback to save queue
            metadata_processed_signal: Signal to emit when metadata is processed
        """
        self._engine = engine
        self._db = db_manager
        self._config = config_manager
        self._cover_service = cover_service
        self._set_source = set_source_callback
        self._save_queue = save_queue_callback
        self._metadata_processed = metadata_processed_signal

        # State
        self._cloud_account: Optional["CloudAccount"] = None
        self._cloud_files: List["CloudFile"] = []
        self._downloaded_files: dict = {}  # cloud_file_id -> local_path

    @property
    def cloud_account(self) -> Optional["CloudAccount"]:
        """Get current cloud account."""
        return self._cloud_account

    @cloud_account.setter
    def cloud_account(self, account: Optional["CloudAccount"]):
        """Set current cloud account."""
        self._cloud_account = account

    @property
    def cloud_files(self) -> List["CloudFile"]:
        """Get current cloud files list."""
        return self._cloud_files

    @cloud_files.setter
    def cloud_files(self, files: List["CloudFile"]):
        """Set current cloud files list."""
        self._cloud_files = files

    @property
    def downloaded_files(self) -> dict:
        """Get downloaded files cache."""
        return self._downloaded_files

    def get_cached_path(self, file_id: str) -> str:
        """Get cached local path for a cloud file."""
        return self._downloaded_files.get(file_id, "")

    def play_track(
        self,
        cloud_file: "CloudFile",
        account: "CloudAccount",
        cloud_files: List["CloudFile"] = None
    ):
        """
        Play a cloud file.

        Args:
            cloud_file: CloudFile to play
            account: CloudAccount for authentication
            cloud_files: Optional list of all cloud files for playlist
        """
        self._cloud_account = account
        self._cloud_files = cloud_files or [cloud_file]
        self._set_source("cloud")

        # Build playlist items
        items = []
        start_index = 0

        for i, cf in enumerate(self._cloud_files):
            local_path = self.get_cached_path(cf.file_id)
            item = PlaylistItem.from_cloud_file(cf, account.id, local_path, provider=account.provider)
            if cf.file_id == cloud_file.file_id:
                start_index = i
            items.append(item)

        self._engine.load_playlist_items(items)

        if self._engine.is_shuffle_mode() and 0 <= start_index < len(items):
            self._engine.shuffle_and_play(items[start_index])
            self._engine.play_at(0)
        else:
            self._engine.play_at(start_index)

        self._config.set_playback_source("cloud")
        self._config.set_cloud_account_id(account.id)

    def play_playlist(
        self,
        cloud_files: List["CloudFile"],
        start_index: int,
        account: "CloudAccount",
        first_file_path: str = "",
        start_position: float = 0.0
    ):
        """
        Play a cloud file playlist.

        Args:
            cloud_files: List of CloudFile objects
            start_index: Index to start playback from
            account: CloudAccount for authentication
            first_file_path: Optional local path for the first file (if already downloaded)
            start_position: Optional position to start from (in seconds)
        """
        self._cloud_account = account
        self._cloud_files = cloud_files
        self._set_source("cloud")

        # Build playlist items - fast path, no blocking operations
        items = []
        files_to_process = []  # Files that need background metadata processing

        for i, cf in enumerate(cloud_files):
            local_path = ""
            if i == start_index and first_file_path:
                local_path = first_file_path
                self._downloaded_files[cf.file_id] = local_path
            else:
                local_path = self.get_cached_path(cf.file_id)

            item = PlaylistItem.from_cloud_file(cf, account.id, local_path, provider=account.provider)

            # For already downloaded files, try fast path first
            if local_path:
                # Try to get existing track record (fast DB lookup)
                track = self._db.get_track_by_cloud_file_id(cf.file_id)
                if track:
                    item.track_id = track.id
                    item.title = track.title or item.title
                    item.artist = track.artist or item.artist
                    item.album = track.album or item.album
                    item.duration = track.duration or item.duration
                    item.cover_path = track.cover_path
                    item.needs_metadata = False
                else:
                    # No existing record - defer metadata extraction to background
                    files_to_process.append((cf.file_id, local_path, account.provider))
                    item.needs_metadata = True

            items.append(item)

        # Start playback immediately
        self._engine.load_playlist_items(items)

        if self._engine.is_shuffle_mode() and 0 <= start_index < len(items):
            self._engine.shuffle_and_play(items[start_index])
            start_index = 0

        # Start playback
        if start_position > 0:
            position_ms = int(start_position * 1000)
            self._engine.play_at_with_position(start_index, position_ms)
        else:
            self._engine.play_at(start_index)

        self._save_queue()
        self._config.set_playback_source("cloud")
        self._config.set_cloud_account_id(account.id)

        # Process metadata in background thread
        if files_to_process:
            self._process_metadata_async(files_to_process)

    def on_file_downloaded(self, cloud_file_id: str, local_path: str, online_handler=None):
        """
        Called when a cloud file has been downloaded.

        Args:
            cloud_file_id: Cloud file ID
            local_path: Local path of downloaded file
            online_handler: Optional online handler to check for QQ Music tracks
        """
        # Skip if this is an online track (QQ Music)
        if online_handler:
            current_item = self._engine.current_playlist_item
            if current_item and current_item.source == TrackSource.QQ:
                logger.debug(f"[CloudTrackHandler] Skipping for online track")
                return

        self._downloaded_files[cloud_file_id] = local_path

        # Update cloud_files table with local_path
        if self._cloud_account:
            self._db.update_cloud_file_local_path(
                cloud_file_id, self._cloud_account.id, local_path
            )

        # Determine provider
        provider = self._cloud_account.provider if self._cloud_account else "quark"

        # Process metadata in background thread
        self._process_metadata_async([(cloud_file_id, local_path, provider)])

    def download_track(self, item: PlaylistItem):
        """Download a cloud track."""
        from services.cloud.download_service import CloudDownloadService

        if not self._cloud_account:
            if item.cloud_account_id:
                self._cloud_account = self._db.get_cloud_account(item.cloud_account_id)
                if not self._cloud_account:
                    return
            else:
                return

        service = CloudDownloadService.instance()
        service.set_download_dir(self._config.get_cloud_download_dir())

        # Find the CloudFile
        cloud_file = None
        for cf in self._cloud_files:
            if cf.file_id == item.cloud_file_id:
                cloud_file = cf
                break

        if not cloud_file:
            cloud_file = self._db.get_cloud_file_by_file_id(item.cloud_file_id)
            if not cloud_file:
                logger.error(f"[CloudTrackHandler] CloudFile not found: {item.cloud_file_id}")
                return

        if cloud_file:
            service.download_file(cloud_file, self._cloud_account)

    def preload_track(self, item: PlaylistItem):
        """Preload a cloud track."""
        from services.cloud.download_service import CloudDownloadService

        # Skip if already downloaded
        if item.local_path:
            return

        service = CloudDownloadService.instance()
        if service.is_downloading(item.cloud_file_id):
            return

        # Find the CloudFile
        cloud_file = None
        for cf in self._cloud_files:
            if cf.file_id == item.cloud_file_id:
                cloud_file = cf
                break

        if not cloud_file:
            cloud_file = self._db.get_cloud_file_by_file_id(item.cloud_file_id)

        if not cloud_file:
            return

        # Get cloud account if needed
        account = self._cloud_account
        if not account and item.cloud_account_id:
            account = self._db.get_cloud_account(item.cloud_account_id)

        if not account:
            return

        # Start preload
        logger.info(f"[CloudTrackHandler] Preloading cloud track: {item.title}")
        service.set_download_dir(self._config.get_cloud_download_dir())
        service.download_file(cloud_file, account)

    def _process_metadata_async(self, files: List[tuple]):
        """Process metadata in background thread."""
        import threading

        def process():
            for file_id, local_path, provider in files:
                try:
                    self._save_to_library(file_id, local_path, provider)
                except Exception as e:
                    logger.error(f"[CloudTrackHandler] Error processing metadata: {e}")

        thread = threading.Thread(target=process, daemon=True)
        thread.start()

    def _save_to_library(self, file_id: str, local_path: str, source: TrackSource = None) -> str:
        """
        Save downloaded cloud track to library with metadata and cover art.
        """
        from services.metadata.metadata_service import MetadataService
        from services.lyrics.lyrics_service import LyricsService
        from utils.helpers import is_filename_like

        # Determine source if not provided
        if source is None:
            if self._cloud_account:
                provider = self._cloud_account.provider.lower()
                if provider == "quark":
                    source = TrackSource.QUARK
                elif provider == "baidu":
                    source = TrackSource.BAIDU
                else:
                    source = TrackSource.LOCAL
            else:
                current_item = self._engine.current_playlist_item
                if current_item and current_item.cloud_file_id == file_id:
                    source = current_item.source
                else:
                    source = TrackSource.QQ

        # Extract metadata from downloaded file
        metadata = MetadataService.extract_metadata(local_path)
        new_title = metadata.get("title", Path(local_path).stem if local_path else "")
        new_artist = metadata.get("artist", "")
        new_album = metadata.get("album", "")
        new_duration = metadata.get("duration", 0)

        # Check if track already exists
        existing = self._db.get_track_by_cloud_file_id(file_id)
        if existing:
            if not existing.path or existing.path != local_path:
                self._db.update_track_path(existing.id, local_path)
                logger.info(f"[CloudTrackHandler] Updated track {existing.id} path: {local_path}")

            needs_update = False
            if is_filename_like(existing.title) or not existing.artist:
                needs_update = True

            if needs_update and (new_artist or not is_filename_like(new_title)):
                self._db.update_track(
                    existing.id,
                    title=new_title if not is_filename_like(new_title) else None,
                    artist=new_artist if new_artist else None,
                    album=new_album if new_album else None,
                )
                logger.info(f"[CloudTrackHandler] Updated track {existing.id} metadata")

                if LyricsService.lyrics_file_exists(local_path):
                    LyricsService.delete_lyrics(local_path)

            if not existing.cover_path and self._cover_service:
                cover_path = self._fetch_cover(new_title, new_artist, new_album, new_duration, local_path)
                if cover_path:
                    self._db.update_track_cover_path(existing.id, cover_path)
                    return cover_path

            return existing.cover_path

        existing_by_path = self._db.get_track_by_path(local_path)
        if existing_by_path:
            self._db.update_track(existing_by_path.id, cloud_file_id=file_id)

            if is_filename_like(existing_by_path.title) or not existing_by_path.artist:
                if new_artist or not is_filename_like(new_title):
                    self._db.update_track(
                        existing_by_path.id,
                        title=new_title if not is_filename_like(new_title) else None,
                        artist=new_artist if new_artist else None,
                        album=new_album if new_album else None,
                    )

            if not existing_by_path.cover_path and self._cover_service:
                cover_path = self._fetch_cover(new_title, new_artist, new_album, new_duration, local_path)
                if cover_path:
                    self._db.update_track_cover_path(existing_by_path.id, cover_path)
                    return cover_path

            return existing_by_path.cover_path

        # Create new track
        title = new_title
        artist = new_artist
        album = new_album
        duration = new_duration
        cover_path = None

        # Fetch cover
        if self._cover_service:
            cover_path = self._fetch_cover(title, artist, album, duration, local_path)

        track = Track(
            path=local_path,
            title=title,
            artist=artist,
            album=album,
            duration=duration,
            cover_path=cover_path,
            cloud_file_id=file_id,
            source=source,
        )

        track_id = self._db.add_track(track)
        logger.info(f"[CloudTrackHandler] Added new track {track_id}: {title} - {artist}")

        return cover_path

    def _fetch_cover(self, title: str, artist: str, album: str, duration: float, local_path: str) -> Optional[str]:
        """Fetch cover for a track."""
        if not self._cover_service:
            return None

        try:
            return self._cover_service.get_cover(
                track_path=local_path,
                title=title,
                artist=artist,
                album=album,
                duration=duration,
            )
        except Exception as e:
            logger.error(f"[CloudTrackHandler] Error fetching cover: {e}")
            return None


class OnlineTrackHandler(QObject):
    """
    Handles online track (QQ Music) playback operations.

    This class encapsulates all logic for playing tracks from
    online music services.
    """

    def __init__(
        self,
        engine: "PlayerEngine",
        db_manager: "DatabaseManager",
        config_manager: "ConfigManager",
        cover_service: Optional["CoverService"],
        online_download_service: Optional["OnlineDownloadService"],
        get_cloud_account_callback,
        save_queue_callback,
    ):
        """
        Initialize online track handler.

        Args:
            engine: Player engine for playback control
            db_manager: Database manager for track data
            config_manager: Configuration manager for settings
            cover_service: Cover service for album art
            online_download_service: Service for downloading online tracks
            get_cloud_account_callback: Callback to get current cloud account
            save_queue_callback: Callback to save queue
        """
        super().__init__()
        self._engine = engine
        self._db = db_manager
        self._config = config_manager
        self._cover_service = cover_service
        self._online_download_service = online_download_service
        self._get_cloud_account = get_cloud_account_callback
        self._save_queue = save_queue_callback

        # Online download workers (song_mid -> QThread)
        self._download_workers: dict = {}
        self._download_lock = threading.Lock()

    def download_track(self, item: PlaylistItem):
        """Download an online track."""
        song_mid = item.cloud_file_id
        worker = None

        # Check if already downloading this song
        with self._download_lock:
            if song_mid in self._download_workers:
                existing = self._download_workers[song_mid]
                if existing.isRunning():
                    logger.info(f"[OnlineTrackHandler] Already downloading: {song_mid}")
                    return
                else:
                    del self._download_workers[song_mid]
                    existing.deleteLater()

            if not self._online_download_service:
                logger.error("[OnlineTrackHandler] Online download service not available")
                self._engine.play_next()
                return

            logger.info(f"[OnlineTrackHandler] Downloading online track: {song_mid}")

            # Create worker
            worker = self._create_download_worker(song_mid, item.title)

            # Store in dict before starting
            self._download_workers[song_mid] = worker

        # Start worker outside lock
        worker.start()

    def _create_download_worker(self, song_mid: str, title: str) -> QThread:
        """Create a download worker thread."""
        class OnlineDownloadWorker(QThread):
            download_finished = Signal(str, str)  # (song_mid, local_path)

            def __init__(self, service, song_mid, title):
                super().__init__()
                self._service = service
                self._song_mid = song_mid
                self._title = title

            def run(self):
                path = self._service.download(self._song_mid, self._title)
                self.download_finished.emit(self._song_mid, path or "")

        worker = OnlineDownloadWorker(
            self._online_download_service,
            song_mid,
            title
        )

        # Handle download result
        def on_download_finished(mid, path):
            self.on_track_downloaded(mid, path)

        # Clean up worker ONLY after thread has fully stopped
        def on_thread_finished():
            with self._download_lock:
                if song_mid in self._download_workers:
                    worker_obj = self._download_workers.pop(song_mid)
                    worker_obj.deleteLater()

        # Connect signals - use AutoConnection (default) for thread safety
        worker.download_finished.connect(on_download_finished)
        worker.finished.connect(on_thread_finished)
        return worker

    def preload_track(self, item: PlaylistItem):
        """Preload an online track."""
        if item.local_path:
            return

        song_mid = item.cloud_file_id
        with self._download_lock:
            if song_mid in self._download_workers and self._download_workers[song_mid].isRunning():
                return

        logger.info(f"[OnlineTrackHandler] Preloading online track: {item.title}")
        self.download_track(item)

    def on_track_downloaded(self, song_mid: str, local_path: str):
        """
        Called when an online track has been downloaded.

        Args:
            song_mid: Song MID
            local_path: Local path of downloaded file (empty if failed)
        """
        if not local_path:
            logger.warning(f"[OnlineTrackHandler] Download failed: {song_mid}")
            # Only skip if this was the current track (not a preloaded next track)
            current_item = self._engine.current_playlist_item
            if current_item and current_item.cloud_file_id == song_mid:
                logger.warning(f"[OnlineTrackHandler] Current track failed to download, skipping: {song_mid}")
                self._engine.remove_playlist_item_by_cloud_id(song_mid)
                self._engine.play_next()
            else:
                logger.info(f"[OnlineTrackHandler] Pre-download failed for next track: {song_mid} (current track not affected)")
                self._engine.remove_playlist_item_by_cloud_id(song_mid)
            return

        logger.info(f"[OnlineTrackHandler] Track downloaded: {song_mid} -> {local_path}")

        # Save to library and get track_id
        track_id = self._save_to_library(song_mid, local_path)

        # Update playlist item in engine
        track = None
        if track_id:
            track = self._db.get_track(track_id)

        if track:
            updated_index = self._engine.update_playlist_item(
                cloud_file_id=song_mid,
                local_path=local_path,
                track_id=track.id,
                title=track.title,
                artist=track.artist,
                album=track.album,
                duration=track.duration,
                needs_download=False,
                needs_metadata=False,
                expected_index=self._engine.current_index
            )
        else:
            updated_index = self._engine.update_playlist_item(
                cloud_file_id=song_mid,
                local_path=local_path,
                needs_download=False,
                expected_index=self._engine.current_index
            )

        # Play if this is current track
        if updated_index is not None and updated_index == self._engine.current_index:
            self._engine.play_after_download(updated_index, local_path)

    def _save_to_library(self, song_mid: str, local_path: str) -> Optional[int]:
        """Save downloaded online track to library."""
        from services.metadata.metadata_service import MetadataService
        from services.lyrics.lyrics_service import LyricsService
        from utils.helpers import is_filename_like

        if not local_path or not Path(local_path).exists():
            return None

        # Check if track already exists by cloud_file_id (song_mid)
        existing = self._db.get_track_by_cloud_file_id(song_mid)
        if existing:
            self._db.update_track_path(existing.id, local_path)
            logger.info(f"[OnlineTrackHandler] Updated track {existing.id} with local path")
            return existing.id

        existing_by_path = self._db.get_track_by_path(local_path)
        if existing_by_path:
            self._db.update_track(existing_by_path.id, cloud_file_id=song_mid)
            return existing_by_path.id

        # Extract metadata
        metadata = MetadataService.extract_metadata(local_path)
        title = metadata.get("title", Path(local_path).stem)
        artist = metadata.get("artist", "")
        album = metadata.get("album", "")
        duration = metadata.get("duration", 0)

        # Fetch cover
        cover_path = None
        if self._cover_service:
            try:
                cover_path = self._cover_service.get_cover(
                    track_path=local_path,
                    title=title,
                    artist=artist,
                    album=album,
                    duration=duration,
                )
            except Exception as e:
                logger.error(f"[OnlineTrackHandler] Error fetching cover: {e}")

        track = Track(
            path=local_path,
            title=title,
            artist=artist,
            album=album,
            duration=duration,
            cover_path=cover_path,
            cloud_file_id=song_mid,
            source=TrackSource.QQ,
        )

        track_id = self._db.add_track(track)
        logger.info(f"[OnlineTrackHandler] Added new track {track_id}: {title} - {artist}")

        return track_id

    def cleanup_workers(self):
        """Clean up all download workers."""
        logger.info("[OnlineTrackHandler] Cleaning up download workers")
        with self._download_lock:
            for song_mid, worker in list(self._download_workers.items()):
                if worker.isRunning():
                    worker.requestInterruption()
                    worker.quit()
                    if not worker.wait(1000):
                        worker.terminate()
                    worker.deleteLater()
            self._download_workers.clear()
