"""
Queue service - Manages playback queue persistence.
"""

import logging

from domain import PlaylistItem
from domain.playback import PlayMode
from infrastructure.audio import PlayerEngine
from repositories.queue_repository import SqliteQueueRepository

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
            db_manager=None
    ):
        self._queue_repo = queue_repo
        self._config = config_manager
        self._engine = engine
        self._db = db_manager

    def save(self):
        """Save the current play queue to database."""
        items = self._engine.playlist_items
        if not items:
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

        # Convert to PlaylistItem list, passing db to get latest track paths
        items = [PlaylistItem.from_play_queue_item(item, db=self._db) for item in queue_items]

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
