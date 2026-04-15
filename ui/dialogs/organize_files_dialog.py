"""
Dialog for organizing music files into structured directories.
"""
import logging
from typing import List

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QPainterPath, QRegion
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QProgressBar, QLineEdit,
    QWidget, QGraphicsDropShadowEffect,
)
from shiboken6 import isValid

from domain import PlaylistItem
from domain.track import Track
from system.i18n import t
from system.theme import ThemeManager
from ui.dialogs.dialog_title_bar import setup_equalizer_title_layout
from ui.dialogs.message_dialog import MessageDialog

logger = logging.getLogger(__name__)


class OrganizeFilesThread(QThread):
    """Thread for organizing files in background."""
    progress = Signal(str)  # Emits status message
    finished = Signal(dict)  # Emits result dict

    def __init__(self, file_org_service, track_ids: List[int], target_dir: str, parent=None):
        super().__init__(parent)
        self._file_org_service = file_org_service
        self._track_ids = track_ids
        self._target_dir = target_dir

    def run(self):
        """Execute file organization."""
        try:
            self.progress.emit(t("organizing"))
            result = self._file_org_service.organize_tracks(
                self._track_ids,
                self._target_dir
            )
            self.finished.emit(result)
        except Exception as e:
            logger.error(f"Error organizing files: {e}", exc_info=True)
            self.finished.emit({
                'success': 0,
                'failed': len(self._track_ids),
                'errors': [str(e)]
            })


