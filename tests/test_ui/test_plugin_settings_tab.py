from unittest.mock import Mock

from PySide6.QtWidgets import QTabWidget, QWidget

from plugins.builtin.qqmusic.lib.login_dialog import QQMusicLoginDialog
from plugins.builtin.qqmusic.lib.settings_tab import QQMusicSettingsTab
from system.plugins.host_services import PluginSettingsBridgeImpl
from system.theme import ThemeManager
from ui.dialogs.plugin_management_tab import PluginManagementTab
from ui.dialogs.settings_dialog import GeneralSettingsDialog
from plugins.builtin.qqmusic.lib import i18n as plugin_i18n


class _Signal:
    def connect(self, _callback):
        return None


def _build_plugin_context(settings: Mock) -> Mock:
    theme = type(
        "Theme",
        (),
        {
            "background": "#101010",
            "background_alt": "#1a1a1a",
            "background_hover": "#202020",
            "text": "#ffffff",
            "text_secondary": "#999999",
            "highlight": "#1db954",
            "highlight_hover": "#1ed760",
            "selection": "#333333",
            "border": "#404040",
        },
    )()
    ui = Mock()
    ui.theme.get_qss.side_effect = lambda template: template
    ui.theme.current_theme.return_value = theme
    ui.theme.register_widget = Mock()
    ui.dialogs = Mock()
    events = Mock(language_changed=_Signal())
    return Mock(settings=settings, ui=ui, events=events, language="zh")


def _build_dialog_config(store: dict) -> Mock:
    config = Mock()
    config.get.side_effect = lambda key, default=None: store.get(key, default)
    config.set.side_effect = lambda key, value: store.__setitem__(key, value)
    config.get_ai_enabled.return_value = False
    config.get_ai_base_url.return_value = ""
    config.get_ai_api_key.return_value = ""
    config.get_ai_model.return_value = ""
    config.get_acoustid_enabled.return_value = False
    config.get_acoustid_api_key.return_value = ""
    config.get_cache_cleanup_strategy.return_value = "manual"
    config.get_cache_cleanup_auto_enabled.return_value = False
    config.get_cache_cleanup_time_days.return_value = 30
    config.get_cache_cleanup_size_mb.return_value = 1000
    config.get_cache_cleanup_count.return_value = 100
    config.get_cache_cleanup_interval_hours.return_value = 1
    config.get_audio_engine.return_value = "mpv"
    config.get_language.return_value = "zh"
    config.get_plugin_setting.side_effect = (
        lambda plugin_id, key, default=None: store.get(f"plugins.{plugin_id}.{key}", default)
    )
    config.get_plugin_secret.side_effect = (
        lambda plugin_id, key, default="": store.get(f"plugins.{plugin_id}.{key}", default)
    )
    config.set_plugin_secret.side_effect = (
        lambda plugin_id, key, value: store.__setitem__(f"plugins.{plugin_id}.{key}", value)
    )
    return config


def test_plugin_management_tab_shows_plugin_rows(qtbot):
    manager = Mock()
    manager.list_plugins.return_value = [
        {
            "id": "lrclib",
            "name": "LRCLIB",
            "version": "1.0.0",
            "source": "builtin",
            "enabled": True,
            "load_error": None,
        },
        {
            "id": "qqmusic",
            "name": "QQ Music",
            "version": "1.0.0",
            "source": "external",
            "enabled": False,
            "load_error": "load failed",
        },
    ]

    widget = PluginManagementTab(manager)
    qtbot.addWidget(widget)

    assert widget._list.count() == 2
    assert "qqmusic" not in widget._list.item(1).text().lower()
    assert "QQ Music" in widget._list.item(1).text()


def test_plugin_management_tab_can_toggle_selected_plugin_enabled_state(qtbot):
    manager = Mock()
    manager.list_plugins.return_value = [
        {
            "id": "qqmusic",
            "name": "QQ Music",
            "version": "1.0.0",
            "source": "builtin",
            "enabled": True,
            "load_error": None,
        },
        {
            "id": "lrclib",
            "name": "LRCLIB",
            "version": "1.0.0",
            "source": "builtin",
            "enabled": False,
            "load_error": None,
        },
    ]

    widget = PluginManagementTab(manager)
    qtbot.addWidget(widget)

    widget._list.setCurrentRow(0)
    widget._disable_btn.click()
    widget._list.setCurrentRow(1)
    widget._enable_btn.click()

    manager.set_plugin_enabled.assert_any_call("qqmusic", False)
    manager.set_plugin_enabled.assert_any_call("lrclib", True)
    assert manager.list_plugins.call_count >= 3


