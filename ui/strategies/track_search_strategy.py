"""
Track cover search strategy.
"""
import logging
from typing import List, Optional

from services.metadata import CoverService
from services.lyrics.qqmusic_lyrics import get_qqmusic_cover_url
from infrastructure.network import HttpClient
from ui.strategies.cover_search_strategy import CoverSearchStrategy

logger = logging.getLogger(__name__)


class TrackSearchStrategy(CoverSearchStrategy):
    """Strategy for searching and saving track covers.

    Handles:
    - Multiple tracks with combo box navigation
    - search_covers() API with title/artist/album/duration
    - QQ Music lazy fetch with album_mid or song_mid
    - Save via track_repo.update() or custom callback
    """

    def __init__(self, tracks: List, track_repo, event_bus, save_callback=None):
        """Initialize track strategy.

        Args:
            tracks: List of Track objects
            track_repo: TrackRepository instance
            event_bus: EventBus instance
            save_callback: Optional custom save callback for cloud files
        """
        self._tracks = tracks
        self._track_repo = track_repo
        self._event_bus = event_bus
        self._save_callback = save_callback

    def get_items(self) -> list:
        """Return list of tracks."""
        return self._tracks

    def get_display_text(self, track) -> str:
        """Format track for combo box display."""
        text = track.title
        if track.artist:
            text += f" - {track.artist}"
        return text

    def search(self, cover_service: CoverService, track) -> List[dict]:
        """Search for track covers."""
        duration = getattr(track, 'duration', None)
        return cover_service.search_covers(
            track.title,
            track.artist,
            track.album,
            duration
        )

    def format_result(self, result: dict) -> str:
        """Format track search result for display."""
        title = result.get('title', '')
        artist = result.get('artist', '')
        album = result.get('album', '')
        source = result.get('source', '')
        score = result.get('score', 0)

        display = f"{title}"
        if artist:
            display += f" - {artist}"
        if album:
            display += f" ({album})"
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

    def save(self, track, cover_data: bytes, cover_path: str) -> bool:
        """Save track cover to database."""
        # Use custom save callback if provided (for cloud files)
        if self._save_callback:
            return self._save_callback(track, cover_path, cover_data)

        # Default: update track in database
        try:
            track.cover_path = cover_path
            self._track_repo.update(track)

            # Emit event
            self._event_bus.cover_updated.emit(track.id, False)
            return True
        except Exception as e:
            logger.error(f"Error saving track cover: {e}", exc_info=True)
            return False

    def get_search_info(self, track) -> dict:
        """Get track info for display."""
        info = {}
        if track.album:
            info['album'] = track.album
        if hasattr(track, 'duration') and track.duration:
            info['duration'] = track.duration
        return info
