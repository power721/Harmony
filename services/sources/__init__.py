"""
Source providers for cover art and lyrics search.

This module provides strategy pattern implementations for multiple
online sources (NetEase, QQ Music, iTunes, etc.).
"""

from .base import CoverSource, LyricsSource, ArtistCoverSource
from .cover_sources import (
    MusicBrainzCoverSource,
    SpotifyCoverSource,
)
from .artist_cover_sources import (
    SpotifyArtistCoverSource,
)

__all__ = [
    # Base classes
    "CoverSource",
    "LyricsSource",
    "ArtistCoverSource",
    # Cover sources
    "MusicBrainzCoverSource",
    "SpotifyCoverSource",
    # Artist cover sources
    "SpotifyArtistCoverSource",
]
