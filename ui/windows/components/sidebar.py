"""
Sidebar navigation widget for MainWindow.
"""

from typing import List, Tuple, TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel

from system.i18n import t, get_language
from ui.icons import IconName, IconButton, PathIconButton

if TYPE_CHECKING:
    from system.config import ConfigManager


class Sidebar(QWidget):
    """
    Sidebar navigation widget with buttons for different views.

    Signals:
        page_requested: Emitted when a navigation button is clicked (page_index)
        language_toggled: Emitted when language button is clicked
        settings_requested: Emitted when settings button is clicked
        add_music_requested: Emitted when add music button is clicked
    """

    # Signals
    page_requested = Signal(int)  # page index
    language_toggled = Signal()
    settings_requested = Signal()
    add_music_requested = Signal()

    # Page indices - must match stacked widget order in MainWindow
    # Stacked widget order:
    # 0: library_view, 1: cloud_drive_view, 2: playlist_view, 3: queue_view
    # 4: albums_view, 5: artists_view, 6: artist_view, 7: album_view
    # 8: genres_view, 9: genre_view
    PAGE_LIBRARY = 0
    PAGE_CLOUD = 1
    PAGE_PLAYLISTS = 2
    PAGE_QUEUE = 3
    PAGE_ALBUMS = 4
    PAGE_ARTISTS = 5
    PAGE_GENRES = 8
    # Special pages (not in stacked widget, handled specially)
    PAGE_FAVORITES = 100
    PAGE_HISTORY = 101
    PAGE_MOST_PLAYED = 102
    PAGE_RECENTLY_ADDED = 103

    _NAV_STYLE = """
        QPushButton {
            text-align: left;
            padding: 12px 18px;
            border-radius: 10px;
            background: transparent;
            color: %text_secondary%;
            border: 2px solid transparent;
            font-size: 14px;
            font-weight: 500;
        }
        QPushButton:hover {
            background: %background_hover%;
            color: %highlight%;
            border: 2px solid %border%;
        }
        QPushButton:checked {
            background: %highlight%;
            color: %background%;
            border: 2px solid %highlight%;
            font-weight: bold;
        }
    """

    _ACTION_BTN_STYLE = """
        QPushButton#{btn_id} {
            background-color: %background_hover%;
            color: %text_secondary%;
            border: 2px solid %border%;
            border-radius: 16px;
            padding: 6px 16px;
            font-size: 13px;
            font-weight: 500;
        }
        QPushButton#{btn_id}:hover {
            background-color: %border%;
            border: 2px solid %highlight%;
            color: %highlight%;
        }
    """

    def __init__(self, config_manager: "ConfigManager" = None, parent=None):
        """
        Initialize the sidebar.

        Args:
            config_manager: Configuration manager for settings status
            parent: Parent widget
        """
        super().__init__(parent)
        self._config = config_manager
        self._nav_buttons = []
        self._setup_ui()

        from system.theme import ThemeManager
        ThemeManager.instance().register_widget(self)

    def _setup_ui(self):
        """Setup the sidebar UI."""
        self.setObjectName("sidebar")
        self.setMinimumWidth(180)
        self.setMaximumWidth(220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 20, 10, 10)
        layout.setSpacing(5)

        # Logo
        logo_label = QLabel("Harmony")
        logo_label.setObjectName("logo")
        logo_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo_label)

        layout.addSpacing(20)

        # Navigation buttons
        nav_items: List[Tuple[int, IconName, str]] = [
            (self.PAGE_LIBRARY, IconName.MUSIC, t("library")),
            (self.PAGE_ALBUMS, IconName.COMPACT_DISC, t("albums")),
            (self.PAGE_ARTISTS, IconName.MICROPHONE, t("artists")),
            (self.PAGE_GENRES, IconName.COMPACT_DISC, t("genres")),
            (self.PAGE_CLOUD, IconName.CLOUD, t("cloud_drive")),
            (self.PAGE_PLAYLISTS, IconName.LIST, t("playlists")),
            (self.PAGE_QUEUE, IconName.QUEUE, t("queue")),
            (self.PAGE_FAVORITES, IconName.STAR, t("favorites")),
            (self.PAGE_HISTORY, IconName.CLOCK, t("history")),
            (self.PAGE_MOST_PLAYED, IconName.STAR, t("most_played")),
            (self.PAGE_RECENTLY_ADDED, IconName.CLOCK, t("recently_added")),
        ]

        self._nav_button_map = {}
        for page_index, icon_name, text in nav_items:
            btn = IconButton(icon_name, text, size=18)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, idx=page_index: self._on_nav_clicked(idx))
            layout.addWidget(btn)
            self._nav_buttons.append((page_index, btn))
            self._nav_button_map[page_index] = btn

        # Default to library
        self._nav_buttons[0][1].setChecked(True)
        self.refresh_optional_view_visibility()

        layout.addStretch()

        # Language button
        lang_text = "EN" if get_language() == "en" else "中文"
        self._language_btn = IconButton(IconName.GLOBE, lang_text, size=16)
        self._language_btn.setObjectName("languageBtn")
        self._language_btn.setCursor(Qt.PointingHandCursor)
        self._language_btn.setFixedHeight(32)
        self._language_btn.clicked.connect(self.language_toggled)
        layout.addWidget(self._language_btn)

        # Settings button
        settings_status = "✅" if self._config and self._config.get_ai_enabled() else "⚙️"
        self._settings_btn = QPushButton(f"⚙️ {t('settings')} {settings_status}")
        self._settings_btn.setObjectName("settingsBtn")
        self._settings_btn.setCursor(Qt.PointingHandCursor)
        self._settings_btn.setFixedHeight(32)
        self._settings_btn.clicked.connect(self.settings_requested)
        layout.addWidget(self._settings_btn)

        # Add music button
        self._add_music_btn = QPushButton(t("add_music"))
        self._add_music_btn.setObjectName("addMusicBtn")
        self._add_music_btn.setCursor(Qt.PointingHandCursor)
        self._add_music_btn.clicked.connect(self.add_music_requested)
        layout.addWidget(self._add_music_btn)

        # Apply initial theme
        self.refresh_theme()

    def refresh_theme(self):
        """Refresh all widget styles with current theme tokens."""
        from system.theme import ThemeManager
        tm = ThemeManager.instance()

        nav_style = tm.get_qss(self._NAV_STYLE)
        for _, btn in self._nav_buttons:
            btn.setStyleSheet(nav_style)
            if hasattr(btn, 'refresh_theme'):
                btn.refresh_theme()

        language_style = tm.get_qss(self._ACTION_BTN_STYLE).replace("{btn_id}", "languageBtn")
        self._language_btn.setStyleSheet(language_style)

        settings_style = tm.get_qss(self._ACTION_BTN_STYLE).replace("{btn_id}", "settingsBtn")
        self._settings_btn.setStyleSheet(settings_style)

    def add_plugin_entry(
        self,
        page_index: int,
        title: str,
        icon_name: str | None = None,
        icon_path: str | None = None,
        title_provider=None,
    ) -> None:
        """Add a plugin-provided navigation button before the footer actions."""
        from system.theme import ThemeManager

        if icon_path:
            btn = PathIconButton(icon_path, title, size=18)
        else:
            resolved_icon = getattr(IconName, icon_name, IconName.GLOBE) if icon_name else IconName.GLOBE
            btn = IconButton(resolved_icon, title, size=18)
        btn.setCheckable(True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setProperty("plugin_title_provider", title_provider)
        btn.setProperty("plugin_icon_path", icon_path)
        btn.clicked.connect(lambda checked, idx=page_index: self._on_nav_clicked(idx))
        btn.setStyleSheet(ThemeManager.instance().get_qss(self._NAV_STYLE))
        insert_index = max(self.layout().count() - 4, 0)
        self.layout().insertWidget(insert_index, btn)
        self._nav_buttons.append((page_index, btn))

    def _on_nav_clicked(self, page_index: int):
        """Handle navigation button click."""
        # Uncheck other buttons
        for idx, btn in self._nav_buttons:
            if idx != page_index:
                btn.setChecked(False)

        # Emit signal
        self.page_requested.emit(page_index)

    def set_current_page(self, page_index: int):
        """
        Set the current active page.

        Args:
            page_index: Page index to activate
        """
        for idx, btn in self._nav_buttons:
            btn.setChecked(idx == page_index)

    def update_settings_status(self, ai_enabled: bool):
        """
        Update the settings button status indicator.

        Args:
            ai_enabled: Whether AI features are enabled
        """
        settings_status = "✅" if ai_enabled else "⚙️"
        self._settings_btn.setText(f"⚙️ {t('settings')} {settings_status}")

    def update_language_button(self):
        """Update the language button text."""
        lang_text = "EN" if get_language() == "en" else "中文"
        self._language_btn.setText(lang_text)

    def refresh_optional_view_visibility(self):
        """Apply config-driven visibility for optional navigation entries."""
        visible_pages = {
            self.PAGE_ALBUMS: self._config.get_albums_visible() if self._config else True,
            self.PAGE_ARTISTS: self._config.get_artists_visible() if self._config else True,
            self.PAGE_GENRES: self._config.get_genres_visible() if self._config else False,
            self.PAGE_CLOUD: self._config.get_cloud_drive_visible() if self._config else True,
            self.PAGE_FAVORITES: self._config.get_favorites_visible() if self._config else True,
            self.PAGE_HISTORY: self._config.get_history_visible() if self._config else True,
            self.PAGE_MOST_PLAYED: self._config.get_most_played_visible() if self._config else False,
            self.PAGE_RECENTLY_ADDED: self._config.get_recently_added_visible() if self._config else False,
        }
        for page_index, visible in visible_pages.items():
            button = self._nav_button_map.get(page_index)
            if button is not None:
                button.setHidden(not visible)

    def refresh_texts(self):
        """Refresh all button texts with current language."""
        nav_texts = {
            self.PAGE_LIBRARY: t("library"),
            self.PAGE_ALBUMS: t("albums"),
            self.PAGE_ARTISTS: t("artists"),
            self.PAGE_GENRES: t("genres"),
            self.PAGE_CLOUD: t("cloud_drive"),
            self.PAGE_PLAYLISTS: t("playlists"),
            self.PAGE_QUEUE: t("queue"),
            self.PAGE_FAVORITES: t("favorites"),
            self.PAGE_HISTORY: t("history"),
            self.PAGE_MOST_PLAYED: t("most_played"),
            self.PAGE_RECENTLY_ADDED: t("recently_added"),
        }

        for idx, btn in self._nav_buttons:
            if idx in nav_texts:
                btn.setText(nav_texts[idx])
            else:
                title_provider = btn.property("plugin_title_provider")
                if callable(title_provider):
                    btn.setText(title_provider())

        self._add_music_btn.setText(t("add_music"))
        self.update_language_button()
        self.update_settings_status(
            self._config.get_ai_enabled() if self._config else False
        )
        self.refresh_optional_view_visibility()
