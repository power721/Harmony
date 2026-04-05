"""
Repository interfaces - Abstract base classes for data access.
"""

from typing import List, Optional, Protocol

from domain.cloud import CloudAccount, CloudFile
from domain.playback import PlayQueueItem
from domain.playlist import Playlist
from domain.track import Track, TrackId


class TrackRepository(Protocol):
    """Abstract interface for track data access."""

    def get_by_id(self, track_id: TrackId) -> Optional[Track]:
        """Get a track by ID."""
        ...

    def get_by_ids(self, track_ids: List[TrackId]) -> List[Track]:
        """Get multiple tracks by IDs in batch."""
        ...

    def get_by_path(self, path: str) -> Optional[Track]:
        """Get a track by file path."""
        ...

    def get_all(self) -> List[Track]:
        """Get all tracks."""
        ...

    def search(self, query: str, limit: int = 100) -> List[Track]:
        """Search tracks by query."""
        ...

    def add(self, track: Track) -> TrackId:
        """Add a new track and return its ID."""
        ...

    def update(self, track: Track) -> bool:
        """Update an existing track."""
        ...

    def delete(self, track_id: TrackId) -> bool:
        """Delete a track by ID."""
        ...

    def get_by_cloud_file_id(self, cloud_file_id: str) -> Optional[Track]:
        """Get a track by cloud file ID."""
        ...

    def get_track_position(self, track_id: TrackId) -> Optional[int]:
        """Get the zero-based library position for a track in default ordering."""
        ...


class PlaylistRepository(Protocol):
    """Abstract interface for playlist data access."""

    def get_by_id(self, playlist_id: int) -> Optional[Playlist]:
        """Get a playlist by ID."""
        ...

    def get_all(self) -> List[Playlist]:
        """Get all playlists."""
        ...

    def get_tracks(self, playlist_id: int) -> List[Track]:
        """Get all tracks in a playlist."""
        ...

    def add(self, playlist: Playlist) -> int:
        """Add a new playlist and return its ID."""
        ...

    def update(self, playlist: Playlist) -> bool:
        """Update an existing playlist."""
        ...

    def delete(self, playlist_id: int) -> bool:
        """Delete a playlist by ID."""
        ...

    def add_track(self, playlist_id: int, track_id: TrackId) -> bool:
        """Add a track to a playlist."""
        ...

    def remove_track(self, playlist_id: int, track_id: TrackId) -> bool:
        """Remove a track from a playlist."""
        ...


class CloudRepository(Protocol):
    """Abstract interface for cloud data access."""

    def get_account_by_id(self, account_id: int) -> Optional[CloudAccount]:
        """Get a cloud account by ID."""
        ...

    def get_all_accounts(self) -> List[CloudAccount]:
        """Get all cloud accounts."""
        ...

    def add_account(self, account: CloudAccount) -> int:
        """Add a new cloud account."""
        ...

    def update_account(self, account: CloudAccount) -> bool:
        """Update a cloud account."""
        ...

    def delete_account(self, account_id: int) -> bool:
        """Delete a cloud account."""
        ...

    def get_file_by_id(self, file_id: str) -> Optional[CloudFile]:
        """Get a cloud file by file ID."""
        ...

    def get_files_by_account(self, account_id: int) -> List[CloudFile]:
        """Get all files for an account."""
        ...

    def add_file(self, file: CloudFile) -> int:
        """Add a cloud file."""
        ...


class QueueRepository(Protocol):
    """Abstract interface for play queue persistence."""

    def load(self) -> List[PlayQueueItem]:
        """Load the saved play queue."""
        ...

    def save(self, items: List[PlayQueueItem]) -> bool:
        """Save the play queue."""
        ...

    def clear(self) -> bool:
        """Clear the saved play queue."""
        ...


class HistoryRepository(Protocol):
    """Abstract interface for play history data access."""

    def add(self, track_id: TrackId) -> bool:
        """Add a play history entry."""
        ...

    def get_recent(self, limit: int = 50) -> List[Track]:
        """Get recently played tracks."""
        ...

    def get_favorites(self) -> List[Track]:
        """Get favorite tracks."""
        ...

    def is_favorite(self, track_id: TrackId) -> bool:
        """Check if a track is a favorite."""
        ...

    def add_favorite(self, track_id: TrackId) -> bool:
        """Add a track to favorites."""
        ...

    def remove_favorite(self, track_id: TrackId) -> bool:
        """Remove a track from favorites."""
        ...
