"""
Compatibility shim for the retired host online music view.

The concrete implementation now lives in `legacy_online_music_view.py` so the
runtime can make its legacy-only status explicit while keeping older tests and
imports working during the plugin migration.
"""

import sys

from . import legacy_online_music_view as _legacy_online_music_view

sys.modules[__name__] = _legacy_online_music_view
