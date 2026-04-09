"""
Genre cover search strategy.
"""
import logging
from typing import List, Optional

from services.metadata import CoverService
from ui.strategies.cover_search_strategy import CoverSearchStrategy

logger = logging.getLogger(__name__)


class GenreSearchStrategy(CoverSearchStrategy):
    """Strategy for searching and saving genre covers."""

    def __init__(self, genre, library_service, event_bus):
        self._genre = genre
        self._library_service = library_service
        self._event_bus = event_bus

    def get_items(self) -> list:
        return [self._genre]

    def get_display_text(self, genre) -> str:
        return genre.display_name

    def search(self, cover_service: CoverService, genre) -> List[dict]:
        return cover_service.search_covers(
            title=genre.name,
            artist="",
            album=genre.name,
            duration=None
        )

    def search_with_query(self, cover_service: CoverService, genre, query: str) -> List[dict]:
        keyword = (query or "").strip() or genre.name
        return cover_service.search_covers(
            title=keyword,
            artist="",
            album=keyword,
            duration=None
        )

    def format_result(self, result: dict) -> str:
        title = result.get("title", "")
        artist = result.get("artist", "")
        album = result.get("album", "")
        source = result.get("source", "")
        score = result.get("score", 0)

        display = f"{album or title}"
        if artist:
            display += f" - {artist}"
        display += f" [{source}] [{score:.0f}%]"
        return display

    def get_cover_url(self, result: dict) -> Optional[str]:
        return result.get("cover_url")

    def needs_lazy_fetch(self, result: dict) -> bool:
        return (
            bool(result.get("source"))
            and not result.get("cover_url")
            and bool(result.get("album_mid") or result.get("id"))
        )

    def lazy_fetch(self, cover_service: CoverService, result: dict) -> bytes:
        # Reuse provider lazy fetch path from existing behavior by importing helper here.
        from infrastructure.network import HttpClient
        from system.plugins.online_cover_helpers import get_online_cover_url

        album_mid = result.get("album_mid")
        song_mid = result.get("id")
        provider_id = result.get("source")
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

        http_client = HttpClient()
        cover_data = http_client.get_content(cover_url, timeout=10)
        if not cover_data:
            raise ValueError(f"Failed to download cover from {cover_url}")
        return cover_data

    def save(self, genre, cover_data: bytes, cover_path: str) -> bool:
        try:
            ok = self._library_service.update_genre_cover(genre.name, cover_path)
            if not ok:
                return False
            self._event_bus.cover_updated.emit(genre.name, False)
            return True
        except Exception as e:
            logger.error(f"Error saving genre cover: {e}", exc_info=True)
            return False

    def get_search_info(self, genre) -> dict:
        return {"title": genre.name}

    def get_default_search_term(self, genre) -> str:
        return genre.name or ""