def test_settings_dialog_includes_plugins_tab(monkeypatch, qtbot):
    config = Mock()
    config.get.return_value = "dark"
    config.get_ai_enabled.return_value = False
    config.get_ai_base_url.return_value = ""
    config.get_ai_api_key.return_value = ""
    config.get_ai_model.return_value = ""
    config.get_acoustid_enabled.return_value = False
    config.get_acoustid_api_key.return_value = ""
    config.get_online_music_download_dir.return_value = "data/online_cache"
    config.get_cache_cleanup_strategy.return_value = "manual"
    config.get_cache_cleanup_auto_enabled.return_value = False
    config.get_cache_cleanup_time_days.return_value = 30
    config.get_cache_cleanup_size_mb.return_value = 1000
    config.get_cache_cleanup_count.return_value = 100
    config.get_cache_cleanup_interval_hours.return_value = 1
    config.get_audio_engine.return_value = "mpv"

    fake_manager = Mock()
    fake_manager.list_plugins.return_value = []
    fake_manager.registry.settings_tabs.return_value = []
    bootstrap = Mock(plugin_manager=fake_manager)
    monkeypatch.setattr("ui.dialogs.settings_dialog.Bootstrap.instance", lambda: bootstrap)
    ThemeManager._instance = None
    ThemeManager.instance(config)

    dialog = GeneralSettingsDialog(config)
    qtbot.addWidget(dialog)
    tab_widget = dialog.findChild(QTabWidget)

    tab_labels = [tab_widget.tabText(index) for index in range(tab_widget.count())]
    assert "Plugins" in tab_labels or "插件" in tab_labels


def test_settings_dialog_omits_qqmusic_tab_without_plugin(monkeypatch, qtbot):
    config = Mock()
    config.get.return_value = "dark"
    config.get_ai_enabled.return_value = False
    config.get_ai_base_url.return_value = ""
    config.get_ai_api_key.return_value = ""
    config.get_ai_model.return_value = ""
    config.get_acoustid_enabled.return_value = False
    config.get_acoustid_api_key.return_value = ""
    config.get_online_music_download_dir.return_value = "data/online_cache"
    config.get_cache_cleanup_strategy.return_value = "manual"
    config.get_cache_cleanup_auto_enabled.return_value = False
    config.get_cache_cleanup_time_days.return_value = 30
    config.get_cache_cleanup_size_mb.return_value = 1000
    config.get_cache_cleanup_count.return_value = 100
    config.get_cache_cleanup_interval_hours.return_value = 1
    config.get_audio_engine.return_value = "mpv"

    fake_manager = Mock()
    fake_manager.list_plugins.return_value = []
    fake_manager.registry.settings_tabs.return_value = []
    bootstrap = Mock(plugin_manager=fake_manager)
    monkeypatch.setattr("ui.dialogs.settings_dialog.Bootstrap.instance", lambda: bootstrap)
    ThemeManager._instance = None
    ThemeManager.instance(config)

    dialog = GeneralSettingsDialog(config)
    qtbot.addWidget(dialog)
    tab_widget = dialog.findChild(QTabWidget)

    tab_labels = [tab_widget.tabText(index) for index in range(tab_widget.count())]
    assert "QQ音乐" not in tab_labels
    assert "QQ Music" not in tab_labels


