"""
Music folder scan dialog for MainWindow.
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QProgressDialog
from PySide6.QtCore import Qt, QThread, Signal, QObject

from services import MetadataService
from domain.track import Track
from system.i18n import t

if TYPE_CHECKING:
    from infrastructure.database import DatabaseManager
    from services.metadata import CoverService

logger = logging.getLogger(__name__)


class ScanWorker(QObject):
    """
    Worker for scanning music folders.

    Signals:
        progress: Emitted during scanning (value, filename)
        finished: Emitted when scanning completes (added, skipped)
    """

    progress = Signal(int, str)
    finished = Signal(int, int)

    def __init__(
        self,
        folder_path: str,
        db_manager: "DatabaseManager",
        cover_service: "CoverService"
    ):
        """
        Initialize the scan worker.

        Args:
            folder_path: Path to the folder to scan
            db_manager: Database manager for adding tracks
            cover_service: Cover service for saving cover art
        """
        super().__init__()
        self.folder_path = folder_path
        self._db = db_manager
        self._cover_service = cover_service
        self._cancelled = False

    def cancel(self):
        """Cancel the scan."""
        self._cancelled = True

    def run(self):
        """Run the scan."""
        folder_path = Path(self.folder_path)
        supported_formats = MetadataService.SUPPORTED_FORMATS

        # Find all audio files
        audio_files = []
        for ext in supported_formats:
            audio_files.extend(folder_path.rglob(f"*{ext}"))

        total_files = len(audio_files)

        if total_files == 0:
            self.finished.emit(0, 0)
            return

        added_count = 0
        skipped_count = 0

        for i, audio_file in enumerate(audio_files):
            if self._cancelled:
                break

            # Emit progress
            self.progress.emit(int((i / total_files) * 100), audio_file.name)

            try:
                # Check if track already exists
                existing = self._db.get_track_by_path(str(audio_file))
                if existing:
                    skipped_count += 1
                    continue

                # Extract metadata
                metadata = MetadataService.extract_metadata(str(audio_file))

                # Save cover art from metadata
                cover_path = None
                if self._cover_service:
                    cover_path = self._cover_service.save_cover_from_metadata(
                        str(audio_file), metadata.get("cover")
                    )

                # Create track object
                track = Track(
                    path=str(audio_file),
                    title=metadata.get("title", audio_file.stem),
                    artist=metadata.get("artist", ""),
                    album=metadata.get("album", ""),
                    duration=metadata.get("duration", 0.0),
                    cover_path=cover_path,
                    created_at=datetime.now(),
                )

                # Add to database
                self._db.add_track(track)
                added_count += 1

            except Exception as e:
                logger.error(f"Error adding track {audio_file}: {e}")
                skipped_count += 1

        self.finished.emit(added_count, skipped_count)


class ScanDialog:
    """
    Dialog for scanning music folders.

    This is a static class that creates and manages the scan dialog.
    """

    @staticmethod
    def scan_folder(
        folder: str,
        db_manager: "DatabaseManager",
        cover_service: "CoverService",
        parent=None,
        on_complete=None
    ) -> tuple:
        """
        Scan a music folder and add tracks.

        Args:
            folder: Path to the folder to scan
            db_manager: Database manager
            cover_service: Cover service
            parent: Parent widget for the dialog
            on_complete: Callback when scan completes (added, skipped)

        Returns:
            Tuple of (worker, thread) for cancellation
        """
        logger.info(f"[ScanDialog] Scanning music folder: {folder}")

        # Create progress dialog
        progress = QProgressDialog(t("scanning"), t("cancel"), 0, 100, parent)
        progress.setWindowTitle(t("scanning"))
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.show()

        # Create worker and thread
        worker = ScanWorker(folder, db_manager, cover_service)
        thread = QThread()
        worker.moveToThread(thread)

        # Connect signals
        def on_progress(value, filename):
            if not progress.wasCanceled():
                progress.setValue(value)
                progress.setLabelText(f"{t('scanning')}: {filename}")

        def on_finished(added, skipped):
            progress.close()
            logger.info(f"[ScanDialog] Scan complete: {added} added, {skipped} skipped")

            # Refresh albums and artists tables
            if added > 0:
                db_manager.refresh_albums()
                db_manager.refresh_artists()

            thread.quit()
            thread.wait()

            if on_complete:
                on_complete(added, skipped)

        def on_cancel():
            worker.cancel()

        worker.progress.connect(on_progress)
        worker.finished.connect(on_finished)
        progress.canceled.connect(on_cancel)
        thread.started.connect(worker.run)

        # Start thread
        thread.start()

        return worker, thread
