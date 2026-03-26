"""
Metadata service module.
"""

from .cover_service import CoverService
from .metadata_service import MetadataService
from .artist_parser import split_artists, normalize_artist_name, get_canonical_artist_name

__all__ = ['MetadataService', 'CoverService', 'split_artists', 'normalize_artist_name', 'get_canonical_artist_name']
