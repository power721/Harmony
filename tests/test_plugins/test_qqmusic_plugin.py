from unittest.mock import Mock

from plugins.builtin.qqmusic.lib.login_dialog import QQMusicLoginDialog
from plugins.builtin.qqmusic.lib.qr_login import QQMusicQRLogin
from plugins.builtin.qqmusic.plugin_main import QQMusicPlugin
from plugins.builtin.qqmusic.lib.settings_tab import QQMusicSettingsTab


def test_qqmusic_plugin_registers_expected_capabilities():
    context = Mock()
    plugin = QQMusicPlugin()

    plugin.register(context)

    assert context.ui.register_sidebar_entry.call_count == 1
    assert context.ui.register_settings_tab.call_count == 1
    assert context.services.register_lyrics_source.call_count == 1
    assert context.services.register_cover_source.call_count == 1
    assert context.services.register_artist_cover_source.call_count == 1
    assert context.services.register_online_music_provider.call_count == 1


def test_qqmusic_settings_tab_reads_and_saves_quality(qtbot):
    settings = Mock()
    settings.get.return_value = "flac"
    context = Mock(settings=settings)

    tab = QQMusicSettingsTab(context)
    qtbot.addWidget(tab)

    assert tab._quality_combo.currentData() == "flac"

    tab._quality_combo.setCurrentIndex(0)
    tab._save()

    settings.set.assert_called_once_with("quality", tab._quality_combo.currentData())


def test_qqmusic_settings_tab_opens_login_dialog(monkeypatch, qtbot):
    settings = Mock()
    settings.get.return_value = "320"
    context = Mock(settings=settings)

    dialog = Mock()
    dialog_ctor = Mock(return_value=dialog)
    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.settings_tab.QQMusicLoginDialog",
        dialog_ctor,
    )

    tab = QQMusicSettingsTab(context)
    qtbot.addWidget(tab)

    tab._open_login_dialog()

    dialog_ctor.assert_called_once_with(tab)
    dialog.exec.assert_called_once_with()


def test_plugin_local_qr_login_client_builds_session():
    client = QQMusicQRLogin()

    https_adapter = client._session.get_adapter("https://u.y.qq.com/cgi-bin/musicu.fcg")

    assert https_adapter._pool_connections == 20
    assert https_adapter._pool_maxsize == 20
    assert https_adapter._pool_block is True


def test_plugin_login_dialog_uses_local_qr_client(qtbot):
    dialog = QQMusicLoginDialog()
    qtbot.addWidget(dialog)

    assert isinstance(dialog._client, QQMusicQRLogin)


def test_qqmusic_settings_tab_clears_plugin_credentials(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "quality": "320",
        "nick": "Tester",
    }.get(key, default)
    context = Mock(settings=settings)

    tab = QQMusicSettingsTab(context)
    qtbot.addWidget(tab)

    tab._clear_credentials()

    settings.set.assert_any_call("credential", None)
    settings.set.assert_any_call("nick", "")
