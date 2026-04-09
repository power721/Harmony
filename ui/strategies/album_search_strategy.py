"""
Album cover search strategy.
"""
import logging
from typing import List, Optional

from infrastructure.network import HttpClient
from services.metadata import CoverService
from system.plugins.online_cover_helpers import get_online_cover_url
from ui.strategies.cover_search_strategy import CoverSearchStrategy

logger = logging.getLogger(__name__)


class AlbumSearchStrategy(CoverSearchStrategy):
    """Strategy for searching and saving album covers.

    Handles:
    - Single album
    - search_covers() API with empty title
    - Provider lazy fetch with album_mid or song_mid
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

    def search_with_query(self, cover_service: CoverService, album, query: str) -> List[dict]:
        """Search album covers with an optional query override."""
        keyword = (query or "").strip()
        if not keyword:
            return self.search(cover_service, album)
        return cover_service.search_covers(
            title=keyword,
            artist=album.artist,
            album=keyword,
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
        """Check if result needs provider lazy fetch."""
        return (
                bool(result.get('source')) and
                not result.get('cover_url') and
                bool(result.get('album_mid') or result.get('id'))
        )

    def lazy_fetch(self, cover_service: CoverService, result: dict) -> bytes:
        """Fetch provider cover with lazy loading."""
        album_mid = result.get('album_mid')
        song_mid = result.get('id')  # Note: 'id' field contains song mid
        provider_id = result.get('source')

        # Get cover URL
        if not (album_mid or song_mid):
            raise ValueError("No album_mid or song_mid for lazy fetch")
        cover_url = get_online_cover_url(
            provider_id=provider_id,
            track_id=song_mid,
            album_id=album_mid,
            size=500,
        )
        if not cover_url:
            raise ValueError("No cover URL returned by provider")

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

    def get_default_search_term(self, album) -> str:
        return album.name or ""
