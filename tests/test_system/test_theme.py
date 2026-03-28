"""Tests for the theme system."""
import pytest
from unittest.mock import MagicMock, patch
from dataclasses import asdict

from system.theme import Theme, ThemeManager, PRESET_THEMES


class TestTheme:
    """Tests for Theme dataclass."""

    def test_theme_creation(self):
        theme = Theme(
            name='Test',
            display_name='theme_test',
            background='#111111',
            background_alt='#222222',
            background_hover='#333333',
            text='#ffffff',
            text_secondary='#aaaaaa',
            highlight='#1db954',
            highlight_hover='#1ed760',
            selection='rgba(40, 40, 40, 0.8)',
            border='#3a3a3a',
        )
        assert theme.name == 'Test'
        assert theme.background == '#111111'
        assert theme.highlight == '#1db954'

    def test_theme_to_dict(self):
        theme = Theme(
            name='Test',
            display_name='theme_test',
            background='#111111',
            background_alt='#222222',
            background_hover='#333333',
            text='#ffffff',
            text_secondary='#aaaaaa',
            highlight='#1db954',
            highlight_hover='#1ed760',
            selection='rgba(40, 40, 40, 0.8)',
            border='#3a3a3a',
        )
        d = theme.to_dict()
        assert d['name'] == 'Test'
        assert d['background'] == '#111111'
        assert d['highlight'] == '#1db954'
        assert len(d) == 11  # name + display_name + 9 colors


class TestPresetThemes:
    """Tests for preset themes."""

    def test_all_presets_have_7_themes(self):
        assert len(PRESET_THEMES) == 7

    def test_preset_names(self):
        expected = {'dark', 'gold', 'ocean', 'purple', 'sunset', 'light', 'sepia'}
        assert set(PRESET_THEMES.keys()) == expected

    def test_all_presets_have_complete_colors(self):
        for name, theme in PRESET_THEMES.items():
            assert theme.name, f"Theme {name} missing name"
            assert theme.display_name, f"Theme {name} missing display_name"
            assert theme.background, f"Theme {name} missing background"
            assert theme.background_alt, f"Theme {name} missing background_alt"
            assert theme.background_hover, f"Theme {name} missing background_hover"
            assert theme.text, f"Theme {name} missing text"
            assert theme.text_secondary, f"Theme {name} missing text_secondary"
            assert theme.highlight, f"Theme {name} missing highlight"
            assert theme.highlight_hover, f"Theme {name} missing highlight_hover"
            assert theme.selection, f"Theme {name} missing selection"
            assert theme.border, f"Theme {name} missing border"


class TestThemeManager:
    """Tests for ThemeManager."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton between tests."""
        ThemeManager._instance = None
        yield
        ThemeManager._instance = None

    @pytest.fixture
    def mock_config(self):
        config = MagicMock()
        config.get.return_value = 'dark'
        return config

    def test_singleton_requires_config(self):
        with pytest.raises(ValueError, match="ConfigManager required"):
            ThemeManager.instance()

    def test_singleton_initialization(self, mock_config):
        tm = ThemeManager.instance(mock_config)
        assert ThemeManager.instance() is tm

    def test_default_theme_is_dark(self, mock_config):
        mock_config.get.return_value = 'dark'
        tm = ThemeManager.instance(mock_config)
        assert tm.current_theme.name == 'Dark'

    def test_set_preset_theme(self, mock_config):
        tm = ThemeManager.instance(mock_config)
        tm.set_theme('gold')
        assert tm.current_theme.name == 'Gold'
        mock_config.set.assert_called_with('ui.theme', 'gold')

    def test_set_unknown_theme_falls_back(self, mock_config):
        tm = ThemeManager.instance(mock_config)
        tm.set_theme('nonexistent')
        assert tm.current_theme.name == 'Dark'

    def test_set_custom_theme(self, mock_config):
        tm = ThemeManager.instance(mock_config)
        custom = Theme(
            name='MyCustom',
            display_name='custom',
            background='#000000',
            background_alt='#111111',
            background_hover='#222222',
            text='#ffffff',
            text_secondary='#aaaaaa',
            highlight='#ff0000',
            highlight_hover='#ff4444',
            selection='rgba(0,0,0,0.8)',
            border='#333333',
        )
        tm.set_custom_theme(custom)
        assert tm.current_theme.name == 'MyCustom'
        assert tm.current_theme.highlight == '#ff0000'

    def test_get_qss_token_replacement(self, mock_config):
        tm = ThemeManager.instance(mock_config)
        template = """
        QMainWindow {
            background: %background%;
            color: %text%;
        }
        QPushButton {
            color: %highlight%;
        }
        """
        result = tm.get_qss(template)
        assert '#121212' in result
        assert '#ffffff' in result
        assert '#1db954' in result
        assert '%background%' not in result
        assert '%text%' not in result
        assert '%highlight%' not in result

    def test_get_qss_with_gold_theme(self, mock_config):
        tm = ThemeManager.instance(mock_config)
        tm.set_theme('gold')
        template = "color: %highlight%;"
        result = tm.get_qss(template)
        assert '#FFD700' in result

    def test_highlight_color_property(self, mock_config):
        tm = ThemeManager.instance(mock_config)
        assert tm.highlight_color == '#1db954'

    def test_hover_color_property(self, mock_config):
        tm = ThemeManager.instance(mock_config)
        assert tm.hover_color == '#1ed760'

    def test_get_available_themes(self, mock_config):
        tm = ThemeManager.instance(mock_config)
        themes = tm.get_available_themes()
        assert 'dark' in themes
        assert 'gold' in themes
        assert 'light' in themes
        assert 'sepia' in themes
        assert len(themes) == 7

    def test_load_custom_theme_from_config(self):
        config = MagicMock()
        config.get.side_effect = lambda key, default=None: {
            'ui.theme': 'custom',
            'ui.theme.custom': {
                'name': 'Loaded',
                'display_name': 'custom',
                'background': '#000000',
                'background_alt': '#111111',
                'background_hover': '#222222',
                'text': '#ffffff',
                'text_secondary': '#aaaaaa',
                'highlight': '#ff0000',
                'highlight_hover': '#ff4444',
                'selection': 'rgba(0,0,0,0.8)',
                'border': '#333333',
            },
        }.get(key, default)

        tm = ThemeManager.instance(config)
        assert tm.current_theme.name == 'Loaded'
        assert tm.current_theme.highlight == '#ff0000'

    def test_load_invalid_custom_falls_back(self):
        config = MagicMock()
        config.get.side_effect = lambda key, default=None: {
            'ui.theme': 'custom',
            'ui.theme.custom': {'invalid': 'data'},
        }.get(key, default)

        tm = ThemeManager.instance(config)
        assert tm.current_theme.name == 'Dark'

    def test_set_custom_theme_persists(self, mock_config):
        tm = ThemeManager.instance(mock_config)
        custom = Theme(
            name='Custom',
            display_name='custom',
            background='#000000',
            background_alt='#111111',
            background_hover='#222222',
            text='#ffffff',
            text_secondary='#aaaaaa',
            highlight='#ff0000',
            highlight_hover='#ff4444',
            selection='rgba(0,0,0,0.8)',
            border='#333333',
        )
        tm.set_custom_theme(custom)
        # Check config.set was called with 'custom' and the dict
        calls = mock_config.set.call_args_list
        assert any(c[0][0] == 'ui.theme' and c[0][1] == 'custom' for c in calls)
        assert any(c[0][0] == 'ui.theme.custom' for c in calls)
