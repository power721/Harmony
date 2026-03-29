"""
Album cover search strategy.
"""
import logging
from typing import List, Optional

from services.metadata import CoverService
from services.lyrics.qqmusic_lyrics import get_qqmusic_cover_url
from infrastructure.network import HttpClient
from ui.strategies.cover_search_strategy import CoverSearchStrategy

logger = logging.getLogger(__name__)


class AlbumSearchStrategy(CoverSearchStrategy):
    """Strategy for searching and saving album covers.

    Handles:
    - Single album
    - search_covers() API with empty title
    - QQ Music lazy fetch with album_mid or song_mid
    - Save via library_service.update_album_cover()
    """

    def __init__(self, album, library_service, event_bus):
        """Initialize album strategy.

        Args:
            album: Album object
            library_service: LibraryService instance
            event_bus: EventBus instance
        """
        self._album = album
        self._library_service = library_service
        self._event_bus = event_bus

    def get_items(self) -> list:
        """Return single-item list with album."""
        return [self._album]

    def get_display_text(self, album) -> str:
        """Format album for display."""
        return f"{album.display_name} - {album.display_artist}"

    def search(self, cover_service: CoverService, album) -> List[dict]:
        """Search for album covers."""
        return cover_service.search_covers(
            title="",  # Empty title for album search
            artist=album.artist,
            album=album.name,
            duration=None
        )

    def format_result(self, result: dict) -> str:
        """Format album search result for display."""
        title = result.get('title', '')
        artist = result.get('artist', '')
        album = result.get('album', '')
        source = result.get('source', '')
        score = result.get('score', 0)

        display = f"{album or title}"
        if artist:
            display += f" - {artist}"
        display += f" [{source}] [{score:.0f}%]"
        return display

    def get_cover_url(self, result: dict) -> Optional[str]:
        """Extract cover URL from result."""
        return result.get('cover_url')

    def needs_lazy_fetch(self, result: dict) -> bool:
        """Check if result needs QQ Music lazy fetch."""
        return (
            result.get('source') == 'qqmusic' and
            not result.get('cover_url') and
            bool(result.get('album_mid') or result.get('id'))
        )

    def lazy_fetch(self, cover_service: CoverService, result: dict) -> bytes:
        """Fetch QQ Music cover with lazy loading."""
        album_mid = result.get('album_mid')
        song_mid = result.get('id')  # Note: 'id' field contains song mid

        # Get cover URL
        if album_mid:
            cover_url = get_qqmusic_cover_url(album_mid=album_mid, size=500)
        elif song_mid:
            cover_url = get_qqmusic_cover_url(mid=song_mid, size=500)
        else:
            raise ValueError("No album_mid or song_mid for lazy fetch")

        # Download cover
        http_client = HttpClient()
        cover_data = http_client.get_content(cover_url, timeout=10)

        if not cover_data:
            raise ValueError(f"Failed to download cover from {cover_url}")

        return cover_data

    def save(self, album, cover_data: bytes, cover_path: str) -> bool:
        """Save album cover to database."""
        try:
            self._library_service.update_album_cover(
                album.name, album.artist, cover_path
            )

            # Emit event
            self._event_bus.cover_updated.emit(
                f"{album.name}:{album.artist}", False
            )
            return True
        except Exception as e:
            logger.error(f"Error saving album cover: {e}", exc_info=True)
            return False
