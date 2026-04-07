"""
Compatibility shim for the QQ Music online detail view.

The concrete implementation now lives in
`plugins.builtin.qqmusic.lib.online_detail_view`.
"""

import sys

from plugins.builtin.qqmusic.lib import online_detail_view as _online_detail_view

sys.modules[__name__] = _online_detail_view
