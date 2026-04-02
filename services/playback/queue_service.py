"""
Queue service - Manages playback queue persistence.
"""

import logging
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

from domain import PlaylistItem
from domain.playback import PlayMode
from domain.track import TrackSource
from infrastructure.audio import PlayerEngine
from repositories.queue_repository import SqliteQueueRepository

if TYPE_CHECKING:
    from repositories.track_repository import SqliteTrackRepository

logger = logging.getLogger(__name__)


class QueueService:
    """
    Manages playback queue persistence and restoration.
    """

    def __init__(
            self,
            queue_repo: SqliteQueueRepository,
            config_manager,
            engine: PlayerEngine,
            track_repo: Optional["SqliteTrackRepository"] = None,
    ):
        self._queue_repo = queue_repo
        self._config = config_manager
        self._engine = engine
        self._track_repo = track_repo

    def save(self):
        """Save the current play queue to database."""
        items = self._engine.playlist_items
        if not items:
            self.clear()
            return

        current_idx = self._engine.current_index

        # Convert to PlayQueueItem list
        queue_items = []
        for i, item in enumerate(items):
            queue_item = item.to_play_queue_item(i)
            queue_items.append(queue_item)

        self._queue_repo.save(queue_items)

        # Save current index and play mode
        self._config.set("queue_current_index", current_idx)
        self._config.set("queue_play_mode", self._engine.play_mode.value)

        logger.debug(f"[QueueService] Saved queue: {len(queue_items)} items, index={current_idx}")

    def restore(self) -> bool:
        """
        Restore the play queue from database.

        Returns:
            True if queue was restored successfully
        """
        queue_items = self._queue_repo.load()
        if not queue_items:
            return False

        # Convert to PlaylistItem list (pure conversion, no DB access)
        items = [PlaylistItem.from_play_queue_item(item) for item in queue_items]

        # Enrich metadata from track repository (batch)
        if self._track_repo:
            items = self._enrich_metadata_batch(items)

        # Get saved index and play mode
        saved_index = self._config.get("queue_current_index", 0)
        saved_mode = self._config.get("queue_play_mode", PlayMode.SEQUENTIAL.value)

        # Clamp index to valid range
        if saved_index < 0 or saved_index >= len(items):
            saved_index = 0

        # Load queue into engine
        self._engine.load_playlist_items(items)

        # Restore play mode
        try:
            mode = PlayMode(saved_mode)
            self._engine.restore_state(mode, saved_index)
        except ValueError:
            pass

        # Load track at saved index (but don't play)
        if 0 <= saved_index < len(items):
            self._engine.load_track_at(saved_index)

        return True

    def _enrich_metadata(self, item: PlaylistItem) -> PlaylistItem:
        """
        Enrich PlaylistItem with metadata from track repository.

        Args:
            item: PlaylistItem to enrich

        Returns:
            Enriched PlaylistItem
        """
        if not self._track_repo:
            return item

        track = None

        # For local tracks with track_id, get by track_id
        if item.track_id and item.is_local:
            track = self._track_repo.get_by_id(item.track_id)
        # For online/cloud tracks, try to get by cloud_file_id
        elif item.is_cloud and item.cloud_file_id:
            track = self._track_repo.get_by_cloud_file_id(item.cloud_file_id)
        # For local files without track_id, try to find by path
        elif item.local_path and not item.cloud_file_id:
            track = self._track_repo.get_by_path(item.local_path)

        if track:
            # Determine needs_download based on source and file existence
            local_path = track.path or item.local_path
            file_exists = local_path and Path(local_path).exists()
            needs_download = False

            if item.source == TrackSource.QQ:
                needs_download = not file_exists
                if not file_exists:
                    local_path = ""
            elif item.source in (TrackSource.QUARK, TrackSource.BAIDU):
                if item.cloud_file_id and not file_exists:
                    needs_download = True
                    local_path = ""

            return item.with_metadata(
                cover_path=track.cover_path,
                title=track.title or item.title,
                artist=track.artist or item.artist,
                album=track.album or item.album,
                duration=track.duration or item.duration,
                local_path=local_path,
                track_id=track.id or item.track_id,
                needs_download=needs_download,
            )

        return item

    def _enrich_metadata_batch(self, items: List[PlaylistItem]) -> List[PlaylistItem]:
        """
        Batch-enrich multiple PlaylistItems with metadata from track repository.

        Collects all IDs/paths first, fetches in 3 batch queries, then enriches.
        """
        if not self._track_repo:
            return items

        # Collect IDs by lookup type
        track_ids = [item.track_id for item in items if item.track_id and item.is_local]
        cloud_file_ids = [item.cloud_file_id for item in items if item.is_cloud and item.cloud_file_id]
        paths = [item.local_path for item in items if item.local_path and not item.cloud_file_id]

        # Batch fetch
        id_map = {t.id: t for t in self._track_repo.get_by_ids(track_ids)} if track_ids else {}
        cloud_map = self._track_repo.get_by_cloud_file_ids(cloud_file_ids) if cloud_file_ids else {}
        path_map = self._track_repo.get_by_paths(paths) if paths else {}

        # Enrich each item from the maps
        # Pre-build path existence cache to avoid per-item disk I/O
        local_paths = set()
        for item in items:
            track = None
            if item.track_id and item.is_local:
                track = id_map.get(item.track_id)
            elif item.is_cloud and item.cloud_file_id:
                track = cloud_map.get(item.cloud_file_id)
            elif item.local_path and not item.cloud_file_id:
                track = path_map.get(item.local_path)
            if track:
                lp = track.path or item.local_path
                if lp:
                    local_paths.add(lp)
        existing_paths = {p for p in local_paths if Path(p).exists()}

        result = []
        for item in items:
            track = None

            if item.track_id and item.is_local:
                track = id_map.get(item.track_id)
            elif item.is_cloud and item.cloud_file_id:
                track = cloud_map.get(item.cloud_file_id)
            elif item.local_path and not item.cloud_file_id:
                track = path_map.get(item.local_path)

            if track:
                local_path = track.path or item.local_path
                file_exists = local_path and local_path in existing_paths
                needs_download = False

                if item.source == TrackSource.QQ:
                    needs_download = not file_exists
                    if not file_exists:
                        local_path = ""
                elif item.source in (TrackSource.QUARK, TrackSource.BAIDU):
                    if item.cloud_file_id and not file_exists:
                        needs_download = True
                        local_path = ""

                item = item.with_metadata(
                    cover_path=track.cover_path,
                    title=track.title or item.title,
                    artist=track.artist or item.artist,
                    album=track.album or item.album,
                    duration=track.duration or item.duration,
                    local_path=local_path,
                    track_id=track.id or item.track_id,
                    needs_download=needs_download,
                )

            result.append(item)

        return result

    def clear(self):
        """Clear the saved play queue from database."""
        self._queue_repo.clear()
        self._config.delete("queue_current_index")
        self._config.delete("queue_play_mode")

    def get_queue(self):
        """
        Get current queue items from engine.

        Returns:
            List of PlaylistItem currently in the playback queue
        """
        return self._engine.playlist_items or []
