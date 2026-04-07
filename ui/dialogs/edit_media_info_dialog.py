"""
Dialog for editing media information for tracks.
"""
import logging
from pathlib import Path
from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainterPath, QRegion
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QDialogButtonBox,
    QFormLayout,
    QCheckBox,
    QProgressBar,
    QPushButton,
    QWidget,
    QGraphicsDropShadowEffect,
)

from services import MetadataService
from system.event_bus import EventBus
from system.i18n import t
from system.theme import ThemeManager
from ui.dialogs.dialog_title_bar import setup_equalizer_title_layout
from ui.dialogs.message_dialog import MessageDialog

logger = logging.getLogger(__name__)


class EditMediaInfoDialog(QDialog):
    """Dialog for editing media information for one or more tracks."""

    tracks_updated = Signal(list)  # Emitted when tracks are updated with list of track IDs

    _PROGRESS_STYLE_TEMPLATE = """
        QProgressBar {
            border: 2px solid %border%;
            border-radius: 5px;
            text-align: center;
            color: %text%;
        }
        QProgressBar::chunk {
            background-color: %highlight%;
            border-radius: 3px;
        }
    """

    def __init__(self, track_ids: List[int], library_service, parent=None):
        """
        Initialize the dialog.

        Args:
            track_ids: List of track IDs to edit
            library_service: Library service for track operations
            parent: Parent widget
        """
        super().__init__(parent)
        self._track_ids = track_ids
        self._library_service = library_service
        self._is_batch_edit = len(track_ids) > 1
        self._drag_pos = None

        # Make dialog frameless
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setProperty("shell", True)

        self._setup_shadow()
        self._setup_ui()
        ThemeManager.instance().register_widget(self)

    def _setup_shadow(self):
        """Setup drop shadow effect."""
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

    def _check_can_save(self, track) -> bool:
        """
        Check if the track can be saved (has a local file).

        Args:
            track: Track object to check

        Returns:
            True if the track has an editable local file, False otherwise
        """
        if not track.path:
            return False

        # Check for online streaming URLs
        if track.path.startswith(('http://', 'https://', 'qqmusic:/')):
            return False

        # Check if file exists locally
        try:
            from pathlib import Path
            return Path(track.path).exists()
        except Exception:
            return False

    def _setup_ui(self):
        """Setup the user interface."""
        # Set window title
        if self._is_batch_edit:
            title_text = f"{t('edit_media_info_title')} ({len(self._track_ids)} {t('tracks')})"
        else:
            title_text = t("edit_media_info_title")
        self.setWindowTitle(title_text)
        self.setMinimumWidth(450)

        # Outer layout with 0 margins — container fills the dialog
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Container widget for rounded corners
        container = QWidget()
        container.setObjectName("dialogContainer")
        outer.addWidget(container)

        container_layout = QVBoxLayout(container)
        layout, self._title_bar_controller = setup_equalizer_title_layout(
            self,
            container_layout,
            title_text,
        )

        # Get first track for initial values
        first_track = self._library_service.get_track(self._track_ids[0])
        if not first_track:
            self.reject()
            return

        # Check if track has editable local file
        self._can_save = self._check_can_save(first_track)

        # Show warning for non-local tracks
        if not self._can_save and not self._is_batch_edit:
            warning_label = QLabel(t("online_track_cannot_edit"))
            warning_label.setStyleSheet(
                f"color: {ThemeManager.instance().current_theme.highlight}; "
                f"font-size: 13px; padding: 10px; "
                f"background-color: {ThemeManager.instance().current_theme.background}; "
                f"border-radius: 4px;"
            )
            layout.addWidget(warning_label)

        # Info label for batch edit
        if self._is_batch_edit:
            info_label = QLabel(
                f"{t('batch_edit_info')}: {len(self._track_ids)} {t('tracks')}"
            )
            info_label.setStyleSheet(
                f"color: {ThemeManager.instance().current_theme.highlight}; font-size: 14px; padding: 10px; background-color: {ThemeManager.instance().current_theme.background}; border-radius: 4px;"
            )
            layout.addWidget(info_label)

        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        form_layout.setLabelAlignment(Qt.AlignRight)

        # Only show title field for single track edit
        self._title_input = None
        if not self._is_batch_edit:
            self._title_input = QLineEdit(first_track.title or "")
            self._title_input.setPlaceholderText(t("enter_title"))
            self._title_input.setReadOnly(not self._can_save)
            form_layout.addRow(t("title") + ":", self._title_input)

        self._artist_input = QLineEdit(first_track.artist or "")
        self._artist_input.setPlaceholderText(t("enter_artist"))
        self._artist_input.setReadOnly(not self._can_save)
        self._album_input = QLineEdit(first_track.album or "")
        self._album_input.setPlaceholderText(t("enter_album"))
        self._album_input.setReadOnly(not self._can_save)
        self._genre_input = QLineEdit(first_track.genre or "")
        self._genre_input.setPlaceholderText(t("enter_genre"))
        self._genre_input.setReadOnly(not self._can_save)

        # For batch edit, add checkboxes to control which fields to update
        if self._is_batch_edit:
            self._update_artist_cb = QCheckBox(t("update_artist"))
            self._update_artist_cb.setChecked(True)
            self._update_artist_cb.setEnabled(self._can_save)
            self._update_album_cb = QCheckBox(t("update_album"))
            self._update_album_cb.setChecked(True)
            self._update_album_cb.setEnabled(self._can_save)
            self._update_genre_cb = QCheckBox(t("update_genre"))
            self._update_genre_cb.setChecked(True)
            self._update_genre_cb.setEnabled(self._can_save)

            form_layout.addRow(t("artist") + ":", self._artist_input)
            form_layout.addRow("", self._update_artist_cb)
            form_layout.addRow(t("album") + ":", self._album_input)
            form_layout.addRow("", self._update_album_cb)
            form_layout.addRow(t("genre") + ":", self._genre_input)
            form_layout.addRow("", self._update_genre_cb)
        else:
            form_layout.addRow(t("artist") + ":", self._artist_input)
            form_layout.addRow(t("album") + ":", self._album_input)
            form_layout.addRow(t("genre") + ":", self._genre_input)

            # Show file information for single track
            self._add_file_info(form_layout, first_track)

        layout.addLayout(form_layout)

        # Progress bar for batch edit
        self._progress_bar = None
        if self._is_batch_edit:
            self._progress_bar = QProgressBar()
            self._progress_bar.setVisible(False)
            self._progress_bar.setStyleSheet(ThemeManager.instance().get_qss(self._PROGRESS_STYLE_TEMPLATE))
            layout.addWidget(self._progress_bar)

        # Buttons
        buttons = QDialogButtonBox()
        self._ok_button = QPushButton(t("save"))
        self._ok_button.setObjectName("saveBtn")
        self._ok_button.setProperty("role", "primary")
        self._ok_button.setCursor(Qt.PointingHandCursor)
        self._ok_button.setEnabled(self._can_save)
        cancel_button = QPushButton(t("cancel"))
        cancel_button.setCursor(Qt.PointingHandCursor)
        cancel_button.setProperty("role", "cancel")

        buttons.addButton(self._ok_button, QDialogButtonBox.AcceptRole)
        buttons.addButton(cancel_button, QDialogButtonBox.RejectRole)

        self._ok_button.clicked.connect(self._save_changes)
        cancel_button.clicked.connect(self.reject)

        layout.addWidget(buttons)

        # Store first track for later use
        self._first_track = first_track

    def _add_file_info(self, form_layout: QFormLayout, track):
        """Add file information to the form for single track edit."""
        try:
            # Check if this is a local file
            if not track.path or track.path.startswith(('http://', 'https://', 'qqmusic:/')):
                # Online track - show online info
                from domain.track import TrackSource
                source_text = t("online_track")
                if hasattr(track, 'source'):
                    if track.source == TrackSource.QQ:
                        source_text = "QQ音乐"
                    elif track.source == TrackSource.QUARK:
                        source_text = "夸克网盘"
                    elif track.source == TrackSource.BAIDU:
                        source_text = "百度网盘"

                info_label = QLabel(source_text)
                theme = ThemeManager.instance().current_theme
                info_label.setStyleSheet(f"color: {theme.text_secondary}; font-size: 13px;")

                path_label = QLabel(track.path or t("online_streaming"))
                path_label.setStyleSheet(f"color: {theme.text_secondary}; font-size: 11px;")
                path_label.setWordWrap(True)

                # Add both labels in a vertical layout
                info_container = QWidget()
                info_layout = QVBoxLayout(info_container)
                info_layout.setContentsMargins(0, 0, 0, 0)
                info_layout.setSpacing(2)
                info_layout.addWidget(info_label)
                info_layout.addWidget(path_label)

                form_layout.addRow(t("source") + ":", info_container)
                return

            track_file = Path(track.path)
            if not track_file.exists():
                # File not found locally
                info_label = QLabel(t("file_not_found"))
                theme = ThemeManager.instance().current_theme
                info_label.setStyleSheet(f"color: {theme.text_secondary}; font-size: 13px;")

                path_label = QLabel(track.path)
                path_label.setStyleSheet(f"color: {theme.text_secondary}; font-size: 11px;")
                path_label.setWordWrap(True)

                # Add both labels in a vertical layout
                info_container = QWidget()
                info_layout = QVBoxLayout(info_container)
                info_layout.setContentsMargins(0, 0, 0, 0)
                info_layout.setSpacing(2)
                info_layout.addWidget(info_label)
                info_layout.addWidget(path_label)

                form_layout.addRow(t("file") + ":", info_container)
                return

            file_size = track_file.stat().st_size
            file_size_str = self._format_file_size(file_size)

            # Get audio codec info using mutagen
            import mutagen

            audio_info = mutagen.File(track.path)
            media_info = []

            if audio_info and hasattr(audio_info, "info"):
                info = audio_info.info
                # Bitrate
                if hasattr(info, "bitrate") and info.bitrate:
                    media_info.append(f"{info.bitrate // 1000} kbps")

                # Sample rate
                if hasattr(info, "sample_rate") and info.sample_rate:
                    media_info.append(f"{info.sample_rate // 1000} kHz")

                # Length/Duration
                if hasattr(info, "length") and info.length:
                    minutes = int(info.length // 60)
                    seconds = int(info.length % 60)
                    media_info.append(f"{minutes}:{seconds:02d}")

            # Format (codec)
            if audio_info:
                mime_type = audio_info.mime if hasattr(audio_info, "mime") else []
                if mime_type:
                    format_str = mime_type[0].split("/")[-1].upper()
                    media_info.append(format_str)
                else:
                    # Try to get format from type
                    if hasattr(audio_info, "type"):
                        media_info.append(audio_info.type)

            # Create info text
            file_info_text = f"{file_size_str}"
            if media_info:
                file_info_text += f" | {' | '.join(media_info)}"

            info_label = QLabel(file_info_text)
            theme = ThemeManager.instance().current_theme
            info_label.setStyleSheet(f"color: {theme.text_secondary}; font-size: 13px;")

            # File path
            path_label = QLabel(track.path)
            path_label.setStyleSheet(f"color: {theme.text_secondary}; font-size: 11px;")
            path_label.setWordWrap(True)

            # Add both labels in a vertical layout
            info_container = QWidget()
            info_layout = QVBoxLayout(info_container)
            info_layout.setContentsMargins(0, 0, 0, 0)
            info_layout.setSpacing(2)
            info_layout.addWidget(info_label)
            info_layout.addWidget(path_label)

            form_layout.addRow(t("file") + ":", info_container)

        except Exception as e:
            logger.error(f"Error displaying track info: {e}", exc_info=True)
            # Fallback to just show path if there's an error
            path_label = QLabel(track.path)
            path_label.setStyleSheet(f"color: {ThemeManager.instance().current_theme.text_secondary}; font-size: 11px;")
            path_label.setWordWrap(True)
            form_layout.addRow(t("file") + ":", path_label)

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

    def _save_changes(self):
        """Save the changes to tracks."""
        if self._is_batch_edit:
            self._save_batch_edit()
        else:
            self._save_single_edit()

    def _save_batch_edit(self):
        """Save changes for batch edit mode."""
        new_artist = self._artist_input.text().strip()
        new_album = self._album_input.text().strip()
        new_genre = self._genre_input.text().strip()

        if not self._update_artist_cb.isChecked() and not self._update_album_cb.isChecked() and not self._update_genre_cb.isChecked():
            MessageDialog.warning(
                self, t("warning"), t("select_fields_to_update")
            )
            return

        if not new_artist and not new_album and not new_genre:
            MessageDialog.warning(self, t("warning"), t("enter_artist_or_album"))
            return

        # Show progress
        if self._progress_bar:
            self._progress_bar.setVisible(True)
            self._progress_bar.setMaximum(len(self._track_ids))
            self._ok_button.setEnabled(False)
            self._ok_button.setText(t("saving") + "...")

        success_count = 0
        for i, track_id in enumerate(self._track_ids):
            track = self._library_service.get_track(track_id)
            if not track:
                continue

            # Determine values to save
            save_artist = (
                new_artist
                if (self._update_artist_cb.isChecked() and new_artist)
                else track.artist
            )
            save_album = (
                new_album
                if (self._update_album_cb.isChecked() and new_album)
                else track.album
            )
            save_genre = (
                new_genre
                if (self._update_genre_cb.isChecked() and new_genre)
                else track.genre
            )

            # Save to file
            success = MetadataService.save_metadata(
                track.path,
                title=track.title,
                artist=save_artist,
                album=save_album,
                genre=save_genre,
            )

            if success:
                self._library_service.update_track_metadata(
                    track_id,
                    title=track.title,
                    artist=save_artist,
                    album=save_album,
                    genre=save_genre,
                )
                # Emit metadata_updated signal to update play_queue
                EventBus.instance().metadata_updated.emit(track_id)
                success_count += 1

            # Update progress
            if self._progress_bar:
                self._progress_bar.setValue(i + 1)

        if success_count > 0:
            MessageDialog.information(
                self,
                t("success"),
                f"{t('batch_save_success')}: {success_count}/{len(self._track_ids)}",
            )
            self.tracks_updated.emit(self._track_ids)
            self.accept()
        else:
            MessageDialog.warning(self, "Error", t("media_save_failed"))

    def _save_single_edit(self):
        """Save changes for single track edit mode."""
        new_title = self._title_input.text().strip() or self._first_track.title
        new_artist = self._artist_input.text().strip() or self._first_track.artist
        new_album = self._album_input.text().strip() or self._first_track.album
        new_genre = self._genre_input.text().strip() or self._first_track.genre

        success = MetadataService.save_metadata(
            self._first_track.path,
            title=new_title,
            artist=new_artist,
            album=new_album,
            genre=new_genre,
        )

        if success:
            self._library_service.update_track_metadata(
                self._track_ids[0],
                title=new_title,
                artist=new_artist,
                album=new_album,
                genre=new_genre,
            )
            # Emit metadata_updated signal to update play_queue
            EventBus.instance().metadata_updated.emit(self._track_ids[0])
            MessageDialog.information(self, t("success"), t("media_saved"))
            self.tracks_updated.emit(self._track_ids)
            self.accept()
        else:
            MessageDialog.warning(self, "Error", t("media_save_failed"))

    def get_updated_track_ids(self) -> List[int]:
        """Get the list of track IDs that were updated."""
        return self._track_ids

    def refresh_theme(self):
        """Refresh theme when changed."""
        self._title_bar_controller.refresh_theme()
        if self._progress_bar:
            self._progress_bar.setStyleSheet(ThemeManager.instance().get_qss(self._PROGRESS_STYLE_TEMPLATE))

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
