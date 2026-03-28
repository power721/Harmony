"""
Metadata service module.
"""

from .cover_service import CoverService
from .metadata_service import MetadataService
from .artist_parser import split_artists, split_artists_aware, normalize_artist_name, get_canonical_artist_name
from .color_extractor import extract_dominant_color, extract_from_file, ColorWorker

__all__ = [
    'MetadataService', 'CoverService',
    'split_artists', 'split_artists_aware', 'normalize_artist_name', 'get_canonical_artist_name',
    'extract_dominant_color', 'extract_from_file', 'ColorWorker',
]
