"""
Artist cover search strategy.
"""
import logging
from typing import List, Optional

from infrastructure.network import HttpClient
from services.lyrics.qqmusic_lyrics import get_qqmusic_artist_cover_url
from services.metadata import CoverService
from ui.strategies.cover_search_strategy import CoverSearchStrategy

logger = logging.getLogger(__name__)


class ArtistSearchStrategy(CoverSearchStrategy):
    """Strategy for searching and saving artist covers.

    Handles:
    - Single artist
    - search_artist_covers() API (QQ Music type=100)
    - Circular cover display
    - QQ Music lazy fetch with singer_mid
    - Save via library_service.update_artist_cover()
    """

    def __init__(self, artist, library_service, event_bus):
        """Initialize artist strategy.

        Args:
            artist: Artist object
            library_service: LibraryService instance
            event_bus: EventBus instance
        """
        self._artist = artist
        self._library_service = library_service
        self._event_bus = event_bus

    def get_items(self) -> list:
        """Return single-item list with artist."""
        return [self._artist]

    def get_display_text(self, artist) -> str:
        """Format artist for display."""
        return artist.name

    def search(self, cover_service: CoverService, artist) -> List[dict]:
        """Search for artist covers."""
        return cover_service.search_artist_covers(artist.name, limit=10)

    def search_with_query(self, cover_service: CoverService, artist, query: str) -> List[dict]:
        """Search artist covers with an optional query override."""
        keyword = (query or "").strip() or artist.name
        return cover_service.search_artist_covers(keyword, limit=10)

    def format_result(self, result: dict) -> str:
        """Format artist search result for display."""
        name = result.get('name', '')
        source = result.get('source', '')
        album_count = result.get('album_count', 0)
        score = result.get('score', 0)

        display = f"{name}"
        if album_count:
            display += f" ({album_count} albums)"
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
                bool(result.get('singer_mid'))
        )

    def lazy_fetch(self, cover_service: CoverService, result: dict) -> bytes:
        """Fetch QQ Music artist cover with lazy loading."""
        singer_mid = result.get('singer_mid')

        if not singer_mid:
            raise ValueError("No singer_mid for lazy fetch")

        # Get artist cover URL
        cover_url = get_qqmusic_artist_cover_url(singer_mid, size=500)

        # Download cover
        http_client = HttpClient()
        cover_data = http_client.get_content(cover_url, timeout=10)

        if not cover_data:
            raise ValueError(f"Failed to download cover from {cover_url}")

        return cover_data

    def save(self, artist, cover_data: bytes, cover_path: str) -> bool:
        """Save artist cover to database."""
        try:
            self._library_service.update_artist_cover(artist.name, cover_path)

            # Emit event
            self._event_bus.cover_updated.emit(artist.name, False)
            return True
        except Exception as e:
            logger.error(f"Error saving artist cover: {e}", exc_info=True)
            return False

    def use_circular_display(self) -> bool:
        """Artist covers display as circular."""
        return True

    def get_search_info(self, artist) -> dict:
        """Get artist info for display."""
        info = {}
        if hasattr(artist, 'album_count'):
            info['album_count'] = artist.album_count
        if hasattr(artist, 'song_count'):
            info['song_count'] = artist.song_count
        return info

    def get_default_search_term(self, artist) -> str:
        return artist.name or ""
