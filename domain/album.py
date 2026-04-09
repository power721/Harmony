"""
Album domain model - Aggregated album entity.
"""

from dataclasses import dataclass
from functools import cached_property
from typing import Optional


@dataclass
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

    @property
    def display_name(self) -> str:
        """Get display name for the album."""
        return self.name if self.name else "Unknown Album"

    @property
    def display_artist(self) -> str:
        """Get display artist for the album."""
        return self.artist if self.artist else "Unknown Artist"

    @cached_property
    def id(self) -> str:
        """Generate a unique ID for the album based on name and artist."""
        # Use name + artist as unique identifier
        return f"{self.artist}:{self.name}".lower()

    def __hash__(self):
        """Make Album hashable for use in sets."""
        return hash(self.id)

    def __eq__(self, other):
        """Equality based on ID."""
        if isinstance(other, Album):
            return self.id == other.id
        return False
