"""
Playlist domain model.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(slots=True)
class Playlist:
    """Represents a playlist."""

    id: Optional[int] = None
    name: str = ""
    folder_id: Optional[int] = None
    position: int = 0
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
