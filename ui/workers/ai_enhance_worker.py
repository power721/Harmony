"""
Worker thread for AI metadata enhancement.
"""
import logging
from pathlib import Path
from typing import List

from PySide6.QtCore import QThread, Signal

from services.ai import AIMetadataService
from services.metadata.metadata_service import MetadataService
from system.event_bus import EventBus

logger = logging.getLogger(__name__)


class AIEnhanceWorker(QThread):
    """Worker thread for enhancing track metadata using AI."""

    progress = Signal(int, int)  # current, total
    finished_signal = Signal(list, int, int)  # enhanced_ids, enhanced_count, failed_count

    def __init__(
            self,
            track_ids: List[int],
            library_service,
            base_url: str,
            api_key: str,
            model: str
    ):
        """
        Initialize the worker.

        Args:
            track_ids: List of track IDs to enhance
            library_service: Library service for track operations
            base_url: AI API base URL
            api_key: AI API key
            model: AI model name
        """
        super().__init__()
        self._track_ids = track_ids
        self._library_service = library_service
        self._base_url = base_url
        self._api_key = api_key
        self._model = model
        self._cancelled = False

    def run(self):
        """Execute the AI enhancement."""
        enhanced_count = 0
        failed_count = 0
        enhanced_track_ids = []

        # Collect all tracks and filenames
        tracks_info = []  # [(index, track_id, track_path, filename)]
        for i, track_id in enumerate(self._track_ids):
            if self._cancelled:
                break
            track = self._library_service.get_track(track_id)
            if track:
                # Skip tracks without local path (online/cloud tracks)
                if not track.path or not track.path.strip():
                    continue
                filename = Path(track.path).name
                tracks_info.append((i, track_id, track.path, filename))

        if not tracks_info:
            self.finished_signal.emit([], 0, len(self._track_ids))
            return

        # Extract filenames for batch processing
        filenames = [info[3] for info in tracks_info]

        # Batch call AI
        self.progress.emit(0, len(tracks_info))
        batch_results = AIMetadataService.enhance_metadata_batch(
            filenames=filenames,
            base_url=self._base_url,
            api_key=self._api_key,
            model=self._model,
        )

        # Apply results
        for idx, (orig_idx, track_id, track_path, filename) in enumerate(tracks_info):
            if self._cancelled:
                break

            self.progress.emit(idx + 1, len(tracks_info))

            if idx in batch_results:
                enhanced = batch_results[idx]
                # Update file metadata
                try:
                    MetadataService.save_metadata(
                        track_path,
                        title=enhanced.get('title'),
                        artist=enhanced.get('artist'),
                        album=enhanced.get('album')
                    )
                except Exception as e:
                    logger.error(f"Failed to save metadata: {e}")

                # Update database
                self._library_service.update_track_metadata(
                    track_id,
                    title=enhanced.get('title'),
                    artist=enhanced.get('artist'),
                    album=enhanced.get('album')
                )
                # Emit metadata_updated signal to update play_queue
                EventBus.instance().metadata_updated.emit(track_id)
                enhanced_count += 1
                enhanced_track_ids.append(track_id)
            else:
                failed_count += 1

        self.finished_signal.emit(enhanced_track_ids, enhanced_count, failed_count)

    def cancel(self):
        """Cancel the enhancement process."""
        self._cancelled = True
