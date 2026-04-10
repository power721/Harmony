"""
Album domain model - Aggregated album entity.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(slots=True)
class Album:
    """
    Represents an album aggregated from tracks.

    This is a pure domain model with no external dependencies.
    Albums are derived from track metadata, not stored separately.
    """
    name: str
    artist: str
    cover_path: Optional[str] = None
    song_count: int = 0
    duration: float = 0.0  # Total duration in seconds
    year: Optional[int] = None
    _id_cache: Optional[str] = field(default=None, init=False, repr=False, compare=False)

    @property
    def display_name(self) -> str:
        """Get display name for the album."""
        return self.name if self.name else "Unknown Album"

    @property
    def display_artist(self) -> str:
        """Get display artist for the album."""
        return self.artist if self.artist else "Unknown Artist"

    @property
    def id(self) -> str:
        """Generate a unique ID for the album based on name and artist."""
        if self._id_cache is None:
            self._id_cache = f"{self.artist}:{self.name}".lower()
        return self._id_cache

    def __hash__(self):
        """Make Album hashable for use in sets."""
        return hash(self.id)

    def __eq__(self, other):
        """Equality based on ID."""
        if isinstance(other, Album):
            return self.id == other.id
        return False
