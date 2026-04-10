"""
Unified playlist item model for local and cloud playback.
"""

import os
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from .track import TrackSource

if TYPE_CHECKING:
    from domain.track import Track
    from domain.cloud import CloudFile
    from domain.playback import PlayQueueItem


@dataclass(slots=True)
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
    online_provider_id: Optional[str] = None
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

    # Download state
    download_failed: bool = False  # Whether download has failed

    @classmethod
    def from_track(cls, track: "Track") -> "PlaylistItem":
        """
        Create a PlaylistItem from a Track.

        Handles both local tracks and plugin-provided online tracks
        by checking if path is empty (indicating online track needs download).

        Args:
            track: Track object from database

        Returns:
            PlaylistItem instance
        """
        # Online tracks may have either a virtual path (download required) or a
        # real cached file path after download. Keep cached files playable.
        has_cached_local_file = bool(track.path) and os.path.exists(track.path)
        is_online = not track.path or (track.source == TrackSource.ONLINE and not has_cached_local_file)

        if is_online:
            return cls(
                source=track.source,
                track_id=track.id,
                cloud_file_id=track.cloud_file_id,
                online_provider_id=track.online_provider_id,
                local_path="",  # No local path yet
                title=track.title or "",
                artist=track.artist or "",
                album=track.album or "",
                duration=track.duration or 0.0,
                cover_path=track.cover_path,
                needs_download=True,  # Needs download before playback
                needs_metadata=False,
            )

        # Local-ready track, including downloaded online/cloud items that now
        # have a concrete local path.
        return cls(
            source=track.source,
            track_id=track.id,
            cloud_file_id=track.cloud_file_id,
            online_provider_id=track.online_provider_id,
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
        source_str = data.get("source")
        if source_str:
            source = TrackSource.from_value(source_str)
            # Legacy fallback: unknown cloud sources defaulted to QUARK.
            if (
                source == TrackSource.LOCAL
                and data.get("cloud_file_id")
                and str(source_str).strip() not in ("Local",)
            ):
                source = TrackSource.QUARK
        else:
            # Legacy: infer from other fields
            source = TrackSource.LOCAL
            if data.get("cloud_file_id"):
                source = TrackSource.QUARK

        # Determine needs_metadata based on source if not provided
        if "needs_metadata" in data:
            needs_metadata = data["needs_metadata"]
        else:
            needs_metadata = source != TrackSource.LOCAL

        return cls(
            source=source,
            track_id=int(data["id"]) if data.get("id") is not None else None,
            cloud_file_id=data.get("cloud_file_id"),
            online_provider_id=data.get("online_provider_id"),
            cloud_account_id=data.get("cloud_account_id"),
            local_path=data.get("path", "") or data.get("local_path", ""),
            title=data.get("title", ""),
            artist=data.get("artist", ""),
            album=data.get("album", ""),
            duration=float(data.get("duration", 0.0)),
            cover_path=data.get("cover_path"),
            needs_download=data.get("needs_download", False),
            needs_metadata=needs_metadata,
            download_failed=data.get("download_failed", False),
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
            "cloud_file_id": self.cloud_file_id,
            "online_provider_id": self.online_provider_id,
            "cloud_account_id": self.cloud_account_id,
            "needs_download": self.needs_download,
            "needs_metadata": self.needs_metadata,
            "download_failed": self.download_failed,
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
    def is_online(self) -> bool:
        """Check if this is an online music item provided by a plugin."""
        return self.source == TrackSource.ONLINE

    @property
    def is_ready(self) -> bool:
        """Check if the item is ready for playback (has valid local path)."""
        return bool(self.local_path) and not self.needs_download and not self.download_failed

    @property
    def display_title(self) -> str:
        """Get display title (fallback to filename if no title)."""
        if self.title:
            return self.title
        if self.local_path:
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
            source=self.source.value,  # "Local", "ONLINE", "QUARK", "BAIDU"
            track_id=self.track_id,
            cloud_file_id=self.cloud_file_id,
            online_provider_id=self.online_provider_id,
            cloud_account_id=self.cloud_account_id,
            local_path=self.local_path,
            title=self.title,
            artist=self.artist,
            album=self.album,
            duration=self.duration,
            download_failed=self.download_failed,
        )

    @classmethod
    def from_play_queue_item(cls, item: "PlayQueueItem") -> "PlaylistItem":
        """
        Create a PlaylistItem from a PlayQueueItem (pure conversion, no DB access).

        This method does NOT access the database. It only converts the data
        from PlayQueueItem. Metadata enrichment should be done by the service layer.

        Args:
            item: PlayQueueItem from database

        Returns:
            PlaylistItem instance
        """
        from pathlib import Path

        # Determine source from item.source
        source = TrackSource.from_value(item.source)

        # Determine needs_download based on source and path
        local_path = item.local_path or ""
        file_exists = local_path and Path(local_path).exists()

        needs_download = False
        if source == TrackSource.ONLINE:
            # Online tracks need download if file doesn't exist
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
            track_id=item.track_id,
            cloud_file_id=item.cloud_file_id,
            online_provider_id=item.online_provider_id,
            cloud_account_id=item.cloud_account_id,
            local_path=local_path,
            title=item.title or "",
            artist=item.artist or "",
            album=item.album or "",
            duration=item.duration or 0.0,
            cover_path=None,  # Service layer should enrich this
            needs_download=needs_download,
            needs_metadata=False,
            download_failed=item.download_failed,
        )

    def with_metadata(
        self,
        cover_path: Optional[str] = None,
        title: Optional[str] = None,
        artist: Optional[str] = None,
        album: Optional[str] = None,
        duration: Optional[float] = None,
        local_path: Optional[str] = None,
        track_id: Optional[int] = None,
        needs_download: Optional[bool] = None,
        needs_metadata: Optional[bool] = None,
        download_failed: Optional[bool] = None,
    ) -> "PlaylistItem":
        """
        Return a new PlaylistItem with updated metadata (immutable update).

        This method creates a new instance with specified fields updated,
        keeping the original instance unchanged.

        Args:
            cover_path: New cover path
            title: New title
            artist: New artist
            album: New album
            duration: New duration
            local_path: New local path
            track_id: New track ID
            needs_download: New needs_download flag
            needs_metadata: New needs_metadata flag
            download_failed: New download_failed flag

        Returns:
            New PlaylistItem instance with updated fields
        """
        return PlaylistItem(
            source=self.source,
            track_id=track_id if track_id is not None else self.track_id,
            cloud_file_id=self.cloud_file_id,
            online_provider_id=self.online_provider_id,
            cloud_account_id=self.cloud_account_id,
            local_path=local_path if local_path is not None else self.local_path,
            title=title if title is not None else self.title,
            artist=artist if artist is not None else self.artist,
            album=album if album is not None else self.album,
            duration=duration if duration is not None else self.duration,
            cover_path=cover_path if cover_path is not None else self.cover_path,
            needs_download=needs_download if needs_download is not None else self.needs_download,
            needs_metadata=needs_metadata if needs_metadata is not None else self.needs_metadata,
            download_failed=download_failed if download_failed is not None else self.download_failed,
            cloud_file_size=self.cloud_file_size,
        )
