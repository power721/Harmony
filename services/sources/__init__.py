"""
Source providers for cover art and lyrics search.

This module provides strategy pattern implementations for multiple
online sources (NetEase, QQ Music, iTunes, etc.).
"""

from .base import CoverSource, LyricsSource, ArtistCoverSource
from .cover_sources import (
    NetEaseCoverSource,
    QQMusicCoverSource,
    ITunesCoverSource,
    LastFmCoverSource,
    MusicBrainzCoverSource,
    SpotifyCoverSource,
)
from .lyrics_sources import (
    NetEaseLyricsSource,
    QQMusicLyricsSource,
    KugouLyricsSource,
)
from .artist_cover_sources import (
    NetEaseArtistCoverSource,
    QQMusicArtistCoverSource,
    ITunesArtistCoverSource,
    SpotifyArtistCoverSource,
)

__all__ = [
    # Base classes
    "CoverSource",
    "LyricsSource",
    "ArtistCoverSource",
    # Cover sources
    "NetEaseCoverSource",
    "QQMusicCoverSource",
    "ITunesCoverSource",
    "LastFmCoverSource",
    "MusicBrainzCoverSource",
    "SpotifyCoverSource",
    # Lyrics sources
    "NetEaseLyricsSource",
    "QQMusicLyricsSource",
    "KugouLyricsSource",
    # Artist cover sources
    "NetEaseArtistCoverSource",
    "QQMusicArtistCoverSource",
    "ITunesArtistCoverSource",
    "SpotifyArtistCoverSource",
]
