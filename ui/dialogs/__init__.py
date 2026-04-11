"""
UI dialogs for Harmony music player.
"""
from .album_rename_dialog import AlbumRenameDialog
from .artist_rename_dialog import ArtistRenameDialog
from .base_cover_download_dialog import BaseCoverDownloadDialog
from .cloud_login_dialog import CloudLoginDialog
from .cover_preview_dialog import CoverPreviewDialog, show_cover_preview
from .edit_media_info_dialog import EditMediaInfoDialog
from .help_dialog import HelpDialog
from .input_dialog import InputDialog
from .lyrics_download_dialog import LyricsDownloadDialog
from .organize_files_dialog import OrganizeFilesDialog
from .provider_select_dialog import ProviderSelectDialog
from .settings_dialog import GeneralSettingsDialog
from .universal_cover_download_dialog import UniversalCoverDownloadDialog
from .welcome_dialog import WelcomeDialog

# Backward compatibility aliases
TrackCoverDownloadDialog = UniversalCoverDownloadDialog
AlbumCoverDownloadDialog = UniversalCoverDownloadDialog
ArtistCoverDownloadDialog = UniversalCoverDownloadDialog

__all__ = [
    'GeneralSettingsDialog',
    'AlbumCoverDownloadDialog',
    'ArtistCoverDownloadDialog',
    'BaseCoverDownloadDialog',
    'CloudLoginDialog',
    'CoverPreviewDialog',
    'ProviderSelectDialog',
    'HelpDialog',
    'OrganizeFilesDialog',
    'LyricsDownloadDialog',
    'TrackCoverDownloadDialog',
    'UniversalCoverDownloadDialog',
    'ArtistRenameDialog',
    'AlbumRenameDialog',
    'EditMediaInfoDialog',
    'InputDialog',
    'WelcomeDialog',
    'show_cover_preview',
]
