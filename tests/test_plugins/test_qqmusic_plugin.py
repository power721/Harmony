from unittest.mock import Mock

from plugins.builtin.qqmusic.plugin_main import QQMusicPlugin


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