class OrganizeFilesDialog(QDialog):
    """Dialog for organizing music files into structured directories."""

    def __init__(self, tracks: List[Track], file_org_service, config_manager, parent=None):
        super().__init__(parent)
        self.tracks = tracks
        self._file_org_service = file_org_service
        self._config = config_manager
        # Load last used directory from settings
        self.target_dir = self._config.get("organize_files_target_dir", "") if self._config else ""
        self.previews = []
        self.organize_thread = None
        self._drag_pos = None

        self.setWindowFlags(Qt.WindowType.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setProperty("shell", True)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

        self._setup_ui()
        self._load_tracks()
        ThemeManager.instance().register_widget(self)

        # If we have a saved directory, update the preview
        if self.target_dir:
            self.dir_edit.setText(self.target_dir)
            self._update_preview()
            self.organize_btn.setEnabled(True)

    def _setup_ui(self):
        """Setup the dialog UI."""
        self.setWindowTitle(t("organize_files"))
        self.setMinimumSize(900, 632)
        self.resize(1000, 732)

        # Root layout for frameless dialog
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        container = QWidget(self)
        container.setObjectName("dialogContainer")
        container.setGeometry(0, 0, self.width(), self.height())
        root_layout.addWidget(container)

        container_layout = QVBoxLayout(container)
        layout, self._title_bar_controller = setup_equalizer_title_layout(
            self,
            container_layout,
            t("organize_files"),
            content_spacing=15,
        )

        # Info
        info_label = QLabel(
            f"{t('selected_tracks')}: {len(self.tracks)}"
        )
        info_label.setProperty("secondary", True)
        layout.addWidget(info_label)

        # Directory selection
        dir_layout = QHBoxLayout()
        dir_label = QLabel(t("target_directory") + ":")
        dir_label.setStyleSheet("font-weight: bold;")
        dir_layout.addWidget(dir_label)

        self.dir_edit = QLineEdit()
        self.dir_edit.setReadOnly(True)
        self.dir_edit.setPlaceholderText(t("select_directory"))
        dir_layout.addWidget(self.dir_edit, 1)

        self.browse_btn = QPushButton(t("browse"))
        self.browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse_btn.clicked.connect(self._select_directory)
        dir_layout.addWidget(self.browse_btn)

        layout.addLayout(dir_layout)

        # Preview table
        preview_label = QLabel(t("organize_preview") + ":")
        preview_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(preview_label)

        self.preview_table = QTableWidget()
        self.preview_table.setObjectName("organizeFilesPreviewTable")
        self.preview_table.setProperty("variant", "panel")
        self.preview_table.setColumnCount(4)
        self.preview_table.setHorizontalHeaderLabels([
            t("track"), t("old_path"), t("new_path"), t("lyrics")
        ])
        self.preview_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents
        )
        self.preview_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch
        )
        self.preview_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.Stretch
        )
        self.preview_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeToContents
        )
        self.preview_table.setMinimumHeight(300)
        self.preview_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.preview_table.setFocusPolicy(Qt.NoFocus)
        self.preview_table.setShowGrid(False)
        self.preview_table.verticalHeader().setVisible(False)
        layout.addWidget(self.preview_table)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # Status label
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setProperty("secondary", True)
        layout.addWidget(self.status_label)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.organize_btn = QPushButton(t("organize"))
        self.organize_btn.setProperty("role", "primary")
        self.organize_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.organize_btn.setEnabled(False)
        self.organize_btn.clicked.connect(self._organize_files)
        button_layout.addWidget(self.organize_btn)

        close_btn = QPushButton(t("cancel"))
        close_btn.setProperty("role", "cancel")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _load_tracks(self):
        """Load tracks into preview table."""
        self.preview_table.setRowCount(len(self.tracks))

        for row, track in enumerate(self.tracks):
            # Track name
            name_text = track.title
            if track.artist:
                name_text += f" - {track.artist}"
            name_item = QTableWidgetItem(name_text)
            name_item.setData(Qt.UserRole, track.id)
            self.preview_table.setItem(row, 0, name_item)

            # Old path
            old_path_item = QTableWidgetItem(track.path)
            old_path_item.setFlags(old_path_item.flags() & ~Qt.ItemIsEditable)
            self.preview_table.setItem(row, 1, old_path_item)

            # New path (will be updated after directory selection)
            new_path_item = QTableWidgetItem("-")
            new_path_item.setFlags(new_path_item.flags() & ~Qt.ItemIsEditable)
            self.preview_table.setItem(row, 2, new_path_item)

            # Lyrics
            lyrics_item = QTableWidgetItem("-")
            lyrics_item.setFlags(lyrics_item.flags() & ~Qt.ItemIsEditable)
            self.preview_table.setItem(row, 3, lyrics_item)

    def _select_directory(self):
        """Open directory selection dialog."""
        # Start from last used directory or home directory
        start_dir = self.target_dir if self.target_dir else ""

        dir_path = QFileDialog.getExistingDirectory(
            self,
            t("select_target_directory"),
            start_dir
        )

        if dir_path:
            self.target_dir = dir_path
            self.dir_edit.setText(dir_path)

            # Save to settings
            if self._config:
                self._config.set("organize_files_target_dir", dir_path)

            self._update_preview()
            self.organize_btn.setEnabled(True)

    def _update_preview(self):
        """Update preview with calculated paths."""
        if not self.target_dir:
            return

        track_ids = [t.id for t in self.tracks if t.id]
        self.previews = self._file_org_service.preview_organization(
            track_ids,
            self.target_dir
        )

        # Update table
        for row, preview in enumerate(self.previews):
            # Update new path
            new_path_item = self.preview_table.item(row, 2)
            if new_path_item:
                new_path_item.setText(preview['new_audio_path'])

            # Update lyrics
            lyrics_item = self.preview_table.item(row, 3)
            if lyrics_item:
                if preview['has_lyrics']:
                    lyrics_item.setText(t("yes"))
                else:
                    lyrics_item.setText(t("no"))

        self.status_label.setText(
            f"{len(self.previews)} {t('files_to_organize')}"
        )

    def _organize_files(self):
        """Start file organization."""
        if not self.target_dir:
            MessageDialog.warning(
                self,
                t("error"),
                t("select_directory_first")
            )
            return

        # Disable UI
        self.browse_btn.setEnabled(False)
        self.organize_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # Indeterminate progress

        # Get track IDs
        track_ids = [t.id for t in self.tracks if t.id]

        # Start organization thread
        self.organize_thread = OrganizeFilesThread(
            self._file_org_service,
            track_ids,
            self.target_dir,
            parent=self
        )
        self.organize_thread.progress.connect(self._on_progress)
        self.organize_thread.finished.connect(self._on_finished)
        self.organize_thread.finished.connect(self.organize_thread.deleteLater)
        self.organize_thread.start()

    def _on_progress(self, message: str):
        """Handle progress update."""
        self.status_label.setText(message)

    def _on_finished(self, result: dict):
        """Handle organization completion."""
        self.progress.setVisible(False)
        self.browse_btn.setEnabled(True)

        success = result.get('success', 0)
        failed = result.get('failed', 0)
        errors = result.get('errors', [])

        # If any files were successfully organized, refresh the playback engine's queue
        if success > 0:
            self._refresh_playback_queue()

        # Show result
        if failed == 0:
            MessageDialog.information(
                self,
                t("organize_complete"),
                f"{success} {t('files_organized')}"
            )
            self.accept()
        else:
            error_text = f"{success} {t('files_organized')}\n"
            error_text += f"{failed} {t('files_failed')}\n"
            if errors:
                error_text += "\n" + "\n".join(errors[:5])  # Show first 5 errors
                if len(errors) > 5:
                    error_text += f"\n... {len(errors) - 5} {t('more')}"

            MessageDialog.warning(
                self,
                t("organize_failed"),
                error_text
            )
            # Keep dialog open if there were failures
            self.organize_btn.setEnabled(True)

    def _refresh_playback_queue(self):
        """Refresh the playback engine's queue to use updated paths."""
        try:
            from app import Application
            app = Application.instance()
            if not app or not app.bootstrap:
                logger.warning("无法获取 app 或 bootstrap")
                return

            engine = app.bootstrap.playback_service.engine
            if not engine:
                logger.warning("无法获取播放引擎")
                return

            # Get current playlist items
            current_items = engine.playlist_items
            if not current_items:
                logger.info("播放队列为空，无需刷新")
                return

            # Get track IDs that were organized
            organized_track_ids = [t.id for t in self.tracks if t.id]
            logger.info(f"整理的歌曲 IDs: {organized_track_ids}")

            # Update items in the queue that match organized track IDs
            updated_count = 0
            for i, item in enumerate(current_items):
                if item.track_id in organized_track_ids:
                    # Re-create the item from database to get the latest path
                    # (includes both local tracks and downloaded cloud files)
                    track = app.bootstrap.track_repo.get_by_id(item.track_id)
                    if track:
                        logger.info(
                            f"更新播放队列项目 {i}: track_id={item.track_id}, 旧路径={item.local_path}, 新路径={track.path}")
                        updated_item = PlaylistItem.from_track(track)
                        current_items[i] = updated_item
                        updated_count += 1
                    else:
                        logger.warning(f"无法从数据库获取 track_id={item.track_id}")

            # Reload the playlist
            engine.load_playlist_items(current_items)
            logger.info(f"刷新播放引擎队列: 更新了 {updated_count} 个项目")

            # If a track is currently playing, reload it
            if engine.current_index >= 0:
                logger.info(f"重新加载当前播放的歌曲，索引: {engine.current_index}")
                engine._load_track(engine.current_index)
        except Exception as e:
            logger.error(f"刷新播放引擎队列失败: {e}", exc_info=True)

    def resizeEvent(self, event):
        """Apply rounded corner mask."""
        path = QPainterPath()
        path.addRoundedRect(self.rect(), 12, 12)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        """Handle mouse press for drag to move."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        """Handle mouse move for drag to move."""
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        """Handle mouse release."""
        self._drag_pos = None

    def closeEvent(self, event):
        """Clean up on close."""
        self._stop_organize_thread(wait_ms=1000)
        super().closeEvent(event)

    def _stop_organize_thread(self, wait_ms: int = 1000):
        """Stop organize worker cooperatively."""
        thread = self.organize_thread
        if not (thread and isValid(thread) and thread.isRunning()):
            return
        thread.requestInterruption()
        thread.quit()
        if not thread.wait(wait_ms):
            logger.warning(
                "[OrganizeFilesDialog] Organize thread did not stop in time via cooperative shutdown"
            )

    def refresh_theme(self):
        """Refresh theme when changed."""
        self._title_bar_controller.refresh_theme()
