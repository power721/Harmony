"""
System module - Application-wide components.
"""

from .config import ConfigManager
from .event_bus import EventBus
from .i18n import t, set_language

# Lazy import for hotkeys to avoid circular dependency
def get_global_hotkeys():
    """Get GlobalHotkeys class (lazy import)."""
    from .hotkeys import GlobalHotkeys
    return GlobalHotkeys

__all__ = ['ConfigManager', 'EventBus', 't', 'set_language', 'get_global_hotkeys']
