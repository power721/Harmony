from unittest.mock import Mock

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
