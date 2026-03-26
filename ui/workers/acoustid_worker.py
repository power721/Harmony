"""
Worker thread for AcoustID fingerprint identification.
"""
import logging
from typing import List

from PySide6.QtCore import QThread, Signal

from services.ai import AcoustIDService
from services.metadata.metadata_service import MetadataService
from system.event_bus import EventBus

logger = logging.getLogger(__name__)


class AcoustIDWorker(QThread):
    """Worker thread for identifying tracks using AcoustID fingerprinting."""

    progress = Signal(int, int, int)  # current, total, track_id
    finished_signal = Signal(list, int, int)  # identified_ids, success_count, failed_count

    def __init__(
        self,
        track_ids: List[int],
        library_service,
        api_key: str
    ):
        """
        Initialize the worker.

        Args:
            track_ids: List of track IDs to identify
            library_service: Library service for track operations
            api_key: AcoustID API key
        """
        super().__init__()
        self._track_ids = track_ids
        self._library_service = library_service
        self._api_key = api_key
        self._cancelled = False

    def run(self):
        """Execute the AcoustID identification."""
        success_count = 0
        failed_count = 0
        identified_track_ids = []

        for i, track_id in enumerate(self._track_ids):
            if self._cancelled:
                break

            self.progress.emit(i, len(self._track_ids), track_id)

            track = self._library_service.get_track(track_id)
            if not track:
                failed_count += 1
                continue

            # Get current metadata
            current_metadata = MetadataService.extract_metadata(track.path) or {}

            # Identify using AcoustID
            enhanced = AcoustIDService.enhance_track(
                file_path=track.path,
                api_key=self._api_key,
                current_metadata=current_metadata,
                update_file=True
            )

            if enhanced and enhanced.get('title'):
                self._library_service.update_track_metadata(
                    track_id,
                    title=enhanced.get('title'),
                    artist=enhanced.get('artist'),
                    album=enhanced.get('album')
                )
                # Emit metadata_updated signal to update play_queue
                EventBus.instance().metadata_updated.emit(track_id)
                success_count += 1
                identified_track_ids.append(track_id)
                logger.info(
                    f"AcoustID identified track {track_id}: {enhanced.get('title')} - {enhanced.get('artist')}"
                )
            else:
                failed_count += 1
                logger.warning(f"AcoustID failed to identify track {track_id}")

        self.finished_signal.emit(identified_track_ids, success_count, failed_count)

    def cancel(self):
        """Cancel the identification process."""
        self._cancelled = True
