"""
Unified playlist item model for local and cloud playback.
"""

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from .cloud import CloudProvider

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
    source_type: CloudProvider = CloudProvider.LOCAL

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
        Create a PlaylistItem from a local Track.

        Args:
            track: Track object from database

        Returns:
            PlaylistItem instance
        """
        return cls(
            source_type=CloudProvider.LOCAL,
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
            local_path: str = ""
    ) -> "PlaylistItem":
        """
        Create a PlaylistItem from a cloud file.

        Args:
            cloud_file: CloudFile object
            account_id: Cloud account ID
            local_path: Optional local path if already downloaded

        Returns:
            PlaylistItem instance
        """
        return cls(
            source_type=CloudProvider.QUARK,  # Currently only Quark is supported
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
        source_type = CloudProvider.LOCAL
        if data.get("cloud_file_id"):
            source_type = CloudProvider.QUARK

        return cls(
            source_type=source_type,
            track_id=data.get("id"),
            cloud_file_id=data.get("cloud_file_id"),
            cloud_account_id=data.get("cloud_account_id"),
            local_path=data.get("path", ""),
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
            "source_type": self.source_type.value,
            "cloud_file_id": self.cloud_file_id,
            "cloud_account_id": self.cloud_account_id,
            "needs_download": self.needs_download,
            "needs_metadata": self.needs_metadata,
            "is_cloud": self.is_cloud,
        }

    @property
    def is_cloud(self) -> bool:
        """Check if this is a cloud file."""
        return self.source_type != CloudProvider.LOCAL

    @property
    def is_local(self) -> bool:
        """Check if this is a local file."""
        return self.source_type == CloudProvider.LOCAL

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
        source = "local" if self.is_local else f"cloud({self.source_type.value})"
        return f"PlaylistItem({source}: {self.display_title} - {self.display_artist})"

    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return (
            f"PlaylistItem(source_type={self.source_type}, "
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

        source_type = "local" if self.is_local else "cloud"
        cloud_type = self.source_type.value if self.is_cloud else ""

        return PlayQueueItem(
            position=position,
            source_type=source_type,
            cloud_type=cloud_type,
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

        source_type = CloudProvider.LOCAL
        if item.source_type == "cloud" and item.cloud_type:
            source_type = CloudProvider(item.cloud_type)

        # Try to get cover_path from database
        cover_path = None
        if db:
            try:
                # For local tracks, get by track_id
                if item.track_id:
                    track = db.get_track(item.track_id)
                    if track:
                        cover_path = track.cover_path
                # For cloud files, get by cloud_file_id
                elif item.cloud_file_id:
                    track = db.get_track_by_cloud_file_id(item.cloud_file_id)
                    if track:
                        cover_path = track.cover_path
            except Exception:
                pass  # Ignore errors, cover_path will remain None

        # Determine the correct local_path to use
        # Always prioritize the latest path from database if track_id exists
        # This ensures that after file organization, the queue uses the new paths
        local_path = item.local_path
        if db and item.track_id:
            try:
                # For tracks with track_id (local or downloaded cloud files), get the latest path
                track = db.get_track(item.track_id)
                if track and track.path:
                    local_path = track.path
            except Exception:
                pass  # Fallback to item.local_path
        elif db and item.cloud_file_id and not local_path:
            try:
                # For cloud files without local_path, try to get from cloud_files table
                cloud_file = db.get_cloud_file_by_file_id(item.cloud_file_id)
                if cloud_file and cloud_file.local_path:
                    local_path = cloud_file.local_path
            except Exception:
                pass  # Ignore errors, local_path will remain empty

        # Check if local file actually exists for cloud files
        # If file was deleted, we need to re-download
        file_exists = local_path and Path(local_path).exists()

        # Only clear path and set needs_download for cloud files
        if item.cloud_file_id and not file_exists:
            needs_download = True
            final_local_path = ""
        else:
            needs_download = bool(item.cloud_file_id and not local_path)
            final_local_path = local_path

        return cls(
            source_type=source_type,
            track_id=item.track_id,
            cloud_file_id=item.cloud_file_id,
            cloud_account_id=item.cloud_account_id,
            local_path=final_local_path,
            title=item.title,
            artist=item.artist,
            album=item.album,
            duration=item.duration,
            cover_path=cover_path,
            needs_download=needs_download,
            needs_metadata=bool(item.cloud_file_id),  # Cloud files need metadata
        )
