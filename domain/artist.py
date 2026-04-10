"""
Artist domain model - Aggregated artist entity.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(slots=True)
class Artist:
    """
    Represents an artist aggregated from tracks.

    This is a pure domain model with no external dependencies.
    Artists are derived from track metadata, not stored separately.
    """
    name: str
    cover_path: Optional[str] = None
    song_count: int = 0
    album_count: int = 0
    _id_cache: Optional[str] = field(default=None, init=False, repr=False, compare=False)

    @property
    def display_name(self) -> str:
        """Get display name for the artist."""
        return self.name if self.name else "Unknown Artist"

    @property
    def id(self) -> str:
        """Generate a unique ID for the artist based on name."""
        if self._id_cache is None:
            self._id_cache = self.name.lower() if self.name else "unknown"
        return self._id_cache

    def __hash__(self):
        """Make Artist hashable for use in sets."""
        return hash(self.id)

    def __eq__(self, other):
        """Equality based on ID."""
        if isinstance(other, Artist):
            return self.id == other.id
        return False
