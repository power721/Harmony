"""
Unified playlist item model for local and cloud playback.
"""

import logging
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from .track import TrackSource

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from domain.track import Track
    from domain.cloud import CloudFile


@dataclass
class PlaylistItem:
    """
    Unified playlist item for both local and cloud playback.

    This class abstracts the differences between local tracks and cloud files,
    providing a consistent interface for the playback engine.
    """
    # Source type
    source: TrackSource = TrackSource.LOCAL

    # Local track fields
    track_id: Optional[int] = None

    # Cloud file fields
    cloud_file_id: Optional[str] = None
    cloud_account_id: Optional[int] = None

    # Common fields
    local_path: str = ""
    title: str = ""
    artist: str = ""
    album: str = ""
    duration: float = 0.0
    cover_path: Optional[str] = None

    # Metadata state
    needs_download: bool = False  # Whether cloud file needs to be downloaded
    needs_metadata: bool = True  # Whether metadata needs to be extracted

    # Additional metadata (for cloud files)
    cloud_file_size: Optional[int] = None

    @classmethod
    def from_track(cls, track: "Track") -> "PlaylistItem":
        """
        Create a PlaylistItem from a Track.

        Handles both local tracks and online tracks (QQ Music, etc.)
        by checking if path is empty (indicating online track needs download).

        Args:
            track: Track object from database

        Returns:
            PlaylistItem instance
        """
        # Check if this is an online track (empty path or QQ source)
        is_online = not track.path or track.source == TrackSource.QQ

        if is_online:
            return cls(
                source=TrackSource.QQ,
                track_id=track.id,
                cloud_file_id=track.cloud_file_id,
                local_path="",  # No local path yet
                title=track.title or "",
                artist=track.artist or "",
                album=track.album or "",
                duration=track.duration or 0.0,
                cover_path=track.cover_path,
                needs_download=True,  # Needs download before playback
                needs_metadata=False,
            )

        # Local track
        return cls(
            source=TrackSource.LOCAL,
            track_id=track.id,
            local_path=track.path,
            title=track.title or "",
            artist=track.artist or "",
            album=track.album or "",
            duration=track.duration or 0.0,
            cover_path=track.cover_path,
            needs_download=False,
            needs_metadata=False,  # Local tracks already have metadata
        )

    @classmethod
    def from_cloud_file(
            cls,
            cloud_file: "CloudFile",
            account_id: int,
            local_path: str = "",
            provider: str = "QUARK"
    ) -> "PlaylistItem":
        """
        Create a PlaylistItem from a cloud file.

        Args:
            cloud_file: CloudFile object
            account_id: Cloud account ID
            local_path: Optional local path if already downloaded
            provider: Cloud provider type ("QUARK" or "BAIDU")

        Returns:
            PlaylistItem instance
        """
        source = TrackSource.QUARK if provider.upper() == "QUARK" else TrackSource.BAIDU
        return cls(
            source=source,
            cloud_file_id=cloud_file.file_id,
            cloud_account_id=account_id,
            local_path=local_path,
            title=cloud_file.name or "",
            artist="",
            album="",
            duration=cloud_file.duration or 0.0,
            needs_download=not bool(local_path),  # Needs download if no local path
            needs_metadata=True,  # Cloud files need metadata extraction
            cloud_file_size=cloud_file.size,
        )

    @classmethod
    def from_dict(cls, data: dict) -> "PlaylistItem":
        """
        Create a PlaylistItem from a dictionary (for backward compatibility).

        Args:
            data: Dictionary with track data

        Returns:
            PlaylistItem instance
        """
        # Determine source from saved value or infer from other fields
        source_str = data.get("source") or data.get("source")
        if source_str:
            try:
                source = TrackSource(source_str)
            except ValueError:
                # Fallback to inference if invalid value
                source = TrackSource.LOCAL
                if data.get("cloud_file_id"):
                    source = TrackSource.QUARK
        else:
            # Legacy: infer from other fields
            source = TrackSource.LOCAL
            if data.get("cloud_file_id"):
                source = TrackSource.QUARK

        return cls(
            source=source,
            track_id=data.get("id"),
            cloud_file_id=data.get("cloud_file_id"),
            cloud_account_id=data.get("cloud_account_id"),
            local_path=data.get("path", "") or data.get("local_path", ""),
            title=data.get("title", ""),
            artist=data.get("artist", ""),
            album=data.get("album", ""),
            duration=data.get("duration", 0.0),
            cover_path=data.get("cover_path"),
            needs_download=data.get("needs_download", False),
            needs_metadata=data.get("needs_metadata", True),
        )

    def to_dict(self) -> dict:
        """
        Convert to dictionary (for backward compatibility with PlayerEngine).

        Returns:
            Dictionary representation
        """
        return {
            "id": self.track_id,
            "path": self.local_path,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "duration": self.duration,
            "cover_path": self.cover_path,
            "source": self.source.value,
            "source": self.source.value,
            "cloud_file_id": self.cloud_file_id,
            "cloud_account_id": self.cloud_account_id,
            "needs_download": self.needs_download,
            "needs_metadata": self.needs_metadata,
            "is_cloud": self.is_cloud,
        }

    @property
    def is_cloud(self) -> bool:
        """Check if this is a cloud file."""
        return self.source != TrackSource.LOCAL

    @property
    def is_local(self) -> bool:
        """Check if this is a local file."""
        return self.source == TrackSource.LOCAL

    @property
    def is_ready(self) -> bool:
        """Check if the item is ready for playback (has valid local path)."""
        return bool(self.local_path) and not self.needs_download

    @property
    def display_title(self) -> str:
        """Get display title (fallback to filename if no title)."""
        if self.title:
            return self.title
        if self.local_path:
            import os
            return os.path.basename(self.local_path)
        return "Unknown Track"

    @property
    def display_artist(self) -> str:
        """Get display artist (fallback to 'Unknown Artist')."""
        return self.artist if self.artist else "Unknown Artist"

    def __str__(self) -> str:
        """String representation for debugging."""
        source = "local" if self.is_local else f"cloud({self.source.value})"
        return f"PlaylistItem({source}: {self.display_title} - {self.display_artist})"

    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return (
            f"PlaylistItem(source={self.source}, "
            f"track_id={self.track_id}, cloud_file_id={self.cloud_file_id}, "
            f"path={self.local_path}, title={self.title}, "
            f"needs_download={self.needs_download})"
        )

    def to_play_queue_item(self, position: int = 0) -> "PlayQueueItem":
        """
        Convert to PlayQueueItem for database persistence.

        Args:
            position: Position in the queue

        Returns:
            PlayQueueItem instance
        """
        from domain.playback import PlayQueueItem

        return PlayQueueItem(
            position=position,
            source=self.source.value,  # "Local", "QQ", "QUARK", "BAIDU"
            track_id=self.track_id,
            cloud_file_id=self.cloud_file_id,
            cloud_account_id=self.cloud_account_id,
            local_path=self.local_path,
            title=self.title,
            artist=self.artist,
            album=self.album,
            duration=self.duration,
        )

    @classmethod
    def from_play_queue_item(cls, item: "PlayQueueItem", db=None) -> "PlaylistItem":
        """
        Create a PlaylistItem from a PlayQueueItem.

        Args:
            item: PlayQueueItem from database
            db: Optional DatabaseManager instance to fetch cover_path for local tracks

        Returns:
            PlaylistItem instance
        """
        from pathlib import Path

        # Determine source from item.source
        try:
            source = TrackSource(item.source)
        except ValueError:
            source = TrackSource.LOCAL

        # Try to get metadata from database
        cover_path = None
        title = item.title
        artist = item.artist
        album = item.album
        duration = item.duration
        track_id = item.track_id
        needs_metadata = False

        if db:
            try:
                # For local tracks, get by track_id
                if item.track_id and source == TrackSource.LOCAL:
                    track = db.get_track(item.track_id)
                    if track:
                        cover_path = track.cover_path
                        title = track.title or title
                        artist = track.artist or artist
                        album = track.album or album
                        duration = track.duration or duration
                        needs_metadata = False
                # For online/cloud tracks, metadata is already stored in queue
                elif source in (TrackSource.QQ, TrackSource.QUARK, TrackSource.BAIDU):
                    needs_metadata = False
                    # Try to get cover_path from tracks table
                    if item.cloud_file_id:
                        track = db.get_track_by_cloud_file_id(item.cloud_file_id)
                        if track:
                            cover_path = track.cover_path
                            track_id = track.id
                # For local files without track_id, try to find by path
                elif item.local_path and not item.cloud_file_id:
                    track = db.get_track_by_path(item.local_path)
                    if track:
                        cover_path = track.cover_path
                        title = track.title or title
                        artist = track.artist or artist
                        album = track.album or album
                        duration = track.duration or duration
                        track_id = track.id
                        needs_metadata = False
            except Exception as e:
                logger.warning(f"Error fetching track metadata from DB: {e}")
                pass  # Ignore errors, use item values

        # Determine the correct local_path to use
        local_path = item.local_path
        if db and track_id and source == TrackSource.LOCAL:
            try:
                track = db.get_track(track_id)
                if track and track.path:
                    local_path = track.path
            except Exception as e:
                logger.warning(f"Error fetching track path from DB: {e}")

        # Check if local file actually exists
        file_exists = local_path and Path(local_path).exists()

        # Determine needs_download
        needs_download = False
        if source == TrackSource.QQ:
            # QQ Music tracks need download if file doesn't exist
            needs_download = not file_exists
            if not file_exists:
                local_path = ""
        elif source in (TrackSource.QUARK, TrackSource.BAIDU):
            # Cloud files need download if no local path
            if item.cloud_file_id and not file_exists:
                needs_download = True
                local_path = ""

        return cls(
            source=source,
            track_id=track_id,
            cloud_file_id=item.cloud_file_id,
            cloud_account_id=item.cloud_account_id,
            local_path=local_path,
            title=title,
            artist=artist,
            album=album,
            duration=duration,
            cover_path=cover_path,
            needs_download=needs_download,
            needs_metadata=needs_metadata,
        )
