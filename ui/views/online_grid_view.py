"""
Compatibility shim for the QQ Music online grid view.

The concrete implementation now lives in
`plugins.builtin.qqmusic.lib.online_grid_view`.
"""

import sys

from plugins.builtin.qqmusic.lib import online_grid_view as _online_grid_view

sys.modules[__name__] = _online_grid_view
