"""
Genre domain model - Aggregated genre entity.
"""

from dataclasses import dataclass
from functools import cached_property
from typing import Optional


@dataclass
class Genre:
    """
    Represents a genre aggregated from tracks.

    This is a pure domain model with no external dependencies.
    Genres are derived from track metadata, not stored separately.
    """
    name: str = ""
    cover_path: Optional[str] = None
    song_count: int = 0
    album_count: int = 0
    duration: float = 0.0  # Total duration in seconds

    @property
    def display_name(self) -> str:
        """Get display name for the genre."""
        return self.name if self.name else "Unknown Genre"

    @property
    def id(self) -> str:
        """Generate a unique ID for the genre based on name."""
        if self.name:
            return self._named_id
        return f"unknown:{id(self)}"

    @cached_property
    def _named_id(self) -> str:
        """Cache the normalized ID for named genres."""
        return self.name.lower()

    def __hash__(self):
        """Make Genre hashable for use in sets."""
        return hash(self.id)

    def __eq__(self, other):
        """Equality based on ID."""
        if isinstance(other, Genre):
            return self.id == other.id
        return False
