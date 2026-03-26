"""
UI dialogs for Harmony music player.
"""

from .qqmusic_qr_login_dialog import QQMusicQRLoginDialog
from .settings_dialog import GeneralSettingsDialog
from .album_cover_download_dialog import AlbumCoverDownloadDialog
from .artist_cover_download_dialog import ArtistCoverDownloadDialog
from .base_cover_download_dialog import BaseCoverDownloadDialog
from .cloud_login_dialog import CloudLoginDialog
from .provider_select_dialog import ProviderSelectDialog
from .help_dialog import HelpDialog
from .organize_files_dialog import OrganizeFilesDialog
from .lyrics_download_dialog import LyricsDownloadDialog
from .track_cover_download_dialog import TrackCoverDownloadDialog, CoverDownloadDialog
from .artist_rename_dialog import ArtistRenameDialog
from .album_rename_dialog import AlbumRenameDialog
from .edit_media_info_dialog import EditMediaInfoDialog

__all__ = [
    'QQMusicQRLoginDialog',
    'GeneralSettingsDialog',
    'AlbumCoverDownloadDialog',
    'ArtistCoverDownloadDialog',
    'BaseCoverDownloadDialog',
    'CloudLoginDialog',
    'ProviderSelectDialog',
    'HelpDialog',
    'OrganizeFilesDialog',
    'LyricsDownloadDialog',
    'TrackCoverDownloadDialog',
    'CoverDownloadDialog',
    'ArtistRenameDialog',
    'AlbumRenameDialog',
    'EditMediaInfoDialog',
]
