"""General Settings Dialog for configuring host and plugin settings."""
import logging
import os
from importlib import util as importlib_util
from typing import cast

from app.bootstrap import Bootstrap
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainterPath, QRegion
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QGroupBox, QTabWidget,
    QWidget, QComboBox, QColorDialog,
    QGridLayout, QFrame, QGraphicsDropShadowEffect
)

from infrastructure.audio import PlayerEngine
from system.i18n import t
from system.theme import ThemeManager
from ui.dialogs.draggable_dialog_mixin import DraggableDialogMixin
from ui.dialogs.dialog_title_bar import setup_equalizer_title_layout
from ui.dialogs.message_dialog import MessageDialog, Yes, No
from ui.dialogs.plugin_management_tab import PluginManagementTab
from ui.dialogs.progress_dialog import ProgressDialog

# Configure logging
logger = logging.getLogger(__name__)


def _get_audio_engine_options() -> list[tuple[str, str]]:
    """Return supported audio engine options for the current runtime."""
    options = []
    if PlayerEngine.is_backend_available(PlayerEngine.BACKEND_MPV):
        options.append((t("audio_engine_mpv"), PlayerEngine.BACKEND_MPV))
    if PlayerEngine.is_backend_available(PlayerEngine.BACKEND_QT):
        options.append((t("audio_engine_qt"), PlayerEngine.BACKEND_QT))
    return options