def test_settings_dialog_with_real_builtins_includes_plugin_tabs(monkeypatch, qtbot):
    from app.bootstrap import Bootstrap

    Bootstrap._instance = None
    config = Mock()
    config.get.return_value = "dark"
    config.get_ai_enabled.return_value = False
    config.get_ai_base_url.return_value = ""
    config.get_ai_api_key.return_value = ""
    config.get_ai_model.return_value = ""
    config.get_acoustid_enabled.return_value = False
    config.get_acoustid_api_key.return_value = ""
    config.get_online_music_download_dir.return_value = "data/online_cache"
    config.get_cache_cleanup_strategy.return_value = "manual"
    config.get_cache_cleanup_auto_enabled.return_value = False
    config.get_cache_cleanup_time_days.return_value = 30
    config.get_cache_cleanup_size_mb.return_value = 1000
    config.get_cache_cleanup_count.return_value = 100
    config.get_cache_cleanup_interval_hours.return_value = 1
    config.get_audio_engine.return_value = "mpv"
    config.get_language.return_value = "zh"
    config.get_plugin_setting.side_effect = lambda plugin_id, key, default=None: default
    config.get_plugin_secret.side_effect = lambda plugin_id, key, default="": default

    bootstrap = Bootstrap(":memory:")
    bootstrap._config = config
    bootstrap._event_bus = Mock()
    bootstrap._http_client = Mock()
    bootstrap._playback_service = Mock()
    bootstrap._library_service = Mock()
    bootstrap._online_download_service = Mock()

    plugin_i18n.set_language("zh")

    monkeypatch.setattr("ui.dialogs.settings_dialog.Bootstrap.instance", lambda: bootstrap)
    ThemeManager._instance = None
    ThemeManager.instance(config)

    dialog = GeneralSettingsDialog(config)
    qtbot.addWidget(dialog)
    tab_widget = dialog.findChild(QTabWidget)

    tab_labels = [tab_widget.tabText(index) for index in range(tab_widget.count())]
    assert "QQ 音乐" in tab_labels


def test_settings_dialog_save_persists_qqmusic_download_dir(monkeypatch, qtbot):
    store = {}
    config = _build_dialog_config(store)
    settings_spec = type(
        "Spec",
        (),
        {
            "plugin_id": "qqmusic",
            "tab_id": "qqmusic.settings",
            "title": "QQ Music",
            "order": 80,
            "title_provider": staticmethod(lambda: "QQ 音乐"),
            "widget_factory": staticmethod(
                lambda _context, parent: QQMusicSettingsTab(
                    _build_plugin_context(PluginSettingsBridgeImpl("qqmusic", config)),
                    parent,
                )
            ),
        },
    )()
    fake_manager = Mock()
    fake_manager.list_plugins.return_value = []
    fake_manager.registry.settings_tabs.return_value = [settings_spec]
    bootstrap = Mock(plugin_manager=fake_manager)

    plugin_i18n.set_language("zh")

    monkeypatch.setattr("ui.dialogs.settings_dialog.Bootstrap.instance", lambda: bootstrap)
    monkeypatch.setattr("ui.dialogs.settings_dialog.MessageDialog.information", lambda *args, **kwargs: None)
    ThemeManager._instance = None
    ThemeManager.instance(config)

    dialog = GeneralSettingsDialog(config)
    qtbot.addWidget(dialog)

    tab = next(widget for widget in dialog.findChildren(QQMusicSettingsTab))
    tab._download_dir_input.setText("/tmp/music")

    dialog._save_settings()

    reopened = GeneralSettingsDialog(config)
    qtbot.addWidget(reopened)
    reopened_tab = next(widget for widget in reopened.findChildren(QQMusicSettingsTab))

    assert store["plugins.qqmusic.download_dir"] == "/tmp/music"
    assert reopened_tab._download_dir_input.text() == "/tmp/music"


def test_settings_dialog_uses_plugin_title_provider(monkeypatch, qtbot):
    config = Mock()
    config.get.return_value = "dark"
    config.get_ai_enabled.return_value = False
    config.get_ai_base_url.return_value = ""
    config.get_ai_api_key.return_value = ""
    config.get_ai_model.return_value = ""
    config.get_acoustid_enabled.return_value = False
    config.get_acoustid_api_key.return_value = ""
    config.get_online_music_download_dir.return_value = "data/online_cache"
    config.get_cache_cleanup_strategy.return_value = "manual"
    config.get_cache_cleanup_auto_enabled.return_value = False
    config.get_cache_cleanup_time_days.return_value = 30
    config.get_cache_cleanup_size_mb.return_value = 1000
    config.get_cache_cleanup_count.return_value = 100
    config.get_cache_cleanup_interval_hours.return_value = 1
    config.get_audio_engine.return_value = "mpv"

    fake_manager = Mock()
    fake_manager.list_plugins.return_value = []
    fake_manager.registry.settings_tabs.return_value = [
        type(
            "Spec",
            (),
            {
                "plugin_id": "qqmusic",
                "tab_id": "qqmusic.settings",
                "title": "QQ Music",
                "order": 80,
                "title_provider": staticmethod(lambda: "QQ 音乐"),
                "widget_factory": staticmethod(lambda _context, parent: QWidget(parent)),
            },
        )()
    ]
    bootstrap = Mock(plugin_manager=fake_manager)
    monkeypatch.setattr("ui.dialogs.settings_dialog.Bootstrap.instance", lambda: bootstrap)
    ThemeManager._instance = None
    ThemeManager.instance(config)

    dialog = GeneralSettingsDialog(config)
    qtbot.addWidget(dialog)
    tab_widget = dialog.findChild(QTabWidget)

    tab_labels = [tab_widget.tabText(index) for index in range(tab_widget.count())]
    assert "QQ 音乐" in tab_labels


