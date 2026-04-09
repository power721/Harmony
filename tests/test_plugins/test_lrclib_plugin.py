from unittest.mock import Mock

from plugins.builtin.lrclib.plugin_main import LRCLIBPlugin


def test_lrclib_plugin_registers_lyrics_source():
    context = Mock()
    plugin = LRCLIBPlugin()

    plugin.register(context)

    context.services.register_lyrics_source.assert_called_once()