class GeneralSettingsDialog(DraggableDialogMixin, QDialog):
    """Dialog for configuring host and plugin settings."""

    def __init__(self, config_manager, parent=None):
        """
        Initialize the AI settings dialog.

        Args:
            config_manager: ConfigManager instance for saving settings
            parent: Parent widget
        """
        super().__init__(parent)
        self._config = config_manager
        self._batch_worker = None
        self._drag_pos = None
        self._plugin_settings_tabs = []

        # Make dialog frameless
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setProperty("shell", True)

        self._setup_shadow()
        self._setup_ui()
        self._load_settings()
        ThemeManager.instance().register_widget(self)

    def _setup_shadow(self):
        """Setup drop shadow effect."""
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

    def _setup_ui(self):
        """Setup the dialog UI."""
        self.setWindowTitle(t("settings"))
        self.setMinimumWidth(550)
        theme = ThemeManager.instance().current_theme

        # Outer layout with 0 margins — container fills the dialog
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Container widget for rounded corners
        container = QWidget()
        container.setObjectName("settingsContainer")
        outer.addWidget(container)

        # Content layout
        container_layout = QVBoxLayout(container)
        layout, self._title_bar_controller = setup_equalizer_title_layout(
            self,
            container_layout,
            t("settings"),
            content_spacing=15,
        )

        # Tab widget for AI and AcoustID settings
        tab_widget = QTabWidget()
        tab_widget.tabBar().setCursor(Qt.CursorShape.PointingHandCursor)

        # AI Settings Tab
        ai_tab = QWidget()
        ai_layout = QVBoxLayout(ai_tab)
        ai_layout.setSpacing(10)

        # Enable AI checkbox
        self._enable_checkbox = QCheckBox(t("ai_enable"))
        self._enable_checkbox.setStyleSheet("font-weight: bold; font-size: 14px;")
        self._enable_checkbox.stateChanged.connect(self._on_enable_changed)
        ai_layout.addWidget(self._enable_checkbox)

        # Settings group
        settings_group = QGroupBox(t("ai_api_config"))
        settings_layout = QVBoxLayout()
        settings_layout.setSpacing(10)

        # Base URL
        base_url_layout = QHBoxLayout()
        base_url_label = QLabel(t("ai_base_url"))
        base_url_label.setMinimumWidth(100)
        self._base_url_input = QLineEdit()
        self._base_url_input.setPlaceholderText("https://api.example.com/v1")
        base_url_layout.addWidget(base_url_label)
        base_url_layout.addWidget(self._base_url_input)
        settings_layout.addLayout(base_url_layout)

        # API Key
        api_key_layout = QHBoxLayout()
        api_key_label = QLabel(t("ai_api_key"))
        api_key_label.setMinimumWidth(100)
        self._api_key_input = QLineEdit()
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_input.setPlaceholderText(t("ai_api_key_placeholder"))
        api_key_layout.addWidget(api_key_label)
        api_key_layout.addWidget(self._api_key_input)
        settings_layout.addLayout(api_key_layout)

        # Model
        model_layout = QHBoxLayout()
        model_label = QLabel(t("ai_model"))
        model_label.setMinimumWidth(100)
        self._model_input = QLineEdit()
        self._model_input.setPlaceholderText("qwen-plus, gpt-3.5-turbo, etc.")
        model_layout.addWidget(model_label)
        model_layout.addWidget(self._model_input)
        settings_layout.addLayout(model_layout)

        # Hint label
        hint_label = QLabel(t("ai_settings_hint"))
        hint_label.setStyleSheet("font-size: 11px;")
        hint_label.setWordWrap(True)
        settings_layout.addWidget(hint_label)

        settings_group.setLayout(settings_layout)
        ai_layout.addWidget(settings_group)

        # Test button for AI
        test_btn = QPushButton(t("ai_test_connection"))
        test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        test_btn.clicked.connect(self._test_connection)
        ai_layout.addWidget(test_btn)

        ai_layout.addStretch()

        # AcoustID Settings Tab
        acoustid_tab = QWidget()
        acoustid_layout = QVBoxLayout(acoustid_tab)
        acoustid_layout.setSpacing(10)

        # Enable AcoustID checkbox
        self._acoustid_enable_checkbox = QCheckBox(t("acoustid_enable"))
        self._acoustid_enable_checkbox.setStyleSheet("font-weight: bold; font-size: 14px;")
        self._acoustid_enable_checkbox.stateChanged.connect(self._on_acoustid_enable_changed)
        acoustid_layout.addWidget(self._acoustid_enable_checkbox)

        # AcoustID settings group
        acoustid_group = QGroupBox(t("acoustid_config"))
        acoustid_settings_layout = QVBoxLayout()
        acoustid_settings_layout.setSpacing(10)

        # AcoustID API Key
        acoustid_key_layout = QHBoxLayout()
        acoustid_key_label = QLabel(t("acoustid_api_key"))
        acoustid_key_label.setMinimumWidth(100)
        self._acoustid_api_key_input = QLineEdit()
        self._acoustid_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._acoustid_api_key_input.setPlaceholderText(t("acoustid_api_key_placeholder"))
        acoustid_key_layout.addWidget(acoustid_key_label)
        acoustid_key_layout.addWidget(self._acoustid_api_key_input)
        acoustid_settings_layout.addLayout(acoustid_key_layout)

        # AcoustID hint label
        acoustid_hint_label = QLabel(t("acoustid_settings_hint"))
        acoustid_hint_label.setStyleSheet("font-size: 11px;")
        acoustid_hint_label.setWordWrap(True)
        acoustid_settings_layout.addWidget(acoustid_hint_label)

        acoustid_group.setLayout(acoustid_settings_layout)
        acoustid_layout.addWidget(acoustid_group)

        # Test button for AcoustID
        acoustid_test_btn = QPushButton(t("acoustid_test"))
        acoustid_test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        acoustid_test_btn.clicked.connect(self._test_acoustid)
        acoustid_layout.addWidget(acoustid_test_btn)

        acoustid_layout.addStretch()

        # Cache Cleanup Settings Tab
        cache_tab = QWidget()
        cache_layout = QVBoxLayout(cache_tab)
        cache_layout.setSpacing(10)

        # Current cache info
        cache_info_group = QGroupBox(t("cache_current_info"))
        cache_info_layout = QVBoxLayout()
        self._cache_info_label = QLabel(t("loading"))
        self._cache_info_label.setStyleSheet(f"color: {theme.text_secondary}; font-size: 12px;")
        cache_info_layout.addWidget(self._cache_info_label)

        # Add button to open cache directory
        open_cache_btn = QPushButton(t("cache_open_directory"))
        open_cache_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_cache_btn.clicked.connect(self._open_cache_directory)
        cache_info_layout.addWidget(open_cache_btn)

        cache_info_group.setLayout(cache_info_layout)
        cache_layout.addWidget(cache_info_group)

        # Cleanup strategy
        strategy_group = QGroupBox(t("cache_cleanup_title"))
        strategy_layout = QVBoxLayout()
        strategy_layout.setSpacing(10)

        # Strategy selector
        strategy_selector_layout = QHBoxLayout()
        strategy_label = QLabel(t("cache_cleanup_strategy"))
        strategy_label.setMinimumWidth(120)
        self._strategy_combo = QComboBox()
        self._strategy_combo.setFixedWidth(300)
        # Add items
        self._strategy_combo.addItem(t("cache_cleanup_manual"))
        self._strategy_combo.setItemData(0, "manual", Qt.ItemDataRole.UserRole)
        self._strategy_combo.addItem(t("cache_cleanup_time"))
        self._strategy_combo.setItemData(1, "time", Qt.ItemDataRole.UserRole)
        self._strategy_combo.addItem(t("cache_cleanup_size"))
        self._strategy_combo.setItemData(2, "size", Qt.ItemDataRole.UserRole)
        self._strategy_combo.addItem(t("cache_cleanup_count"))
        self._strategy_combo.setItemData(3, "count", Qt.ItemDataRole.UserRole)
        self._strategy_combo.addItem(t("cache_cleanup_disabled"))
        self._strategy_combo.setItemData(4, "disabled", Qt.ItemDataRole.UserRole)
        self._strategy_combo.currentIndexChanged.connect(self._on_strategy_changed)
        strategy_selector_layout.addWidget(strategy_label)
        strategy_selector_layout.addWidget(self._strategy_combo)
        strategy_layout.addLayout(strategy_selector_layout)

        # Auto cleanup checkbox
        self._auto_cleanup_checkbox = QCheckBox(t("cache_auto_cleanup"))
        self._auto_cleanup_checkbox.setStyleSheet("font-weight: bold;")
        self._auto_cleanup_checkbox.stateChanged.connect(self._on_auto_cleanup_changed)
        strategy_layout.addWidget(self._auto_cleanup_checkbox)

        # Settings for each strategy
        settings_grid_layout = QHBoxLayout()

        # Time threshold (for time-based strategy)
        time_layout = QVBoxLayout()
        time_label_layout = QHBoxLayout()
        time_label = QLabel(t("cache_time_threshold"))
        time_label.setStyleSheet("font-size: 11px; color: #c0c0c0;")
        self._time_threshold_input = QLineEdit()
        self._time_threshold_input.setPlaceholderText("30")
        self._time_threshold_input.setMaximumWidth(80)
        time_days_label = QLabel(t("cache_days"))
        time_days_label.setStyleSheet("font-size: 11px; color: #a0a0a0;")
        time_label_layout.addWidget(time_label)
        time_label_layout.addStretch()
        time_label_layout.addWidget(self._time_threshold_input)
        time_label_layout.addWidget(time_days_label)
        time_layout.addLayout(time_label_layout)
        settings_grid_layout.addLayout(time_layout)

        # Size threshold (for size-based strategy)
        size_layout = QVBoxLayout()
        size_label_layout = QHBoxLayout()
        size_label = QLabel(t("cache_size_threshold"))
        size_label.setStyleSheet("font-size: 11px; color: #c0c0c0;")
        self._size_threshold_input = QLineEdit()
        self._size_threshold_input.setPlaceholderText("1000")
        self._size_threshold_input.setMaximumWidth(80)
        size_mb_label = QLabel("MB")
        size_mb_label.setStyleSheet("font-size: 11px; color: #a0a0a0;")
        size_label_layout.addWidget(size_label)
        size_label_layout.addStretch()
        size_label_layout.addWidget(self._size_threshold_input)
        size_label_layout.addWidget(size_mb_label)
        size_layout.addLayout(size_label_layout)
        settings_grid_layout.addLayout(size_layout)

        # Count threshold (for count-based strategy)
        count_layout = QVBoxLayout()
        count_label_layout = QHBoxLayout()
        count_label = QLabel(t("cache_count_threshold"))
        count_label.setStyleSheet("font-size: 11px; color: #c0c0c0;")
        self._count_threshold_input = QLineEdit()
        self._count_threshold_input.setPlaceholderText("100")
        self._count_threshold_input.setMaximumWidth(80)
        count_files_label = QLabel(t("cache_files"))
        count_files_label.setStyleSheet("font-size: 11px; color: #a0a0a0;")
        count_label_layout.addWidget(count_label)
        count_label_layout.addStretch()
        count_label_layout.addWidget(self._count_threshold_input)
        count_label_layout.addWidget(count_files_label)
        count_layout.addLayout(count_label_layout)
        settings_grid_layout.addLayout(count_layout)

        strategy_layout.addLayout(settings_grid_layout)

        # Interval settings
        interval_layout = QHBoxLayout()
        interval_label = QLabel(t("cache_cleanup_interval"))
        interval_label.setMinimumWidth(120)
        self._interval_input = QLineEdit()
        self._interval_input.setPlaceholderText("1")
        self._interval_input.setMaximumWidth(80)
        interval_hours_label = QLabel(t("cache_interval_hours").replace("{hours}", ""))
        interval_layout.addWidget(interval_label)
        interval_layout.addWidget(self._interval_input)
        interval_layout.addWidget(interval_hours_label)
        interval_layout.addStretch()
        strategy_layout.addLayout(interval_layout)

        # Hint label
        cache_hint = QLabel(t("cache_settings_hint"))
        cache_hint.setStyleSheet(f"color: {theme.text_secondary}; font-size: 11px;")
        cache_hint.setWordWrap(True)
        strategy_layout.addWidget(cache_hint)

        strategy_group.setLayout(strategy_layout)
        cache_layout.addWidget(strategy_group)

        # Manual cleanup button
        manual_cleanup_layout = QHBoxLayout()
        self._cleanup_now_btn = QPushButton(t("cache_cleanup_now"))
        self._cleanup_now_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cleanup_now_btn.clicked.connect(self._cleanup_now)
        manual_cleanup_layout.addWidget(self._cleanup_now_btn)
        manual_cleanup_layout.addStretch()
        cache_layout.addLayout(manual_cleanup_layout)

        cache_layout.addStretch()

        # Covers Tab
        covers_tab = QWidget()
        covers_layout = QVBoxLayout(covers_tab)
        covers_layout.setSpacing(10)

        # Only missing checkbox (shared by both sections)
        self._covers_missing_only = QCheckBox(t("batch_covers_missing_only"))
        self._covers_missing_only.setChecked(True)
        covers_layout.addWidget(self._covers_missing_only)

        # Artist covers section
        artist_covers_group = QGroupBox(t("artist_cover"))
        artist_covers_section = QVBoxLayout()
        artist_covers_section.setSpacing(8)

        self._artist_covers_count = QLabel()
        self._artist_covers_count.setStyleSheet(f"color: {theme.text_secondary}; font-size: 12px;")
        artist_covers_section.addWidget(self._artist_covers_count)

        artist_covers_hint = QLabel(t("batch_artist_covers_hint"))
        artist_covers_hint.setStyleSheet(f"color: {theme.text_secondary}; font-size: 11px;")
        artist_covers_hint.setWordWrap(True)
        artist_covers_section.addWidget(artist_covers_hint)

        self._download_artist_covers_btn = QPushButton(t("batch_download_artist_covers"))
        self._download_artist_covers_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._download_artist_covers_btn.clicked.connect(self._batch_download_artist_covers)
        artist_covers_section.addWidget(self._download_artist_covers_btn)

        artist_covers_group.setLayout(artist_covers_section)
        covers_layout.addWidget(artist_covers_group)

        # Album covers section
        album_covers_group = QGroupBox(t("album_art"))
        album_covers_section = QVBoxLayout()
        album_covers_section.setSpacing(8)

        self._album_covers_count = QLabel()
        self._album_covers_count.setStyleSheet(f"color: {theme.text_secondary}; font-size: 12px;")
        album_covers_section.addWidget(self._album_covers_count)

        album_covers_hint = QLabel(t("batch_album_covers_hint"))
        album_covers_hint.setStyleSheet(f"color: {theme.text_secondary}; font-size: 11px;")
        album_covers_hint.setWordWrap(True)
        album_covers_section.addWidget(album_covers_hint)

        self._download_album_covers_btn = QPushButton(t("batch_download_album_covers"))
        self._download_album_covers_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._download_album_covers_btn.clicked.connect(self._batch_download_album_covers)
        album_covers_section.addWidget(self._download_album_covers_btn)

        album_covers_group.setLayout(album_covers_section)
        covers_layout.addWidget(album_covers_group)

        # Fix album covers section
        fix_covers_group = QGroupBox(t("fix_album_covers"))
        fix_covers_section = QVBoxLayout()
        fix_covers_section.setSpacing(8)

        fix_covers_hint = QLabel(t("fix_album_covers_hint"))
        fix_covers_hint.setStyleSheet(f"color: {theme.text_secondary}; font-size: 11px;")
        fix_covers_hint.setWordWrap(True)
        fix_covers_section.addWidget(fix_covers_hint)

        self._fix_album_covers_btn = QPushButton(t("fix_album_covers_button"))
        self._fix_album_covers_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fix_album_covers_btn.clicked.connect(self._fix_album_covers)
        fix_covers_section.addWidget(self._fix_album_covers_btn)

        fix_covers_group.setLayout(fix_covers_section)
        covers_layout.addWidget(fix_covers_group)

        covers_layout.addStretch()

        # Repair Tab
        repair_tab = QWidget()
        repair_layout = QVBoxLayout(repair_tab)
        repair_layout.setSpacing(10)

        # Artist repair section
        artist_repair_group = QGroupBox(t("artist_repair"))
        artist_repair_section = QVBoxLayout()
        artist_repair_section.setSpacing(8)

        artist_repair_hint = QLabel(t("artist_repair_hint"))
        artist_repair_hint.setStyleSheet(f"color: {theme.text_secondary}; font-size: 11px;")
        artist_repair_hint.setWordWrap(True)
        artist_repair_section.addWidget(artist_repair_hint)

        self._rebuild_artists_btn = QPushButton(t("rebuild_artists"))
        self._rebuild_artists_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._rebuild_artists_btn.clicked.connect(self._rebuild_artists)
        artist_repair_section.addWidget(self._rebuild_artists_btn)

        artist_repair_group.setLayout(artist_repair_section)
        repair_layout.addWidget(artist_repair_group)

        # Album repair section
        album_repair_group = QGroupBox(t("album_repair"))
        album_repair_section = QVBoxLayout()
        album_repair_section.setSpacing(8)

        album_repair_hint = QLabel(t("album_repair_hint"))
        album_repair_hint.setStyleSheet(f"color: {theme.text_secondary}; font-size: 11px;")
        album_repair_hint.setWordWrap(True)
        album_repair_section.addWidget(album_repair_hint)

        self._rebuild_albums_btn = QPushButton(t("rebuild_albums"))
        self._rebuild_albums_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._rebuild_albums_btn.clicked.connect(self._rebuild_albums)
        album_repair_section.addWidget(self._rebuild_albums_btn)

        album_repair_group.setLayout(album_repair_section)
        repair_layout.addWidget(album_repair_group)

        # Junction table repair section
        junction_repair_group = QGroupBox(t("junction_repair"))
        junction_repair_section = QVBoxLayout()
        junction_repair_section.setSpacing(8)

        junction_repair_hint = QLabel(t("junction_repair_hint"))
        junction_repair_hint.setStyleSheet(f"color: {theme.text_secondary}; font-size: 11px;")
        junction_repair_hint.setWordWrap(True)
        junction_repair_section.addWidget(junction_repair_hint)

        self._rebuild_junction_btn = QPushButton(t("rebuild_junction"))
        self._rebuild_junction_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._rebuild_junction_btn.clicked.connect(self._rebuild_junction)
        junction_repair_section.addWidget(self._rebuild_junction_btn)

        junction_repair_group.setLayout(junction_repair_section)
        repair_layout.addWidget(junction_repair_group)

        repair_layout.addStretch()

        # Playback tab
        playback_tab = QWidget()
        playback_tab_layout = QVBoxLayout(playback_tab)
        playback_tab_layout.setSpacing(10)

        playback_group = QGroupBox(t("playback_settings"))
        playback_layout = QVBoxLayout()
        playback_layout.setSpacing(8)

        playback_row = QHBoxLayout()
        playback_label = QLabel(t("audio_engine"))
        playback_label.setMinimumWidth(120)
        self._audio_engine_combo = QComboBox()
        self._audio_engine_combo.setFixedWidth(320)
        for label, value in _get_audio_engine_options():
            self._audio_engine_combo.addItem(label, value)
        playback_row.addWidget(playback_label)
        playback_row.addWidget(self._audio_engine_combo)
        playback_row.addStretch()
        playback_layout.addLayout(playback_row)

        self._audio_engine_status_label = QLabel("")
        self._audio_engine_status_label.setStyleSheet(f"color: {theme.text_secondary}; font-size: 11px;")
        self._audio_engine_status_label.setWordWrap(True)
        playback_layout.addWidget(self._audio_engine_status_label)

        playback_hint = QLabel(t("audio_engine_restart_hint"))
        playback_hint.setStyleSheet(f"color: {theme.text_secondary}; font-size: 11px;")
        playback_hint.setWordWrap(True)
        playback_layout.addWidget(playback_hint)

        playback_group.setLayout(playback_layout)
        playback_tab_layout.addWidget(playback_group)
        playback_tab_layout.addStretch()

        # Appearance Tab
        appearance_tab = QWidget()
        appearance_layout = QVBoxLayout(appearance_tab)
        appearance_layout.setSpacing(10)

        # Preset Themes
        preset_group = QGroupBox(t("theme_settings"))
        preset_section = QVBoxLayout()
        preset_section.setSpacing(10)

        preset_label = QLabel(t("theme_presets"))
        preset_label.setStyleSheet("font-weight: bold;")
        preset_section.addWidget(preset_label)

        preset_btn_layout = QHBoxLayout()
        preset_btn_layout.setSpacing(8)

        from system.theme import PRESET_THEMES
        self._theme_preset_buttons = {}
        for theme_key in PRESET_THEMES:
            theme_preset = PRESET_THEMES[theme_key]
            btn = QPushButton(t(theme_preset.display_name))
            btn.setFixedHeight(35)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty("_skip_theme", True)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {theme_preset.highlight};
                    color: #ffffff;
                    border: 2px solid transparent;
                    border-radius: 4px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    border: 2px solid #ffffff;
                }}
            """)
            btn.clicked.connect(lambda checked, k=theme_key: self._select_theme_preset(k))
            preset_btn_layout.addWidget(btn)
            self._theme_preset_buttons[theme_key] = btn

        preset_section.addLayout(preset_btn_layout)

        # Custom Colors Group
        colors_group = QGroupBox(t("theme_custom_colors"))
        colors_layout = QGridLayout()
        colors_layout.setSpacing(8)
        colors_layout.setHorizontalSpacing(30)  # Add extra spacing between columns

        self._theme_color_labels = {}
        color_fields = [
            ('background', t("theme_background")),
            ('background_alt', t("theme_background_alt")),
            ('background_hover', t("theme_background_hover")),
            ('border', t("theme_border")),
            ('text', t("theme_text")),
            ('text_secondary', t("theme_text_secondary")),
            ('highlight', t("theme_highlight")),
            ('highlight_hover', t("theme_highlight_hover")),
            ('selection', t("theme_selection")),
        ]

        self._theme_color_inputs = {}
        self._theme_color_pickers = {}

        # Two-column layout
        for index, (field, label_text) in enumerate(color_fields):
            column = index % 2  # 0 for left column, 1 for right column
            row = index // 2  # Integer division to get row number

            # Each column uses 3 grid columns: label, color button, hex input
            grid_col = column * 3

            label = QLabel(label_text)
            colors_layout.addWidget(label, row, grid_col)

            # Color preview button
            color_btn = QPushButton()
            color_btn.setFixedSize(60, 28)
            color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            color_btn.setProperty("_skip_theme", True)
            colors_layout.addWidget(color_btn, row, grid_col + 1)

            # Hex input
            hex_input = QLineEdit()
            hex_input.setPlaceholderText("#RRGGBB")
            hex_input.setMaximumWidth(100)
            hex_input.setProperty("_skip_theme", True)
            hex_input.textChanged.connect(lambda text, f=field: self._on_theme_color_input_changed(f, text))
            colors_layout.addWidget(hex_input, row, grid_col + 2)

            self._theme_color_labels[field] = label
            self._theme_color_pickers[field] = color_btn
            self._theme_color_inputs[field] = hex_input

            # Connect picker click
            color_btn.clicked.connect(lambda checked, f=field: self._pick_theme_color(f))

        colors_group.setLayout(colors_layout)
        preset_section.addWidget(colors_group)

        # Preview
        preview_group = QGroupBox(t("theme_preview"))
        preview_layout = QVBoxLayout()

        self._theme_preview_frame = QFrame()
        self._theme_preview_frame.setFixedHeight(80)
        self._theme_preview_frame.setProperty("_skip_theme", True)
        preview_layout.addWidget(self._theme_preview_frame)

        preview_group.setLayout(preview_layout)
        preset_section.addWidget(preview_group)

        # Apply / Reset buttons
        theme_btn_layout = QHBoxLayout()
        self._theme_apply_btn = QPushButton(t("theme_apply"))
        self._theme_apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._theme_apply_btn.clicked.connect(self._apply_custom_theme)
        theme_btn_layout.addWidget(self._theme_apply_btn)

        self._theme_reset_btn = QPushButton(t("theme_reset"))
        self._theme_reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._theme_reset_btn.clicked.connect(self._reset_theme_colors)
        theme_btn_layout.addWidget(self._theme_reset_btn)

        preset_section.addLayout(theme_btn_layout)

        preset_group.setLayout(preset_section)
        appearance_layout.addWidget(preset_group)

        # Store temporary edit state
        self._theme_edit_colors = {}
        self._selected_preset_key = 'dark'

        appearance_layout.addStretch()

        tab_widget.addTab(playback_tab, t("playback_tab"))
        tab_widget.addTab(appearance_tab, t("theme_tab"))
        tab_widget.addTab(cache_tab, t("cache_tab"))
        tab_widget.addTab(covers_tab, t("covers_tab"))
        tab_widget.addTab(repair_tab, t("repair_tab"))
        tab_widget.addTab(ai_tab, t("ai_tab"))
        tab_widget.addTab(acoustid_tab, t("acoustid_tab"))
        bootstrap = Bootstrap.instance()
        tab_widget.addTab(
            PluginManagementTab(bootstrap.plugin_manager, self),
            t("plugins_tab"),
        )
        for spec in bootstrap.plugin_manager.registry.settings_tabs():
            plugin_tab = spec.widget_factory(bootstrap.plugin_manager, self)
            self._plugin_settings_tabs.append(plugin_tab)
            tab_widget.addTab(
                plugin_tab,
                spec.title_provider() if callable(getattr(spec, "title_provider", None)) else spec.title,
            )

        layout.addWidget(tab_widget)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        save_btn = QPushButton(t("save"))
        save_btn.setProperty("role", "primary")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._save_settings)
        button_layout.addWidget(save_btn)

        cancel_btn = QPushButton(t("cancel"))
        cancel_btn.setProperty("role", "cancel")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def _on_enable_changed(self, state):
        """Handle enable checkbox state change."""
        # state is an int from stateChanged signal
        # Qt.Checked = 2, but we also accept True (bool) for direct calls
        enabled = state is True or state == 2
        self._base_url_input.setEnabled(enabled)
        self._api_key_input.setEnabled(enabled)
        self._model_input.setEnabled(enabled)

    def _on_acoustid_enable_changed(self, state):
        """Handle AcoustID enable checkbox state change."""
        enabled = state is True or state == 2
        self._acoustid_api_key_input.setEnabled(enabled)

    def _on_strategy_changed(self, index):
        """Handle strategy combo box change."""
        strategy = self._strategy_combo.itemData(index)

        # Enable/disable threshold inputs based on strategy
        time_enabled = (strategy == "time")
        size_enabled = (strategy == "size")
        count_enabled = (strategy == "count")
        interval_enabled = (strategy in ("time", "size", "count"))

        self._time_threshold_input.setEnabled(time_enabled)
        self._size_threshold_input.setEnabled(size_enabled)
        self._count_threshold_input.setEnabled(count_enabled)
        self._interval_input.setEnabled(interval_enabled and self._auto_cleanup_checkbox.isChecked())
        self._cleanup_now_btn.setEnabled(strategy != "disabled")

    def _on_auto_cleanup_changed(self, state):
        """Handle auto cleanup checkbox state change."""
        enabled = state is True or state == 2
        strategy = self._strategy_combo.currentData()
        interval_enabled = enabled and (strategy in ("time", "size", "count"))
        self._interval_input.setEnabled(interval_enabled)

    def _load_settings(self):
        """Load settings from config."""
        # AI settings
        enabled = self._config.get_ai_enabled()
        base_url = self._config.get_ai_base_url()
        api_key = self._config.get_ai_api_key()
        model = self._config.get_ai_model()

        # Block signals to prevent triggering _on_enable_changed during setup
        self._enable_checkbox.blockSignals(True)
        self._enable_checkbox.setChecked(enabled)
        self._enable_checkbox.blockSignals(False)

        # Set text and enable state
        self._base_url_input.setText(base_url)
        self._api_key_input.setText(api_key)
        self._model_input.setText(model)

        # Manually set enabled state
        self._base_url_input.setEnabled(enabled)
        self._api_key_input.setEnabled(enabled)
        self._model_input.setEnabled(enabled)

        # AcoustID settings
        acoustid_enabled = self._config.get_acoustid_enabled()
        acoustid_api_key = self._config.get_acoustid_api_key()

        self._acoustid_enable_checkbox.blockSignals(True)
        self._acoustid_enable_checkbox.setChecked(acoustid_enabled)
        self._acoustid_enable_checkbox.blockSignals(False)

        self._acoustid_api_key_input.setText(acoustid_api_key)
        self._acoustid_api_key_input.setEnabled(acoustid_enabled)

        # Audio engine setting
        configured_engine = str(self._config.get_audio_engine()) if hasattr(self._config, "get_audio_engine") else "mpv"
        for i in range(self._audio_engine_combo.count()):
            if self._audio_engine_combo.itemData(i) == configured_engine:
                self._audio_engine_combo.setCurrentIndex(i)
                break
        runtime_engine = self._get_runtime_audio_engine()
        self._audio_engine_status_label.setText(
            t("audio_engine_status").format(runtime=runtime_engine, configured=configured_engine)
        )

        # Cache cleanup settings
        strategy = str(self._config.get_cache_cleanup_strategy())
        for i in range(self._strategy_combo.count()):
            if self._strategy_combo.itemData(i) == strategy:
                self._strategy_combo.setCurrentIndex(i)
                break

        auto_enabled = self._config.get_cache_cleanup_auto_enabled()
        self._auto_cleanup_checkbox.blockSignals(True)
        self._auto_cleanup_checkbox.setChecked(auto_enabled)
        self._auto_cleanup_checkbox.blockSignals(False)

        self._time_threshold_input.setText(str(self._config.get_cache_cleanup_time_days()))
        self._size_threshold_input.setText(str(self._config.get_cache_cleanup_size_mb()))
        self._count_threshold_input.setText(str(self._config.get_cache_cleanup_count()))
        self._interval_input.setText(str(self._config.get_cache_cleanup_interval_hours()))

        # Update cache info display
        self._update_cache_info()

        # Set initial enabled states
        self._on_strategy_changed(self._strategy_combo.currentIndex())
        self._on_auto_cleanup_changed(auto_enabled)

        # Update cover status
        self._update_covers_status()

        # Load theme settings
        theme_name = self._config.get('ui.theme', 'dark')
        self._select_theme_preset(theme_name, load_only=True)

    def _save_settings(self):
        """Save settings to config."""
        # AI settings
        enabled = self._enable_checkbox.isChecked()
        base_url = self._base_url_input.text().strip()
        api_key = self._api_key_input.text().strip()
        model = self._model_input.text().strip()

        # Validate AI settings
        if enabled:
            if not base_url:
                MessageDialog.warning(self, t("warning"), t("ai_base_url_required"))
                return
            if not api_key:
                MessageDialog.warning(self, t("warning"), t("ai_api_key_required"))
                return
            if not model:
                MessageDialog.warning(self, t("warning"), t("ai_model_required"))
                return

        # AcoustID settings
        acoustid_enabled = self._acoustid_enable_checkbox.isChecked()
        acoustid_api_key = self._acoustid_api_key_input.text().strip()

        # Validate AcoustID settings
        if acoustid_enabled and not acoustid_api_key:
            MessageDialog.warning(self, t("warning"), t("acoustid_api_key_required"))
            return

        if not self._save_plugin_settings_tabs():
            return

        # Save AI settings
        self._config.set_ai_enabled(enabled)
        self._config.set_ai_base_url(base_url)
        self._config.set_ai_api_key(api_key)
        self._config.set_ai_model(model)

        # Save AcoustID settings
        self._config.set_acoustid_enabled(acoustid_enabled)
        self._config.set_acoustid_api_key(acoustid_api_key)

        # Save audio engine setting
        selected_engine = self._audio_engine_combo.currentData()
        if hasattr(self._config, "set_audio_engine"):
            self._config.set_audio_engine(selected_engine)

        # Save cache cleanup settings
        strategy = self._strategy_combo.currentData()
        self._config.set_cache_cleanup_strategy(strategy)

        auto_enabled = self._auto_cleanup_checkbox.isChecked()
        self._config.set_cache_cleanup_auto_enabled(auto_enabled)

        # Save threshold values
        try:
            time_days = int(self._time_threshold_input.text()) if self._time_threshold_input.text() else 30
            size_mb = int(self._size_threshold_input.text()) if self._size_threshold_input.text() else 1000
            count = int(self._count_threshold_input.text()) if self._count_threshold_input.text() else 100
            interval = int(self._interval_input.text()) if self._interval_input.text() else 1

            # Validate values
            if time_days < 0:
                raise ValueError("Days must be >= 0")
            if size_mb < 0:
                raise ValueError("Size must be >= 0")
            if count < 0:
                raise ValueError("Count must be >= 0")
            if interval < 1:
                raise ValueError("Interval must be >= 1")

            self._config.set_cache_cleanup_time_days(time_days)
            self._config.set_cache_cleanup_size_mb(size_mb)
            self._config.set_cache_cleanup_count(count)
            self._config.set_cache_cleanup_interval_hours(interval)

        except ValueError as e:
            MessageDialog.warning(self, t("warning"), f"Invalid cache cleanup settings: {e}")
            return

        # Save theme (if changed from preset)
        if self._theme_edit_colors:
            self._apply_custom_theme()
        else:
            # Just ensure the current preset is applied
            try:
                from system.theme import ThemeManager
                theme = ThemeManager.instance()
                theme.set_theme(self._selected_preset_key)
            except Exception as e:
                logger.warning(f"Failed to apply theme: {e}")

        MessageDialog.information(self, t("success"), t("ai_settings_saved"))
        self.accept()

    def _save_plugin_settings_tabs(self) -> bool:
        """Persist mounted plugin settings tabs before closing the dialog."""
        for plugin_tab in self._plugin_settings_tabs:
            save_hook = getattr(plugin_tab, "_save", None)
            if not callable(save_hook):
                save_hook = getattr(plugin_tab, "_save_settings", None)
            if not callable(save_hook):
                continue
            try:
                save_hook()
            except Exception as exc:
                logger.warning("Failed to save plugin settings tab %r: %s", plugin_tab, exc, exc_info=True)
                MessageDialog.warning(self, t("warning"), f"Failed to save plugin settings: {exc}")
                return False
        return True

    def _get_runtime_audio_engine(self) -> str:
        """Get currently running engine name from parent window playback service."""
        parent = self.parent()
        try:
            playback = getattr(parent, "_playback", None)
            if playback is not None:
                backend = playback.engine.backend
                name = backend.__class__.__name__.lower()
                if "mpv" in name:
                    return "mpv"
                if "qt" in name:
                    return "qt"
        except Exception:
            pass
        return "unknown"

    def _test_connection(self):
        """Test the AI API connection."""
        base_url = self._base_url_input.text().strip()
        api_key = self._api_key_input.text().strip()
        model = self._model_input.text().strip()

        if not base_url or not api_key or not model:
            MessageDialog.warning(self, t("warning"), t("ai_fill_all_fields"))
            return

        # Test connection
        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=api_key,
                base_url=base_url,
            )

            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=10,
            )

            if response.choices:
                MessageDialog.information(self, t("success"), t("ai_connection_success"))
            else:
                MessageDialog.warning(self, t("warning"), t("ai_connection_failed"))

        except Exception as e:
            logger.error(f"AI connection test failed: {e}", exc_info=True)
            MessageDialog.critical(self, t("error"), f"{t('ai_connection_failed')}: {str(e)}")

    def _test_acoustid(self):
        """Test the AcoustID API key by checking if pyacoustid is installed."""
        acoustid_api_key = self._acoustid_api_key_input.text().strip()

        if not acoustid_api_key:
            MessageDialog.warning(self, t("warning"), t("acoustid_api_key_required"))
            return

        # Check if pyacoustid is installed
        try:
            if importlib_util.find_spec("acoustid") is None:
                raise ImportError
            # The API key can't be tested without an actual file,
            # but we can verify the format and that pyacoustid is installed
            MessageDialog.information(
                self, t("success"),
                t("acoustid_ready")
            )
        except ImportError:
            MessageDialog.warning(
                self, t("warning"),
                t("acoustid_not_installed")
            )

    def _open_cache_directory(self):
        """Open the cache directory in file explorer."""
        try:
            from app.bootstrap import Bootstrap

            download_service = Bootstrap.instance().online_download_service
            if not download_service:
                MessageDialog.warning(self, t("warning"), "Download service not available")
                return

            cache_dir = download_service._download_dir
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir, exist_ok=True)

            # Open directory based on platform
            import subprocess
            import platform

            system = platform.system()
            if system == "Windows":
                startfile = getattr(os, "startfile", None)
                if callable(startfile):
                    startfile(cache_dir)
            elif system == "Darwin":  # macOS
                subprocess.run(["open", cache_dir])
            else:  # Linux
                subprocess.run(["xdg-open", cache_dir])

        except Exception as e:
            logger.error(f"Failed to open cache directory: {e}")
            MessageDialog.critical(self, t("error"), f"Failed to open directory: {e}")

    def _update_cache_info(self):
        """Update cache information display."""
        try:
            from app.bootstrap import Bootstrap

            cache_cleaner = Bootstrap.instance().cache_cleaner_service
            if not cache_cleaner:
                return

            info = cache_cleaner.get_cache_info()
            file_count = info["file_count"]
            total_size = info["total_size"]

            # Format size
            if total_size < 1024:
                size_str = f"{total_size} B"
            elif total_size < 1024 * 1024:
                size_str = f"{total_size / 1024:.1f} KB"
            elif total_size < 1024 * 1024 * 1024:
                size_str = f"{total_size / (1024 * 1024):.1f} MB"
            else:
                size_str = f"{total_size / (1024 * 1024 * 1024):.1f} GB"

            self._cache_info_label.setText(
                f"{file_count} {t('cache_files')} • {size_str} {t('cache_size')}"
            )
        except Exception as e:
            logger.warning(f"Failed to update cache info: {e}")
            self._cache_info_label.setText(t("loading"))

    def _cleanup_now(self):
        """Execute manual cache cleanup."""
        try:
            from app.bootstrap import Bootstrap

            cache_cleaner = Bootstrap.instance().cache_cleaner_service
            if not cache_cleaner:
                MessageDialog.warning(self, t("warning"), "Cache cleaner service not available")
                return

            # Get current strategy (use manual to override auto cleanup)
            result = cache_cleaner.cleanup(strategy=None)

            files_deleted = result["files_deleted"]
            space_freed = result["space_freed"]

            # Format size
            if space_freed < 1024:
                space_str = f"{space_freed} B"
            elif space_freed < 1024 * 1024:
                space_str = f"{space_freed / 1024:.1f} KB"
            elif space_freed < 1024 * 1024 * 1024:
                space_str = f"{space_freed / (1024 * 1024):.1f} MB"
            else:
                space_str = f"{space_freed / (1024 * 1024 * 1024):.1f} GB"

            if files_deleted == 0:
                MessageDialog.information(self, t("success"), t("cache_no_cleanup_needed"))
            else:
                MessageDialog.information(
                    self, t("success"),
                    t("cache_cleanup_result").format(files=files_deleted, space=space_str)
                )

            # Update cache info
            self._update_cache_info()

        except Exception as e:
            logger.error(f"Manual cleanup failed: {e}")
            MessageDialog.critical(self, t("error"), f"Cleanup failed: {e}")

    def _update_covers_status(self):
        """Update cover counts."""
        try:
            from app.bootstrap import Bootstrap
            from pathlib import Path
            bootstrap = Bootstrap.instance()
            if not bootstrap:
                return
            library_service = bootstrap.library_service
            if not library_service:
                return

            artists = library_service.get_artists()
            total_artists = len(artists)
            missing_artists = sum(
                1 for a in artists
                if not a.cover_path or not Path(a.cover_path).exists()
            )
            self._artist_covers_count.setText(
                t("batch_covers_count_info").format(missing=missing_artists, total=total_artists)
            )

            albums = library_service.get_albums()
            total_albums = len(albums)
            missing_albums = sum(
                1 for a in albums
                if not a.cover_path or not Path(a.cover_path).exists()
            )
            self._album_covers_count.setText(
                t("batch_covers_count_info").format(missing=missing_albums, total=total_albums)
            )
        except Exception as e:
            logger.warning(f"Failed to update covers status: {e}")

    def _batch_download_artist_covers(self):
        """Start batch artist cover download."""
        from ui.workers.batch_cover_worker import BatchArtistCoverWorker
        from app.bootstrap import Bootstrap
        from pathlib import Path

        bootstrap = Bootstrap.instance()
        cover_service = bootstrap.cover_service
        library_service = bootstrap.library_service

        artists = library_service.get_artists()
        missing_only = self._covers_missing_only.isChecked()
        if missing_only:
            artists = [
                a for a in artists
                if not a.cover_path or not Path(a.cover_path).exists()
            ]

        if not artists:
            MessageDialog.information(self, t("artist_cover"), t("batch_no_missing_covers"))
            return

        self._download_artist_covers_btn.setEnabled(False)

        progress = ProgressDialog(
            t("batch_download_artist_covers"),
            t("batch_downloading_artist_cover"),
            t("cancel"),
            0, len(artists), self
        )

        worker = BatchArtistCoverWorker(cover_service, library_service, artists)
        self._batch_worker = worker

        def on_item(name):
            progress.setLabelText(f"{t('batch_downloading_artist_cover')}: {name}")

        def on_progress(current, total):
            progress.setValue(current)

        def on_finished(success, failed):
            progress.close()
            self._download_artist_covers_btn.setEnabled(True)
            self._batch_worker = None
            message = t("batch_cover_result").format(success=success, failed=failed)
            MessageDialog.information(self, t("batch_download_artist_covers"), message)
            self._update_covers_status()
            # Notify UI to refresh covers
            from system.event_bus import EventBus
            EventBus.instance().cover_updated.emit(None, True)

        def on_cancel():
            worker.cancel()

        worker.item_progress.connect(on_item)
        worker.progress.connect(on_progress)
        worker.finished_signal.connect(on_finished)
        progress.canceled.connect(on_cancel)

        progress.show()
        worker.start()

    def _batch_download_album_covers(self):
        """Start batch album cover download."""
        from ui.workers.batch_cover_worker import BatchAlbumCoverWorker
        from app.bootstrap import Bootstrap
        from pathlib import Path

        bootstrap = Bootstrap.instance()
        cover_service = bootstrap.cover_service
        library_service = bootstrap.library_service

        albums = library_service.get_albums()
        missing_only = self._covers_missing_only.isChecked()
        if missing_only:
            albums = [
                a for a in albums
                if not a.cover_path or (
                    not a.cover_path.startswith("http") and not Path(a.cover_path).exists()
                )
            ]

        if not albums:
            MessageDialog.information(self, t("album_art"), t("batch_no_missing_covers"))
            return

        self._download_album_covers_btn.setEnabled(False)

        progress = ProgressDialog(
            t("batch_download_album_covers"),
            t("batch_downloading_album_cover"),
            t("cancel"),
            0, len(albums), self
        )

        worker = BatchAlbumCoverWorker(cover_service, library_service, albums)
        self._batch_worker = worker

        def on_item(name):
            progress.setLabelText(f"{t('batch_downloading_album_cover')}: {name}")

        def on_progress(current, total):
            progress.setValue(current)

        def on_finished(success, failed):
            progress.close()
            self._download_album_covers_btn.setEnabled(True)
            self._batch_worker = None
            message = t("batch_cover_result").format(success=success, failed=failed)
            MessageDialog.information(self, t("batch_download_album_covers"), message)
            self._update_covers_status()
            from system.event_bus import EventBus
            EventBus.instance().cover_updated.emit(None, True)

        def on_cancel():
            worker.cancel()

        worker.item_progress.connect(on_item)
        worker.progress.connect(on_progress)
        worker.finished_signal.connect(on_finished)
        progress.canceled.connect(on_cancel)

        progress.show()
        worker.start()

    def _fix_album_covers(self):
        """Fix album covers by finding tracks with covers for albums without covers."""
        from app.bootstrap import Bootstrap
        from ui.dialogs.progress_dialog import ProgressDialog

        bootstrap = Bootstrap.instance()
        library_service = bootstrap.library_service

        # Get albums without covers
        albums = library_service.get_albums_without_cover()
        total = len(albums)

        if total == 0:
            MessageDialog.information(self, t("fix_album_covers"), t("fix_album_covers_no_missing"))
            return

        # Confirm with user
        reply = MessageDialog.question(
            self, t("fix_album_covers"),
            t("fix_album_covers_confirm").format(count=total),
            Yes | No,
            No
        )

        if reply != Yes:
            return

        self._fix_album_covers_btn.setEnabled(False)

        progress = ProgressDialog(
            t("fix_album_covers"),
            t("fix_album_covers_progress"),
            "",
            0, 0, self  # Indeterminate progress
        )
        progress.show()

        try:
            result = library_service.fix_album_covers()
            progress.close()

            message = t("fix_album_covers_success").format(
                fixed=result['fixed'],
                total=result['total']
            )
            MessageDialog.information(self, t("fix_album_covers"), message)

            # Update status and notify UI
            self._update_covers_status()
            from system.event_bus import EventBus
            EventBus.instance().cover_updated.emit(None, True)

        except Exception as e:
            progress.close()
            logger.error(f"Error fixing album covers: {e}", exc_info=True)
            MessageDialog.critical(self, t("fix_album_covers"), t("fix_album_covers_failed"))
        finally:
            self._fix_album_covers_btn.setEnabled(True)

    def _rebuild_artists(self):
        """Rebuild artists table from tracks."""
        from app.bootstrap import Bootstrap

        reply = MessageDialog.question(
            self, t("artist_repair"),
            t("rebuild_artists_confirm"),
            Yes | No,
            No
        )

        if reply != Yes:
            return

        try:
            bootstrap = Bootstrap.instance()
            library_service = bootstrap.library_service

            self._rebuild_artists_btn.setEnabled(False)
            self._rebuild_artists_btn.setText(t("rebuilding"))

            # Rebuild artists table
            library_service.rebuild_albums_artists()

            self._rebuild_artists_btn.setEnabled(True)
            self._rebuild_artists_btn.setText(t("rebuild_artists"))

            MessageDialog.information(self, t("success"), t("rebuild_artists_success"))

            # Refresh covers status
            self._update_covers_status()
        except Exception as e:
            logger.error(f"Failed to rebuild artists: {e}")
            self._rebuild_artists_btn.setEnabled(True)
            self._rebuild_artists_btn.setText(t("rebuild_artists"))
            MessageDialog.critical(self, t("error"), f"{t('rebuild_failed')}: {e}")

    def _rebuild_albums(self):
        """Rebuild albums table from tracks."""
        from app.bootstrap import Bootstrap

        reply = MessageDialog.question(
            self, t("album_repair"),
            t("rebuild_albums_confirm"),
            Yes | No,
            No
        )

        if reply != Yes:
            return

        try:
            bootstrap = Bootstrap.instance()
            library_service = bootstrap.library_service

            self._rebuild_albums_btn.setEnabled(False)
            self._rebuild_albums_btn.setText(t("rebuilding"))

            # Rebuild albums table
            library_service.rebuild_albums_artists()

            self._rebuild_albums_btn.setEnabled(True)
            self._rebuild_albums_btn.setText(t("rebuild_albums"))

            MessageDialog.information(self, t("success"), t("rebuild_albums_success"))

            # Refresh covers status
            self._update_covers_status()
        except Exception as e:
            logger.error(f"Failed to rebuild albums: {e}")
            self._rebuild_albums_btn.setEnabled(True)
            self._rebuild_albums_btn.setText(t("rebuild_albums"))
            MessageDialog.critical(self, t("error"), f"{t('rebuild_failed')}: {e}")

    def _rebuild_junction(self):
        """Rebuild track_artists junction table."""
        from app.bootstrap import Bootstrap

        reply = MessageDialog.question(
            self, t("junction_repair"),
            t("rebuild_junction_confirm"),
            Yes | No,
            No
        )

        if reply != Yes:
            return

        try:
            bootstrap = Bootstrap.instance()
            library_service = bootstrap.library_service

            self._rebuild_junction_btn.setEnabled(False)
            self._rebuild_junction_btn.setText(t("rebuilding"))

            # Rebuild junction table
            count = library_service.rebuild_track_artists()

            self._rebuild_junction_btn.setEnabled(True)
            self._rebuild_junction_btn.setText(t("rebuild_junction"))

            MessageDialog.information(
                self, t("success"),
                t("rebuild_junction_success").format(count=count)
            )
        except Exception as e:
            logger.error(f"Failed to rebuild junction: {e}")
            self._rebuild_junction_btn.setEnabled(True)
            self._rebuild_junction_btn.setText(t("rebuild_junction"))
            MessageDialog.critical(self, t("error"), f"{t('rebuild_failed')}: {e}")

    def closeEvent(self, event):
        """Handle dialog close event."""
        if self._batch_worker:
            self._batch_worker.cancel()
            self._batch_worker.quit()
            self._batch_worker.wait()
        event.accept()

    def _select_theme_preset(self, theme_key: str, load_only: bool = False):
        """Select a preset theme and update the color editor."""
        from system.theme import PRESET_THEMES

        self._selected_preset_key = theme_key
        theme = PRESET_THEMES.get(theme_key)
        if not theme:
            return

        # Highlight selected button
        for key, btn in self._theme_preset_buttons.items():
            if key == theme_key:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {theme.highlight};
                        color: #ffffff;
                        border: 2px solid #ffffff;
                        border-radius: 4px;
                        font-weight: bold;
                    }}
                """)
            else:
                other = PRESET_THEMES[key]
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {other.highlight};
                        color: #ffffff;
                        border: 2px solid transparent;
                        border-radius: 4px;
                        font-weight: bold;
                    }}
                    QPushButton:hover {{
                        border: 2px solid #ffffff;
                    }}
                """)

        # Fill color inputs from preset
        color_map = {
            'background': theme.background,
            'background_alt': theme.background_alt,
            'background_hover': theme.background_hover,
            'text': theme.text,
            'text_secondary': theme.text_secondary,
            'highlight': theme.highlight,
            'highlight_hover': theme.highlight_hover,
            'selection': theme.selection,
            'border': theme.border,
        }

        for field, color in color_map.items():
            self._theme_color_inputs[field].blockSignals(True)
            self._theme_color_inputs[field].setText(color)
            self._theme_color_inputs[field].blockSignals(False)
            self._theme_color_pickers[field].setStyleSheet(
                f"background-color: {color}; border: 1px solid #4a4a4a; border-radius: 4px;"
            )

        # Clear edit state
        self._theme_edit_colors = {}
        self._update_theme_preview(color_map)

        # Don't apply immediately - let user preview and click "Apply" button

    def _on_theme_color_input_changed(self, field: str, text: str):
        """Handle hex input change for a theme color field."""
        text = text.strip()
        if text.startswith("#") and len(text) == 7:
            color = QColor(text)
            if color.isValid():
                self._theme_edit_colors[field] = text
                self._theme_color_pickers[field].setStyleSheet(
                    f"background-color: {text}; border: 1px solid #4a4a4a; border-radius: 4px;"
                )
                self._update_theme_preview_from_state()

    def _pick_theme_color(self, field: str):
        """Open color picker for a theme color field."""
        current_text = self._theme_color_inputs[field].text().strip()
        initial = QColor(current_text) if current_text.startswith("#") else QColor()
        color = QColorDialog.getColor(initial, self, t("choose_color"))
        if color.isValid():
            hex_color = color.name()
            self._theme_color_inputs[field].blockSignals(True)
            self._theme_color_inputs[field].setText(hex_color)
            self._theme_color_inputs[field].blockSignals(False)
            self._theme_edit_colors[field] = hex_color
            self._theme_color_pickers[field].setStyleSheet(
                f"background-color: {hex_color}; border: 1px solid #4a4a4a; border-radius: 4px;"
            )
            self._update_theme_preview_from_state()

    def _get_current_theme_colors(self) -> dict:
        """Get current theme colors from inputs, applying edits on top of preset."""
        from system.theme import PRESET_THEMES
        base = PRESET_THEMES.get(self._selected_preset_key, PRESET_THEMES['dark'])
        color_map = {
            'background': base.background,
            'background_alt': base.background_alt,
            'background_hover': base.background_hover,
            'text': base.text,
            'text_secondary': base.text_secondary,
            'highlight': base.highlight,
            'highlight_hover': base.highlight_hover,
            'selection': base.selection,
            'border': base.border,
        }
        color_map.update(self._theme_edit_colors)
        return color_map

    def _update_theme_preview_from_state(self):
        """Update preview using current input state."""
        self._update_theme_preview(self._get_current_theme_colors())

    def _update_theme_preview(self, colors: dict):
        """Update the live preview frame with given colors."""
        c = colors
        self._theme_preview_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {c.get('background', '#121212')};
                border: 1px solid {c.get('border', '#3a3a3a')};
                border-radius: 8px;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        # Clear old preview content
        layout = self._theme_preview_frame.layout()
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                if item is None:
                    continue
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
        else:
            layout = QVBoxLayout(self._theme_preview_frame)
            layout.setContentsMargins(12, 8, 12, 8)
        preview_layout = cast(QVBoxLayout, layout)

        title = QLabel(t("theme_preview_text"))
        title.setStyleSheet(f"color: {c.get('text', '#ffffff')}; font-size: 14px; font-weight: bold;")
        secondary = QLabel(t("theme_preview_secondary"))
        secondary.setStyleSheet(f"color: {c.get('text_secondary', '#b3b3b3')}; font-size: 11px;")

        accent = QLabel("  ■  ")
        accent.setStyleSheet(f"color: {c.get('highlight', '#1db954')}; font-size: 16px; font-weight: bold;")
        accent.setMaximumWidth(40)

        h_layout = QHBoxLayout()
        h_layout.addWidget(accent)
        h_layout.addWidget(title)
        h_layout.addStretch()
        preview_layout.addLayout(h_layout)
        preview_layout.addWidget(secondary)

    def _apply_custom_theme(self):
        """Apply the current theme (preset or custom)."""
        colors = self._get_current_theme_colors()
        from system.theme import Theme, ThemeManager

        # Check if we're applying a preset or custom theme
        if not self._theme_edit_colors:
            # No custom edits - apply preset theme
            try:
                ThemeManager.instance().set_theme(self._selected_preset_key)
                MessageDialog.information(self, t("success"), t("theme_saved"))
            except Exception as e:
                logger.warning(f"Failed to apply theme: {e}")
        else:
            # Has custom edits - apply as custom theme
            custom_theme = Theme(
                name='Custom',
                display_name='theme_custom',
                **colors
            )
            try:
                ThemeManager.instance().set_custom_theme(custom_theme)
                MessageDialog.information(self, t("success"), t("theme_saved"))
            except Exception as e:
                logger.warning(f"Failed to apply custom theme: {e}")

    def _reset_theme_colors(self):
        """Reset custom color edits back to the selected preset."""
        self._theme_edit_colors = {}
        self._select_theme_preset(self._selected_preset_key)

    def refresh_theme(self):
        """Refresh theme when changed."""
        self._title_bar_controller.refresh_theme()

    def resizeEvent(self, event):
        """Apply rounded corner mask."""
        path = QPainterPath()
        path.addRoundedRect(self.rect(), 12, 12)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))
        super().resizeEvent(event)

# Backward compatibility alias
AISettingsDialog = GeneralSettingsDialog
