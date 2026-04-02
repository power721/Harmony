"""
Abstract strategy interface for cover search and save operations.
"""
from abc import ABC, abstractmethod
from typing import List, Optional

from services.metadata import CoverService


class CoverSearchStrategy(ABC):
    """Abstract strategy for searching and saving covers.

    Each strategy encapsulates the domain-specific logic for:
    - What items to search (Track list / Album / Artist)
    - How to display items in UI
    - How to search for covers
    - How to format results
    - How to handle QQ Music lazy fetch
    - How to save covers to database
    """

    @abstractmethod
    def get_items(self) -> list:
        """Return items to search.

        Returns:
            List of items (List[Track] / [Album] / [Artist])
        """
        pass

    @abstractmethod
    def get_display_text(self, item) -> str:
        """Format item for display in combo box or info label.

        Args:
            item: The item to display (Track / Album / Artist)

        Returns:
            Formatted string for display
        """
        pass

    @abstractmethod
    def search(self, cover_service: CoverService, item) -> List[dict]:
        """Execute search for item.

        Args:
            cover_service: CoverService instance
            item: The item to search for (Track / Album / Artist)

        Returns:
            List of search result dictionaries
        """
        pass

    def search_with_query(self, cover_service: CoverService, item, query: str) -> List[dict]:
        """Search using an optional user-provided query.

        Default behavior delegates to ``search`` to preserve backwards compatibility.
        """
        return self.search(cover_service, item)

    @abstractmethod
    def format_result(self, result: dict) -> str:
        """Format search result for display in results list.

        Args:
            result: Search result dictionary

        Returns:
            Formatted string for display
        """
        pass

    @abstractmethod
    def get_cover_url(self, result: dict) -> Optional[str]:
        """Extract cover URL from result.

        Args:
            result: Search result dictionary

        Returns:
            Cover URL or None if not available (needs lazy fetch)
        """
        pass

    @abstractmethod
    def needs_lazy_fetch(self, result: dict) -> bool:
        """Check if result needs lazy fetch (QQ Music).

        Args:
            result: Search result dictionary

        Returns:
            True if lazy fetch is needed
        """
        pass

    @abstractmethod
    def lazy_fetch(self, cover_service: CoverService, result: dict) -> bytes:
        """Fetch cover with lazy loading (QQ Music).

        Args:
            cover_service: CoverService instance
            result: Search result dictionary with album_mid/song_mid/singer_mid

        Returns:
            Cover data as bytes
        """
        pass

    @abstractmethod
    def save(self, item, cover_data: bytes, cover_path: str) -> bool:
        """Save cover to database.

        Args:
            item: The item to save cover for (Track / Album / Artist)
            cover_data: Cover image data
            cover_path: Path where cover is saved

        Returns:
            True if save was successful
        """
        pass

    def use_circular_display(self) -> bool:
        """Check if cover should display as circular (for artists).

        Returns:
            True for circular display, False for rectangular
        """
        return False

    def get_search_info(self, item) -> dict:
        """Get additional info to display for search (optional).

        Args:
            item: The item being searched

        Returns:
            Dictionary with info to display (e.g., duration, album count)
        """
        return {}

    def get_default_search_term(self, item) -> str:
        """Return default query text shown in the dialog's search input."""
        if hasattr(item, "title") and getattr(item, "title"):
            return item.title
        if hasattr(item, "name") and getattr(item, "name"):
            return item.name
        return ""
