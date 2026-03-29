"""
Production-grade music folder scan dialog for MainWindow.

Features:
- Stable Qt thread lifecycle
- Two-phase scanning (discover + import)
- Incremental scan (path + size + mtime)
- Batch database insert
- Better cancellation
- NAS / network drive friendly
- Non-blocking progress dialog
"""

import logging
import os
import time
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Callable

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QPushButton, QWidget, QGraphicsDropShadowEffect,
)
from PySide6.QtCore import Qt, QThread, Signal, QObject, QTimer
from PySide6.QtGui import QColor

from services import MetadataService
from domain.track import Track
from system.i18n import t
from system.theme import ThemeManager
from ui.widgets.title_bar import TitleBar

if TYPE_CHECKING:
    from infrastructure.database import DatabaseManager
    from services.metadata import CoverService

logger = logging.getLogger(__name__)


# =========================================================
# Data models
# =========================================================

@dataclass
class FileCandidate:
    path: str
    name: str
    size: int
    mtime: float


@dataclass
class ScanStats:
    discovered: int = 0
    added: int = 0
    skipped: int = 0
    unchanged: int = 0
    failed: int = 0
    cancelled: bool = False


# =========================================================
# Worker
# =========================================================

class ScanWorker(QObject):
    """
    Background worker for scanning and importing music files.

    IMPORTANT:
    - This worker should not touch QWidget/UI objects.
    - Keep heavy IO and metadata extraction here.
    """

    # phase, percent, message
    status = Signal(str, int, str)

    # final stats
    finished = Signal(dict)

    # optional: summary / debug events
    log = Signal(str)

    def __init__(
        self,
        folder_path: str,
        db_manager: "DatabaseManager",
        cover_service: Optional["CoverService"] = None,
        batch_size: int = 100,
        enable_cover_extraction: bool = False,
    ):
        super().__init__()
        self.folder_path = folder_path
        self._db = db_manager
        self._cover_service = cover_service
        self._batch_size = max(1, batch_size)
        self._enable_cover_extraction = enable_cover_extraction

        self._cancelled = False
        self._last_progress_emit = 0.0

    # -------------------------
    # lifecycle
    # -------------------------

    def cancel(self):
        logger.info("[ScanWorker] Cancel requested")
        self._cancelled = True

    def is_cancelled(self) -> bool:
        return self._cancelled

    def run(self):
        """
        Main worker entrypoint.
        """
        stats = ScanStats()
        start_time = time.time()

        try:
            logger.info(f"[ScanWorker] Start scanning: {self.folder_path}")
            folder = Path(self.folder_path)

            if not folder.exists() or not folder.is_dir():
                self.log.emit(f"Invalid folder: {self.folder_path}")
                self.finished.emit({
                    "error": f"Invalid folder: {self.folder_path}",
                    "stats": stats.__dict__,
                })
                return

            # Phase A: discover files
            candidates = self._discover_audio_files(folder, stats)

            if self.is_cancelled():
                stats.cancelled = True
                self.finished.emit({"stats": stats.__dict__})
                return

            # Phase B: import / update
            self._import_candidates(candidates, stats)

            if self.is_cancelled():
                stats.cancelled = True

            elapsed = time.time() - start_time
            logger.info(
                f"[ScanWorker] Finished in {elapsed:.2f}s | "
                f"discovered={stats.discovered}, added={stats.added}, "
                f"skipped={stats.skipped}, unchanged={stats.unchanged}, failed={stats.failed}"
            )

            self.finished.emit({
                "stats": stats.__dict__,
                "elapsed_seconds": round(elapsed, 2),
            })

        except Exception as e:
            logger.exception("[ScanWorker] Fatal scan error")
            self.finished.emit({
                "error": str(e),
                "stats": stats.__dict__,
            })

    # =====================================================
    # Phase A: Discover files
    # =====================================================

    def _discover_audio_files(self, folder: Path, stats: ScanStats) -> list[FileCandidate]:
        """
        Discover all supported audio files.

        Designed to be friendlier to large folders / NAS:
        - uses os.walk() instead of repeated rglob per extension
        - checks cancellation often
        - emits lightweight status updates
        """
        supported_formats = {
            ext.lower() for ext in MetadataService.SUPPORTED_FORMATS
        }

        candidates: list[FileCandidate] = []

        self.status.emit("discover", 0, t("scanning") + " - " + t("discovering_files"))

        # os.walk is generally more predictable than multiple Path.rglob()
        for root, dirs, files in os.walk(folder, topdown=True):
            if self.is_cancelled():
                return candidates

            # Optional: skip hidden/system folders if you want
            # dirs[:] = [d for d in dirs if not d.startswith(".")]

            for filename in files:
                if self.is_cancelled():
                    return candidates

                ext = Path(filename).suffix.lower()
                if ext not in supported_formats:
                    continue

                full_path = os.path.join(root, filename)

                try:
                    st = os.stat(full_path)
                    candidates.append(
                        FileCandidate(
                            path=str(Path(full_path).resolve()),
                            name=filename,
                            size=st.st_size,
                            mtime=st.st_mtime,
                        )
                    )
                    stats.discovered += 1

                    # throttle UI updates
                    self._emit_throttled_status(
                        phase="discover",
                        percent=0,  # indeterminate phase
                        message=f"{t('discovering_files')}: {filename}",
                        interval=0.08,
                    )

                except Exception:
                    logger.exception(f"[ScanWorker] Failed to stat file: {full_path}")
                    stats.failed += 1

        logger.info(f"[ScanWorker] Discovered {len(candidates)} audio files")
        return candidates

    # =====================================================
    # Phase B: Import files
    # =====================================================

    def _import_candidates(self, candidates: list[FileCandidate], stats: ScanStats):
        """
        Incremental import with batch DB insert.
        """
        total = len(candidates)

        if total == 0:
            self.status.emit("import", 100, t("no_audio_files_found"))
            return

        self.status.emit("import", 0, t("importing_music"))

        # IMPORTANT:
        # This method expects your DatabaseManager to support one of:
        #
        # 1) get_track_index_for_paths(paths: list[str]) -> dict[str, {"size": int, "mtime": float}]
        # 2) fallback per-file get_track_by_path(path)
        #
        # and one of:
        # 1) add_tracks_bulk(tracks: list[Track])
        # 2) fallback add_track(track)
        #
        existing_index = self._load_existing_index([c.path for c in candidates])

        pending_tracks: list[Track] = []

        for i, candidate in enumerate(candidates, start=1):
            if self.is_cancelled():
                break

            percent = int((i / total) * 100)
            self.status.emit("import", percent, f"{t('scanning')}: {candidate.name}")

            try:
                existing = existing_index.get(candidate.path)

                # Incremental check
                if existing and self._is_unchanged(existing, candidate):
                    stats.unchanged += 1
                    continue

                metadata = MetadataService.extract_metadata(candidate.path)

                if self.is_cancelled():
                    break

                # IMPORTANT:
                # To avoid Qt cross-thread issues, keep cover extraction disabled
                # unless your CoverService is pure Python and thread-safe.
                cover_path = None
                if self._enable_cover_extraction and self._cover_service:
                    try:
                        cover_path = self._safe_extract_cover(candidate.path, metadata)
                    except Exception:
                        logger.exception(f"[ScanWorker] Cover extraction failed: {candidate.path}")

                track = Track(
                    path=candidate.path,
                    title=metadata.get("title", Path(candidate.path).stem),
                    artist=metadata.get("artist", ""),
                    album=metadata.get("album", ""),
                    duration=metadata.get("duration", 0.0),
                    cover_path=cover_path,
                    created_at=datetime.now(),
                    file_size=candidate.size,
                    file_mtime=candidate.mtime,
                )

                pending_tracks.append(track)

                if existing:
                    # file changed → treated as "skipped old / updated new" depending on your DB design
                    # Here we simply overwrite/replace at DB layer if supported.
                    pass

                if len(pending_tracks) >= self._batch_size:
                    self._flush_batch(pending_tracks, stats)
                    pending_tracks.clear()

            except Exception:
                logger.exception(f"[ScanWorker] Failed to import: {candidate.path}")
                stats.failed += 1

        # flush remaining
        if pending_tracks and not self.is_cancelled():
            self._flush_batch(pending_tracks, stats)
            pending_tracks.clear()

        # refresh aggregate tables only once
        if stats.added > 0 and not self.is_cancelled():
            try:
                self.status.emit("finalize", 100, t("updating_library"))
                self._refresh_aggregates()
            except Exception:
                logger.exception("[ScanWorker] Failed to refresh aggregates")

    # =====================================================
    # Helpers
    # =====================================================

    def _load_existing_index(self, paths: list[str]) -> dict:
        """
        Load existing tracks index for incremental comparison.

        Preferred DB API:
            db.get_track_index_for_paths(paths) -> dict[path] = {"size": ..., "mtime": ...}

        Fallback:
            db.get_track_by_path(path)
        """
        try:
            if hasattr(self._db, "get_track_index_for_paths"):
                return self._db.get_track_index_for_paths(paths) or {}
        except Exception:
            logger.exception("[ScanWorker] Bulk track index load failed")

        # fallback (slower)
        result = {}
        for path in paths:
            if self.is_cancelled():
                break
            try:
                existing = self._db.get_track_by_path(path)
                if existing:
                    result[path] = {
                        "size": existing.file_size,
                        "mtime": existing.file_mtime,
                    }
            except Exception:
                logger.exception(f"[ScanWorker] Failed get_track_by_path: {path}")

        return result

    def _is_unchanged(self, existing: dict, candidate: FileCandidate) -> bool:
        """
        Compare file fingerprint for incremental scan.
        """
        old_size = existing.get("size")
        old_mtime = existing.get("mtime")

        # if DB doesn't yet store these fields, cannot safely determine unchanged
        if old_size is None or old_mtime is None:
            return False

        return int(old_size) == int(candidate.size) and int(old_mtime) == int(candidate.mtime)

    def _flush_batch(self, tracks: list[Track], stats: ScanStats):
        """
        Bulk insert/update tracks.
        """
        if not tracks:
            return

        try:
            if hasattr(self._db, "add_tracks_bulk"):
                added, skipped = self._db.add_tracks_bulk(tracks)
                stats.added += int(added or 0)
                stats.skipped += int(skipped or 0)
            else:
                # fallback
                for track in tracks:
                    self._db.add_track(track)
                    stats.added += 1

        except Exception:
            logger.exception("[ScanWorker] Batch insert failed")
            # degrade to per-track to salvage partial import
            for track in tracks:
                try:
                    self._db.add_track(track)
                    stats.added += 1
                except Exception:
                    logger.exception(f"[ScanWorker] Failed fallback add_track: {track.path}")
                    stats.failed += 1

    def _refresh_aggregates(self):
        if hasattr(self._db, "refresh_albums"):
            self._db.refresh_albums()
        if hasattr(self._db, "refresh_artists"):
            self._db.refresh_artists()

    def _safe_extract_cover(self, file_path: str, metadata: dict) -> Optional[str]:
        """
        Cover extraction wrapper.

        WARNING:
        Only use this if your CoverService is pure Python / thread-safe.
        If it internally uses Qt image classes, keep it disabled.
        """
        cover_blob = metadata.get("cover")
        if not cover_blob:
            return None

        return self._cover_service.save_cover_from_metadata(file_path, cover_blob)

    def _emit_throttled_status(self, phase: str, percent: int, message: str, interval: float = 0.1):
        now = time.time()
        if now - self._last_progress_emit >= interval:
            self.status.emit(phase, percent, message)
            self._last_progress_emit = now


