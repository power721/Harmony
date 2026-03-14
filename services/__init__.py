"""
Services module - Business logic layer organized by domain.
"""

# Playback services
from .playback import PlaybackService, QueueService

# Library services
from .library import LibraryService

# Lyrics services
from .lyrics import LyricsService

# Metadata services
from .metadata import MetadataService, CoverService

# Cloud services
from .cloud import QuarkDriveService, CloudDownloadService

# AI services
from .ai import AIMetadataService, AcoustIDService

__all__ = [
    'PlaybackService', 'QueueService',
    'LibraryService',
    'LyricsService',
    'MetadataService', 'CoverService',
    'QuarkDriveService', 'CloudDownloadService',
    'AIMetadataService', 'AcoustIDService',
]