def test_qqmusic_settings_tab_matches_legacy_sections(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "quality": "320",
        "download_dir": "data/online_cache",
        "credential": {"musicid": "12345", "loginType": 2},
        "nick": "Tester",
    }.get(key, default)
    context = _build_plugin_context(settings)

    widget = QQMusicSettingsTab(context)
    qtbot.addWidget(widget)

    assert widget._quality_combo.count() >= 3
    assert widget._download_dir_input.text() == "data/online_cache"
    assert widget._qqmusic_qr_btn.isHidden() is False
    assert widget._qqmusic_logout_btn.isHidden() is False
    assert widget._qqmusic_status_label.text()
    assert hasattr(widget, "_open_qqmusic_qr_login")
    assert hasattr(widget, "_qqmusic_logout")


def test_qqmusic_settings_tab_save_writes_plugin_scoped_settings(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "quality": "320",
        "download_dir": "",
        "credential": None,
        "nick": "",
    }.get(key, default)
    context = _build_plugin_context(settings)

    widget = QQMusicSettingsTab(context)
    qtbot.addWidget(widget)
    widget._download_dir_input.setText("/tmp/music")
    widget._quality_combo.setCurrentIndex(1)
    widget._save_settings()

    settings.set.assert_any_call("download_dir", "/tmp/music")
    settings.set.assert_any_call("quality", widget._quality_combo.currentData())


def test_qqmusic_settings_tab_translates_quality_labels(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "quality": "320",
        "download_dir": "data/online_cache",
        "credential": None,
        "nick": "",
    }.get(key, default)
    context = _build_plugin_context(settings)

    widget = QQMusicSettingsTab(context)
    qtbot.addWidget(widget)

    assert widget._quality_group.title() != "qqmusic_quality"
    assert widget._quality_label.text() != "qqmusic_quality"
    assert widget._quality_combo.itemText(0) != "qqmusic_quality_master"


def test_qqmusic_settings_tab_applies_popup_stylesheet_directly(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "quality": "320",
        "download_dir": "data/online_cache",
        "credential": None,
        "nick": "",
    }.get(key, default)
    context = _build_plugin_context(settings)

    widget = QQMusicSettingsTab(context)
    qtbot.addWidget(widget)

    stylesheet = widget._quality_combo.view().styleSheet()
    popup_stylesheet = widget._quality_combo.view().window().styleSheet()
    assert "background-color" in stylesheet
    assert "selection-background-color" in stylesheet
    assert "QListView::item" in stylesheet
    assert "background-color" in popup_stylesheet


def test_qqmusic_settings_tab_keeps_content_padding(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "quality": "320",
        "download_dir": "data/online_cache",
        "credential": None,
        "nick": "",
    }.get(key, default)
    context = _build_plugin_context(settings)

    widget = QQMusicSettingsTab(context)
    qtbot.addWidget(widget)

    layout = widget._qqmusic_tab.layout()
    margins = layout.contentsMargins()
    assert margins.left() > 0
    assert margins.top() > 0


def test_qqmusic_login_dialog_uses_dialog_container_selector_and_scoped_button_style():
    assert "QWidget#dialogContainer" in QQMusicLoginDialog._STYLE_TEMPLATE
    assert "QWidget#settingsContainer" not in QQMusicLoginDialog._STYLE_TEMPLATE
    assert "QPushButton#loginDialogActionBtn" in QQMusicLoginDialog._STYLE_TEMPLATE
