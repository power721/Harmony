"""
Compatibility shim for the QQ Music online tracks list view.

The concrete implementation now lives in
`plugins.builtin.qqmusic.lib.online_tracks_list_view`.
"""

import sys

from plugins.builtin.qqmusic.lib import online_tracks_list_view as _online_tracks_list_view

sys.modules[__name__] = _online_tracks_list_view
