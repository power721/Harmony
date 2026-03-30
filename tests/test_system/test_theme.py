"""Tests for the theme system."""
import pytest
from unittest.mock import MagicMock, patch, call
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

    def test_register_widget(self, mock_config):
        """Test registering a widget to receive theme updates."""
        tm = ThemeManager.instance(mock_config)
        mock_widget = MagicMock()

        tm.register_widget(mock_widget)

        assert mock_widget in tm._widgets

    def test_register_multiple_widgets(self, mock_config):
        """Test registering multiple widgets."""
        tm = ThemeManager.instance(mock_config)
        widget1 = MagicMock()
        widget2 = MagicMock()

        tm.register_widget(widget1)
        tm.register_widget(widget2)

        assert widget1 in tm._widgets
        assert widget2 in tm._widgets

    def test_register_widget_refresh_on_theme_change(self, mock_config):
        """Test registered widgets get refreshed when theme changes."""
        tm = ThemeManager.instance(mock_config)
        mock_widget = MagicMock()
        mock_widget.refresh_theme = MagicMock()

        tm.register_widget(mock_widget)
        tm.set_theme('gold')

        mock_widget.refresh_theme.assert_called_once()

    def test_register_widget_no_refresh_theme_method(self, mock_config):
        """Test widget without refresh_theme is safely skipped."""
        tm = ThemeManager.instance(mock_config)
        mock_widget = MagicMock()
        # Remove refresh_theme attribute
        del mock_widget.refresh_theme

        tm.register_widget(mock_widget)
        # Should not raise
        tm.set_theme('ocean')

    def test_register_widget_refresh_theme_raises(self, mock_config):
        """Test widget whose refresh_theme raises is safely handled."""
        tm = ThemeManager.instance(mock_config)
        mock_widget = MagicMock()
        mock_widget.refresh_theme.side_effect = RuntimeError("broken")

        tm.register_widget(mock_widget)
        # Should not raise
        tm.set_theme('purple')

        mock_widget.refresh_theme.assert_called_once()

    def test_apply_and_broadcast_emits_signal(self, mock_config):
        """Test _apply_and_broadcast emits theme_changed signal."""
        tm = ThemeManager.instance(mock_config)
        signal_received = []

        tm.theme_changed.connect(lambda theme: signal_received.append(theme))
        tm.set_theme('gold')

        assert len(signal_received) == 1
        assert signal_received[0].name == 'Gold'

    def test_apply_and_broadcast_with_registered_widgets(self, mock_config):
        """Test _apply_and_broadcast applies stylesheet and refreshes widgets."""
        tm = ThemeManager.instance(mock_config)
        widget1 = MagicMock()
        widget1.refresh_theme = MagicMock()
        widget2 = MagicMock()
        widget2.refresh_theme = MagicMock()

        tm.register_widget(widget1)
        tm.register_widget(widget2)

        signal_received = []
        tm.theme_changed.connect(lambda theme: signal_received.append(theme))
        tm.set_theme('ocean')

        # Signal was emitted
        assert len(signal_received) == 1
        assert signal_received[0].name == 'Ocean'
        # Both widgets refreshed
        widget1.refresh_theme.assert_called_once()
        widget2.refresh_theme.assert_called_once()

    @patch('system.theme.QApplication')
    def test_apply_global_stylesheet_no_qapp(self, mock_qapp):
        """Test apply_global_stylesheet logs warning when no QApplication."""
        mock_qapp.instance.return_value = None

        config = MagicMock()
        config.get.return_value = 'dark'
        tm = ThemeManager.instance(config)

        # Should not raise, just warn
        tm.apply_global_stylesheet()

    @patch('system.theme.QApplication')
    @patch('system.theme.Path')
    def test_apply_global_stylesheet_missing_file(self, mock_path_cls, mock_qapp):
        """Test apply_global_stylesheet when QSS file doesn't exist."""
        mock_qapp.instance.return_value = MagicMock()
        mock_qss_path = MagicMock()
        mock_qss_path.exists.return_value = False
        mock_path_cls.return_value.parent.parent.__truediv__ = MagicMock(return_value=mock_qss_path)

        config = MagicMock()
        config.get.return_value = 'dark'
        tm = ThemeManager.instance(config)

        # Should not raise
        tm.apply_global_stylesheet()

    @patch('system.theme.QApplication')
    @patch('builtins.open', new_callable=MagicMock, side_effect=OSError("permission denied"))
    def test_apply_global_stylesheet_read_error(self, mock_open, mock_qapp):
        """Test apply_global_stylesheet handles file read error."""
        mock_app = MagicMock()
        mock_qapp.instance.return_value = mock_app

        config = MagicMock()
        config.get.return_value = 'dark'
        tm = ThemeManager.instance(config)

        # Should not raise
        tm.apply_global_stylesheet()
