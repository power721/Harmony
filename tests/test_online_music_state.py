"""
Test online music view state persistence.

This test verifies that the online music view state (search keyword,
current page type, and detail view) is properly saved and restored.
"""
import pytest
import tempfile
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infrastructure.database import DatabaseManager
from repositories.settings_repository import SqliteSettingsRepository
from system.config import ConfigManager, SettingKey


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield db_path
    os.unlink(db_path)


@pytest.fixture
def config_manager(temp_db):
    """Create a ConfigManager instance with temporary database."""
    db_manager = DatabaseManager(temp_db)
    settings_repo = SqliteSettingsRepository(db_manager=db_manager)
    return ConfigManager(settings_repo)


def test_online_music_keyword_persistence(config_manager):
    """Test saving and loading online music search keyword."""
    # Save keyword
    config_manager.set_online_music_keyword("周杰伦")

    # Load keyword
    keyword = config_manager.get_online_music_keyword()
    assert keyword == "周杰伦"

    # Test empty keyword
    config_manager.set_online_music_keyword("")
    assert config_manager.get_online_music_keyword() == ""

    # Test overwrite
    config_manager.set_online_music_keyword("Taylor Swift")
    assert config_manager.get_online_music_keyword() == "Taylor Swift"


def test_online_music_page_type_persistence(config_manager):
    """Test saving and loading online music page type."""
    # Test different page types
    page_types = ["top_list", "search", "detail"]

    for page_type in page_types:
        config_manager.set_online_music_page_type(page_type)
        assert config_manager.get_online_music_page_type() == page_type


def test_online_music_detail_type_persistence(config_manager):
    """Test saving and loading online music detail type."""
    detail_types = ["artist", "album", "playlist", ""]

    for detail_type in detail_types:
        config_manager.set_online_music_detail_type(detail_type)
        assert config_manager.get_online_music_detail_type() == detail_type


def test_online_music_detail_mid_persistence(config_manager):
    """Test saving and loading online music detail mid."""
    test_mids = [
        "001ABC123",
        "002XYZ789",
        "",
        "artist_mid_test_12345"
    ]

    for mid in test_mids:
        config_manager.set_online_music_detail_mid(mid)
        assert config_manager.get_online_music_detail_mid() == mid


def test_online_music_detail_data_persistence(config_manager):
    """Test saving and loading online music detail data."""
    # Test artist detail
    artist_data = {
        "detail_type": "artist",
        "mid": "001ABC123",
        "name": "周杰伦",
        "cover_url": "https://example.com/artist.jpg"
    }
    config_manager.set_online_music_detail_data(artist_data)
    loaded_data = config_manager.get_online_music_detail_data()
    assert loaded_data["detail_type"] == "artist"
    assert loaded_data["mid"] == "001ABC123"
    assert loaded_data["name"] == "周杰伦"

    # Test album detail
    album_data = {
        "detail_type": "album",
        "mid": "002XYZ789",
        "name": "范特西",
        "singer_name": "周杰伦",
        "cover_url": "https://example.com/album.jpg"
    }
    config_manager.set_online_music_detail_data(album_data)
    loaded_data = config_manager.get_online_music_detail_data()
    assert loaded_data["detail_type"] == "album"
    assert loaded_data["singer_name"] == "周杰伦"

    # Test playlist detail
    playlist_data = {
        "detail_type": "playlist",
        "mid": "003PLAY123",
        "name": "我的歌单",
        "creator": "用户A",
        "cover_url": "https://example.com/playlist.jpg"
    }
    config_manager.set_online_music_detail_data(playlist_data)
    loaded_data = config_manager.get_online_music_detail_data()
    assert loaded_data["detail_type"] == "playlist"
    assert loaded_data["creator"] == "用户A"


def test_complete_state_scenario(config_manager):
    """Test a complete scenario of saving and restoring state."""
    # Scenario 1: User searches for "周杰伦" and views an artist detail page
    config_manager.set_online_music_keyword("周杰伦")
    config_manager.set_online_music_page_type("detail")
    config_manager.set_online_music_detail_type("artist")
    config_manager.set_online_music_detail_mid("artist_mid_123")
    artist_state = {
        "detail_type": "artist",
        "mid": "artist_mid_123",
        "name": "周杰伦",
        "cover_url": "https://example.com/jay.jpg"
    }
    config_manager.set_online_music_detail_data(artist_state)

    # Verify state can be restored
    assert config_manager.get_online_music_keyword() == "周杰伦"
    assert config_manager.get_online_music_page_type() == "detail"
    assert config_manager.get_online_music_detail_type() == "artist"
    assert config_manager.get_online_music_detail_mid() == "artist_mid_123"
    loaded_state = config_manager.get_online_music_detail_data()
    assert loaded_state["name"] == "周杰伦"

    # Scenario 2: User searches for "Taylor Swift" and is on search results page
    config_manager.set_online_music_keyword("Taylor Swift")
    config_manager.set_online_music_page_type("search")

    # Verify state
    assert config_manager.get_online_music_keyword() == "Taylor Swift"
    assert config_manager.get_online_music_page_type() == "search"

    # Scenario 3: User is on top list page (default)
    config_manager.set_online_music_keyword("")
    config_manager.set_online_music_page_type("top_list")

    assert config_manager.get_online_music_keyword() == ""
    assert config_manager.get_online_music_page_type() == "top_list"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
