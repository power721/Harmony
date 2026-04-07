"""
Compatibility shim for the retired QQ Music legacy page.

The concrete implementation now lives in
`plugins.builtin.qqmusic.lib.online_music_view` so host-side QQ code can be
retired while preserving old imports and tests.
"""

import sys

from plugins.builtin.qqmusic.lib import online_music_view as _online_music_view

sys.modules[__name__] = _online_music_view