# =========================================================
# Controller / Dialog
# =========================================================

class _ScanProgressDialog(QDialog):
    """Themed frameless scan progress dialog."""

    _STYLE = """
    #scanContainer {
        background-color: %background_alt%;
        border-radius: 12px;
    }
    #scanTitle {
        font-size: 16px;
        font-weight: bold;
        color: %text%;
    }
    #scanMessage {
        font-size: 13px;
        color: %text_secondary%;
    }
    QProgressBar {
        background-color: %background%;
        border: none;
        border-radius: 4px;
        height: 6px;
        text-align: center;
    }
    QProgressBar::chunk {
        background-color: %highlight%;
        border-radius: 4px;
    }
    QPushButton#scanCancelBtn {
        background-color: %background%;
        color: %text%;
        border: 1px solid %border%;
        border-radius: 6px;
        padding: 6px 24px;
        font-size: 13px;
    }
    QPushButton#scanCancelBtn:hover {
        background-color: %background_hover%;
        border-color: %highlight%;
    }
    QPushButton#scanCancelBtn:disabled {
        color: %text_secondary%;
        border-color: %background_hover%;
    }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(420, 200)
        self.setModal(True)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        container = QWidget(self)
        container.setObjectName("scanContainer")
        container.setGeometry(0, 0, 420, 200)
        layout.addWidget(container)

        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(20, 12, 20, 20)
        main_layout.setSpacing(12)

        self._title_bar = TitleBar(container)
        self._title_bar.setFixedHeight(32)
        self._title_bar.set_track_title(t("scanning"), "")
        main_layout.addWidget(self._title_bar)

        self._message_label = QLabel(t("discovering_files"))
        self._message_label.setObjectName("scanMessage")
        self._message_label.setWordWrap(True)
        main_layout.addWidget(self._message_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)  # indeterminate
        self._progress_bar.setTextVisible(False)
        main_layout.addWidget(self._progress_bar)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self._cancel_btn = QPushButton(t("cancel"))
        self._cancel_btn.setObjectName("scanCancelBtn")
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self._cancel_btn)
        main_layout.addLayout(btn_layout)

        self._apply_style()
        ThemeManager.instance().register_widget(self)

    def _apply_style(self):
        self.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE))

    def set_indeterminate(self):
        self._progress_bar.setRange(0, 0)

    def set_progress(self, percent: int):
        if self._progress_bar.maximum() == 0:
            self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(percent)

    def set_message(self, message: str):
        self._message_label.setText(message)

    def disable_cancel(self):
        self._cancel_btn.setEnabled(False)

    def closeEvent(self, event):
        """Treat close button as cancel."""
        self.reject()


class ScanController(QObject):
    """
    A controller that owns the worker thread and progress dialog.

    Keeps lifecycle clean and avoids leaking QThread/QObject references.
    """

    completed = Signal(dict)

    def __init__(
        self,
        folder: str,
        db_manager: "DatabaseManager",
        cover_service: Optional["CoverService"] = None,
        parent=None,
        on_complete: Optional[Callable[[dict], None]] = None,
        batch_size: int = 100,
        enable_cover_extraction: bool = False,
    ):
        super().__init__(parent)
        self.folder = folder
        self.db_manager = db_manager
        self.cover_service = cover_service
        self.on_complete = on_complete
        self.batch_size = batch_size
        self.enable_cover_extraction = enable_cover_extraction

        self.thread: Optional[QThread] = None
        self.worker: Optional[ScanWorker] = None
        self.dialog: Optional[_ScanProgressDialog] = None

    def start(self):
        logger.info(f"[ScanController] Start scan: {self.folder}")

        self.dialog = _ScanProgressDialog(self.parent())

        self.thread = QThread(self)
        self.worker = ScanWorker(
            folder_path=self.folder,
            db_manager=self.db_manager,
            cover_service=self.cover_service,
            batch_size=self.batch_size,
            enable_cover_extraction=self.enable_cover_extraction,
        )
        self.worker.moveToThread(self.thread)

        # Connect
        self.thread.started.connect(self.worker.run)
        self.worker.status.connect(self._on_status, Qt.QueuedConnection)
        self.worker.finished.connect(self._on_finished, Qt.QueuedConnection)
        self.dialog.rejected.connect(self._on_cancel)

        # Clean lifecycle
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.dialog.show()

        # Delay thread start until dialog paints
        QTimer.singleShot(0, self.thread.start)

        return self

    # -------------------------
    # Slots
    # -------------------------

    def _on_status(self, phase: str, percent: int, message: str):
        if not self.dialog:
            return

        if phase == "discover":
            self.dialog.set_indeterminate()
            self.dialog.set_message(message)

        elif phase in ("import", "finalize"):
            self.dialog.set_progress(percent)
            self.dialog.set_message(message)

    def _on_cancel(self):
        logger.info("[ScanController] User requested cancel")
        if self.worker:
            self.worker.cancel()
        if self.dialog:
            self.dialog.disable_cancel()
            self.dialog.set_message(t("cancelling"))

    def _on_finished(self, payload: dict):
        logger.info(f"[ScanController] Scan finished: {payload}")

        if self.dialog:
            # Disconnect cancel to avoid double-fire
            try:
                self.dialog.rejected.disconnect(self._on_cancel)
            except RuntimeError:
                pass
            self.dialog.set_progress(100)
            self.dialog.close()

        # Stop thread cleanly
        self._cleanup_thread()

        # Callback
        if self.on_complete:
            try:
                self.on_complete(payload)
            except Exception:
                logger.exception("[ScanController] on_complete callback failed")

        self.completed.emit(payload)

        # Optional self cleanup
        self.deleteLater()

    def _cleanup_thread(self):
        if not self.thread:
            return

        if self.thread.isRunning():
            self.thread.quit()
            if not self.thread.wait(5000):
                logger.warning("[ScanController] Thread did not quit in time")

        self.thread = None
        self.worker = None
        self.dialog = None


# =========================================================
# Public API
# =========================================================

class ScanDialog:
    """
    Public entry for launching scan.
    """

    @staticmethod
    def scan_folder(
        folder: str,
        db_manager: "DatabaseManager",
        cover_service: Optional["CoverService"] = None,
        parent=None,
        on_complete: Optional[Callable[[dict], None]] = None,
        batch_size: int = 100,
        enable_cover_extraction: bool = False,
    ) -> ScanController:
        """
        Start scanning a music folder asynchronously.

        Returns:
            ScanController
                Keep a reference on MainWindow (important),
                e.g. self._scan_controller = ScanDialog.scan_folder(...)
        """
        controller = ScanController(
            folder=folder,
            db_manager=db_manager,
            cover_service=cover_service,
            parent=parent,
            on_complete=on_complete,
            batch_size=batch_size,
            enable_cover_extraction=enable_cover_extraction,
        )
        controller.start()
        return controller