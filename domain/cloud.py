"""
Cloud domain models - CloudProvider, CloudAccount, CloudFile.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from enum import Enum


class CloudProvider(Enum):
    """Cloud storage provider enumeration."""
    LOCAL = "local"      # Local music files
    QUARK = "quark"      # Quark cloud drive
    # Future extensions: ONEDRIVE, GOOGLE_DRIVE, DROPBOX, etc.


@dataclass
class CloudAccount:
    """Represents a cloud storage account (Quark, OneDrive, etc.)"""

    id: Optional[int] = None
    provider: str = ""  # "quark", "onedrive", etc.
    account_name: str = ""  # User-defined name
    account_email: str = ""  # From provider
    access_token: str = ""  # Cookie or OAuth token
    refresh_token: str = ""  # For token refresh
    token_expires_at: Optional[datetime] = None
    is_active: bool = True
    last_folder_path: str = "/"  # Last opened folder display path (e.g., /音乐/test)
    last_fid_path: str = "0"  # FID path (e.g., /fid1/fid2/fid3) for navigation
    last_playing_fid: str = ""  # Last playing file ID
    last_position: float = 0.0  # Last playback position in seconds
    last_playing_local_path: str = ""  # Local path of last playing file for faster restore
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()


@dataclass
class CloudFile:
    """Cached metadata for cloud drive files"""

    id: Optional[int] = None
    account_id: int = 0
    file_id: str = ""  # Provider's file identifier
    parent_id: str = ""  # Parent folder ID (empty for root)
    name: str = ""
    file_type: str = ""  # "folder", "audio", "other"
    size: Optional[int] = None
    mime_type: Optional[str] = None
    duration: Optional[float] = None  # For audio files
    metadata: Optional[str] = None  # JSON for provider-specific data
    local_path: Optional[str] = None  # Downloaded local file path
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
