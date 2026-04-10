"""
Theme manager for consistent styling across the application.

Provides configurable theme colors including background, text, highlight,
selection, and hover colors. Supports preset themes and custom colors.
Real-time theme switching via widget registration and refresh mechanism.
"""

import hashlib
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict
from weakref import WeakSet
from PySide6.QtCore import Signal, QObject
from PySide6.QtWidgets import QWidget, QApplication
from shiboken6 import isValid

logger = logging.getLogger(__name__)


@dataclass
class Theme:
    """Theme definition with color palette."""
    name: str
    display_name: str  # i18n key
    background: str  # Main background color
    background_alt: str  # Alternative background (lighter)
    background_hover: str  # Hover state background
    text: str  # Primary text color
    text_secondary: str  # Secondary text color (dimmer)
    highlight: str  # Accent/highlight color
    highlight_hover: str  # Accent hover state color
    selection: str  # Selection background color
    border: str  # Border/divider color

    def to_dict(self) -> Dict[str, str]:
        """Convert theme to dictionary."""
        return {
            'name': self.name,
            'display_name': self.display_name,
            'background': self.background,
            'background_alt': self.background_alt,
            'background_hover': self.background_hover,
            'text': self.text,
            'text_secondary': self.text_secondary,
            'highlight': self.highlight,
            'highlight_hover': self.highlight_hover,
            'selection': self.selection,
            'border': self.border,
        }


# Preset themes - all dark mode
PRESET_THEMES = {
    'dark': Theme(
        name='Dark',
        display_name='theme_dark',
        background='#121212',
        background_alt='#282828',
        background_hover='#2a2a2a',
        text='#ffffff',
        text_secondary='#b3b3b3',
        highlight='#1db954',  # Spotify green
        highlight_hover='#1ed760',
        selection='rgba(40, 40, 40, 0.8)',
        border='#3a3a3a'
    ),
    'gold': Theme(
        name='Gold',
        display_name='theme_gold',
        background='#1a1a1a',
        background_alt='#2a2a2a',
        background_hover='#3a3a3a',
        text='#ffffff',
        text_secondary='#cccccc',
        highlight='#FFD700',  # Gold
        highlight_hover='#FFE44D',
        selection='rgba(42, 42, 42, 0.8)',
        border='#4a4a4a'
    ),
    'ocean': Theme(
        name='Ocean',
        display_name='theme_ocean',
        background='#0d1b2a',
        background_alt='#1b2838',
        background_hover='#25374a',
        text='#e6f1ff',
        text_secondary='#8892b0',
        highlight='#00b4d8',  # Ocean blue
        highlight_hover='#48cae4',
        selection='rgba(27, 40, 56, 0.8)',
        border='#1b3a4b'
    ),
    'purple': Theme(
        name='Purple',
        display_name='theme_purple',
        background='#1a0a2e',
        background_alt='#2d1b4e',
        background_hover='#3d2b5e',
        text='#f0e6ff',
        text_secondary='#b39ddb',
        highlight='#9b59b6',  # Purple
        highlight_hover='#b370cf',
        selection='rgba(45, 27, 78, 0.8)',
        border='#4a2c6a'
    ),
    'sunset': Theme(
        name='Sunset',
        display_name='theme_sunset',
        background='#1a0a0a',
        background_alt='#2a1414',
        background_hover='#3a1e1e',
        text='#fff5f5',
        text_secondary='#d4a5a5',
        highlight='#e74c3c',  # Sunset red
        highlight_hover='#ff6b6b',
        selection='rgba(42, 20, 20, 0.8)',
        border='#4a2a2a'
    ),
    'light': Theme(
        name='Light',
        display_name='theme_light',
        background='#ffffff',
        background_alt='#f5f5f5',
        background_hover='#e8e8e8',
        text='#1a1a1a',
        text_secondary='#666666',
        highlight='#0066cc',  # Deep blue for better contrast on white
        highlight_hover='#0080ff',
        selection='rgba(232, 232, 232, 0.8)',
        border='#d0d0d0'
    ),
    'sepia': Theme(
        name='Sepia',
        display_name='theme_sepia',
        background='#f4ecd8',
        background_alt='#ebe3cf',
        background_hover='#ddd5c1',
        text='#3d3d3d',
        text_secondary='#666666',
        highlight='#8b4513',  # Saddle brown
        highlight_hover='#a0522d',
        selection='rgba(221, 213, 193, 0.8)',
        border='#c4b89e'
    ),
}


