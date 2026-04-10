"""
Genre domain model - Aggregated genre entity.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(slots=True)
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
    _id_cache: Optional[str] = field(default=None, init=False, repr=False, compare=False)

    @property
    def display_name(self) -> str:
        """Get display name for the genre."""
        return self.name if self.name else "Unknown Genre"

    @property
    def id(self) -> str:
        """Generate a unique ID for the genre based on name."""
        if self._id_cache is None:
            self._id_cache = self.name.lower() if self.name else f"unknown:{id(self)}"
        return self._id_cache

    def __hash__(self):
        """Make Genre hashable for use in sets."""
        return hash(self.id)

    def __eq__(self, other):
        """Equality based on ID."""
        if isinstance(other, Genre):
            return self.id == other.id
        return False
