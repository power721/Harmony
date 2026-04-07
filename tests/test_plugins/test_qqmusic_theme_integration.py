from pathlib import Path
from unittest.mock import Mock

from plugins.builtin.qqmusic.lib.login_dialog import QQMusicLoginDialog
from plugins.builtin.qqmusic.lib.online_music_view import OnlineMusicView
from system.theme import ThemeManager


def _plugin_settings(tmp_path: Path):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "",
        "quality": "320",
        "search_history": [],
        "ranking_view_mode": "table",
    }.get(key, default)
    settings.set.side_effect = lambda key, value: None
    settings.get_language.return_value = "zh"
    settings.get_online_music_download_dir.return_value = str(tmp_path / "online-cache")
    return settings


def test_plugin_login_dialog_uses_host_owned_shell_and_title_bar_styles(qtbot, monkeypatch, tmp_path):
    ThemeManager._instance = None
    ThemeManager.instance(_plugin_settings(tmp_path))
    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.login_dialog.QQMusicLoginDialog._start_login",
        lambda self, login_type=None: None,
    )

    dialog = QQMusicLoginDialog()
    qtbot.addWidget(dialog)

    assert dialog.property("shell") is True
    assert dialog._title_bar_controller.title_bar.styleSheet() == ""
    assert dialog._title_bar_controller.close_btn.styleSheet() == ""
    assert dialog._cancel_button.property("role") == "cancel"

def test_online_music_view_search_input_uses_theme_variant_and_host_popup_helper(qtbot, tmp_path):
    settings = _plugin_settings(tmp_path)
    ThemeManager._instance = None
    ThemeManager.instance(settings)

    view = OnlineMusicView(config_manager=settings, qqmusic_service=None)
    qtbot.addWidget(view)

    assert view._search_input.property("variant") == "search"
    assert view._search_input.styleSheet() == ""
    assert view._completer.popup().styleSheet()
