"""
Test OnlineAlbumCard theming functionality.
"""

import pytest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication

from system.theme import ThemeManager, Theme
from ui.views.online_detail_view import OnlineAlbumCard


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton between tests."""
    ThemeManager._instance = None
    yield
    ThemeManager._instance = None


@pytest.fixture
def mock_config():
    """Mock config manager."""
    config = MagicMock()
    config.get.return_value = 'dark'
    return config


@pytest.fixture
def qt_app():
    """Create QApplication instance."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_online_album_card_has_theme_attributes(mock_config, qt_app):
    """Test that OnlineAlbumCard has required theme attributes."""
    tm = ThemeManager.instance(mock_config)

    test_data = {
        'mid': 'test123',
        'name': 'Test Album',
        'singer_mid': 'singer123',
        'singer_name': 'Test Artist',
        'cover_url': '',
        'song_count': 10,
        'publish_date': '2024'
    }

    card = OnlineAlbumCard(test_data)

    assert hasattr(card, '_style_normal'), 'Missing _style_normal attribute'
    assert hasattr(card, '_style_hover'), 'Missing _style_hover attribute'
    assert hasattr(card, '_cover_container'), 'Missing _cover_container widget'


def test_online_album_card_registered_with_theme_manager(mock_config, qt_app):
    """Test that OnlineAlbumCard is registered with theme manager."""
    tm = ThemeManager.instance(mock_config)

    test_data = {
        'mid': 'test123',
        'name': 'Test Album',
        'singer_mid': 'singer123',
        'singer_name': 'Test Artist',
        'cover_url': '',
        'song_count': 10,
        'publish_date': '2024'
    }

    card = OnlineAlbumCard(test_data)

    # Verify the card is registered with theme manager
    registered_widgets = tm._widgets
    assert card in registered_widgets, 'OnlineAlbumCard not registered with theme manager'


def test_online_album_card_theme_change(mock_config, qt_app):
    """Test that OnlineAlbumCard properly updates on theme change."""
    tm = ThemeManager.instance(mock_config)

    test_data = {
        'mid': 'test123',
        'name': 'Test Album',
        'singer_mid': 'singer123',
        'singer_name': 'Test Artist',
        'cover_url': '',
        'song_count': 10,
        'publish_date': '2024'
    }

    card = OnlineAlbumCard(test_data)

    # Test theme change
    old_style = card._style_normal
    tm.set_theme('light')
    new_style = card._style_normal
    assert old_style != new_style, 'Theme change did not update styles'


def test_online_album_card_hover_styles(mock_config, qt_app):
    """Test that OnlineAlbumCard has proper hover styles."""
    tm = ThemeManager.instance(mock_config)

    test_data = {
        'mid': 'test123',
        'name': 'Test Album',
        'singer_mid': 'singer123',
        'singer_name': 'Test Artist',
        'cover_url': '',
        'song_count': 10,
        'publish_date': '2024'
    }

    card = OnlineAlbumCard(test_data)

    # Test hover states
    assert 'border: 2px solid' in card._style_hover, 'Hover style missing border'
    assert 'border: 2px solid' not in card._style_normal, 'Normal style has border when it should not'


def test_online_album_card_refresh_theme(mock_config, qt_app):
    """Test that refresh_theme method works correctly."""
    tm = ThemeManager.instance(mock_config)

    test_data = {
        'mid': 'test123',
        'name': 'Test Album',
        'singer_mid': 'singer123',
        'singer_name': 'Test Artist',
        'cover_url': '',
        'song_count': 10,
        'publish_date': '2024'
    }

    card = OnlineAlbumCard(test_data)

    # Store old styles
    old_normal = card._style_normal
    old_hover = card._style_hover

    # Change theme
    tm.set_theme('gold')

    # Verify styles changed
    assert card._style_normal != old_normal, 'Normal style not updated after theme change'
    assert card._style_hover != old_hover, 'Hover style not updated after theme change'

    # Verify border radius is correct
    assert f'border-radius: {card.BORDER_RADIUS}px' in card._style_normal
    assert f'border-radius: {card.BORDER_RADIUS}px' in card._style_hover