class ThemeManager(QObject):
    """Manage application theme and colors with real-time switching support."""

    _instance: Optional['ThemeManager'] = None
    _lock = threading.Lock()

    # Signal emitted when theme changes
    theme_changed = Signal(Theme)

    def __init__(self, config):
        """
        Initialize theme manager.

        Args:
            config: ConfigManager instance for persisting theme settings
        """
        super().__init__()
        self._config = config
        self._current_theme = self._load_theme()
        self._widgets: WeakSet[QWidget] = WeakSet()
        self._qss_cache: dict = {}
        self._global_qss_template: str | None = None
        logger.info(f"ThemeManager initialized with theme: {self._current_theme.name}")

    @classmethod
    def instance(cls, config=None) -> 'ThemeManager':
        """
        Get singleton instance.

        Args:
            config: ConfigManager required for first initialization

        Returns:
            ThemeManager singleton instance
        """
        with cls._lock:
            if cls._instance is None:
                if config is None:
                    raise ValueError("ConfigManager required for first initialization")
                cls._instance = cls(config)
            return cls._instance

    def _load_theme(self) -> Theme:
        """Load theme from config or return default."""
        from system.config import SettingKey
        theme_name = self._config.get(SettingKey.UI_THEME, 'dark')

        # Check if it's a preset theme
        if theme_name in PRESET_THEMES:
            return PRESET_THEMES[theme_name]

        # Check if it's a custom theme
        custom_theme_data = self._config.get(SettingKey.UI_THEME_CUSTOM)
        if custom_theme_data:
            try:
                return Theme(**custom_theme_data)
            except Exception as e:
                logger.error(f"Failed to load custom theme: {e}")

        # Fallback to dark theme
        return PRESET_THEMES['dark']

    @property
    def current_theme(self) -> Theme:
        """Get current theme."""
        return self._current_theme

    @property
    def highlight_color(self) -> str:
        """Get highlight color (for backward compatibility)."""
        return self._current_theme.highlight

    @property
    def hover_color(self) -> str:
        """Get hover color (for backward compatibility)."""
        return self._current_theme.highlight_hover

    def get_available_themes(self) -> Dict[str, str]:
        """Get list of available themes with display names."""
        return {key: theme.display_name for key, theme in PRESET_THEMES.items()}

    def set_theme(self, name: str):
        """
        Set theme by name (preset only).

        Args:
            name: Theme name ('dark', 'gold', 'ocean', 'purple', 'sunset')
        """
        if name not in PRESET_THEMES:
            logger.warning(f"Unknown theme: {name}, falling back to dark")
            name = 'dark'

        self._current_theme = PRESET_THEMES[name]
        self._qss_cache.clear()
        from system.config import SettingKey
        self._config.set(SettingKey.UI_THEME, name)
        self._config.delete(SettingKey.UI_THEME_CUSTOM)
        logger.info(f"Theme changed to preset: {name}")

        self._apply_and_broadcast()

    def set_custom_theme(self, theme: Theme):
        """
        Set custom theme.

        Args:
            theme: Custom Theme instance
        """
        self._current_theme = theme
        self._qss_cache.clear()
        from system.config import SettingKey
        self._config.set(SettingKey.UI_THEME, 'custom')
        self._config.set(SettingKey.UI_THEME_CUSTOM, theme.to_dict())
        logger.info(f"Custom theme set: {theme.name}")

        self._apply_and_broadcast()

    def _apply_and_broadcast(self):
        """Apply global stylesheet and notify all registered widgets."""
        self.apply_global_stylesheet()
        self.theme_changed.emit(self._current_theme)

        # Refresh all registered widgets
        for widget in list(self._widgets):
            if not self._is_widget_valid(widget):
                self._widgets.discard(widget)
                continue
            if hasattr(widget, 'refresh_theme'):
                try:
                    widget.refresh_theme()
                except Exception as e:
                    logger.error(f"Failed to refresh widget {widget.__class__.__name__}: {e}", exc_info=True)

    def register_widget(self, widget: QWidget):
        """
        Register a widget to receive theme change notifications.

        Args:
            widget: QWidget instance to register
        """
        self._widgets.add(widget)

    @staticmethod
    def _is_widget_valid(widget) -> bool:
        """Return False for Qt wrappers whose underlying C++ object is already gone."""
        try:
            return isValid(widget)
        except TypeError:
            # Test doubles and non-Qt objects should keep existing behavior.
            return True

    def get_qss(self, template: str) -> str:
        """
        Replace theme tokens in QSS template with current theme colors.

        Args:
            template: QSS string with %token% placeholders

        Returns:
            QSS string with tokens replaced by actual colors
        """
        theme = self._current_theme
        # Use stable digest of template + theme name as cache key.
        cache_key = (hashlib.sha256(template.encode("utf-8")).hexdigest(), theme.name)
        cached = self._qss_cache.get(cache_key)
        if cached is not None:
            return cached

        # Token replacement map
        tokens = {
            '%background%': theme.background,
            '%background_alt%': theme.background_alt,
            '%background_hover%': theme.background_hover,
            '%text%': theme.text,
            '%text_secondary%': theme.text_secondary,
            '%highlight%': theme.highlight,
            '%highlight_hover%': theme.highlight_hover,
            '%selection%': theme.selection,
            '%border%': theme.border,
        }

        result = template
        for token, color in tokens.items():
            result = result.replace(token, color)

        self._qss_cache[cache_key] = result
        return result

    @staticmethod
    def get_completer_popup_style() -> str:
        """Get themed QListView popup style for completers."""
        return """
            QListView {
                background-color: %background_alt%;
                border: 1px solid %border%;
                border-radius: 8px;
                color: %text%;
                selection-background-color: %highlight%;
                selection-color: %background%;
                outline: none;
            }
            QListView::item {
                padding: 8px 12px;
                border-bottom: 1px solid %border%;
            }
            QListView::item:selected {
                background-color: %highlight%;
                color: %background%;
            }
            QListView::item:hover {
                background-color: %border%;
            }
        """

    @staticmethod
    def get_popup_surface_style() -> str:
        """Get themed popup surface style for custom popup widgets."""
        return """
            QWidget[popupSurface="true"] {
                background-color: %background_alt%;
                border: 1px solid %border%;
                border-radius: 10px;
                color: %text%;
            }
        """

    def get_themed_completer_popup_style(self) -> str:
        """Return popup completer style with current theme tokens resolved."""
        return self.get_qss(self.get_completer_popup_style())

    def get_themed_popup_surface_style(self) -> str:
        """Return popup surface style with current theme tokens resolved."""
        return self.get_qss(self.get_popup_surface_style())

    def apply_global_stylesheet(self):
        """Load and apply themed global stylesheet to QApplication."""
        app = QApplication.instance()
        if not app:
            logger.warning("QApplication not found, cannot apply global stylesheet")
            return

        qss_path = Path(__file__).parent.parent / "ui" / "styles.qss"
        if qss_path.exists():
            try:
                # Cache the template to avoid re-reading from disk
                if self._global_qss_template is None:
                    self._global_qss_template = qss_path.read_text(encoding="utf-8")
                themed_qss = self.get_qss(self._global_qss_template)
                app.setStyleSheet(themed_qss)
                logger.info("Global stylesheet applied")
            except Exception as e:
                logger.error(f"Failed to apply global stylesheet: {e}")
        else:
            logger.warning(f"Global stylesheet not found: {qss_path}")
