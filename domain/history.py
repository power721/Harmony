"""
Play history and favorites domain models.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class PlayHistory:
    """Represents a play history entry."""

    id: Optional[int] = None
    track_id: int = 0
    played_at: Optional[datetime] = None
    play_count: int = 1

    def __post_init__(self):
        if self.played_at is None:
            self.played_at = datetime.now()


@dataclass
class Favorite:
    """Represents a favorite track."""

    id: Optional[int] = None
    track_id: int = 0
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
