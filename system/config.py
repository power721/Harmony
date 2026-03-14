"""
Configuration manager for the music player.
Unified configuration storage using database.
"""
import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from infrastructure.database import DatabaseManager

# Configure logging
logger = logging.getLogger(__name__)


# Setting key constants
class SettingKey:
    """Constants for setting keys."""

    # Player settings (shared)
    PLAYER_VOLUME = "player.volume"
    PLAYER_PLAY_MODE = "player.play_mode"

    # Playback source
    PLAYER_SOURCE = "player.source"  # "local" or "cloud"

    # Local playback state
    PLAYER_CURRENT_TRACK_ID = "player.current_track_id"
    PLAYER_POSITION = "player.position"
    PLAYER_WAS_PLAYING = "player.was_playing"

    # Cloud playback state
    CLOUD_ACCOUNT_ID = "cloud.account_id"
    CLOUD_DOWNLOAD_DIR = "cloud.download_dir"

    # UI settings
    UI_LANGUAGE = "ui.language"
    UI_GEOMETRY = "ui.geometry"
    UI_SPLITTER = "ui.splitter"

    # AI settings
    AI_ENABLED = "ai.enabled"
    AI_BASE_URL = "ai.base_url"
    AI_API_KEY = "ai.api_key"
    AI_MODEL = "ai.model"

    # AcoustID settings
    ACOUSTID_ENABLED = "acoustid.enabled"
    ACOUSTID_API_KEY = "acoustid.api_key"


class ConfigManager:
    """
    Manage application configuration using database storage.

    This class provides a unified interface for all application settings.
    Settings are stored in the 'settings' table in the SQLite database.
    """

    def __init__(self, db_manager: "DatabaseManager"):
        """
        Initialize config manager.

        Args:
            db_manager: DatabaseManager instance for database operations
        """
        self._db = db_manager

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self._db.get_setting(key, default)

    def set(self, key: str, value: Any):
        """
        Set a configuration value.

        Args:
            key: Configuration key
            value: Value to set
        """
        self._db.set_setting(key, value)

    def get_multiple(self, keys: list) -> Dict[str, Any]:
        """
        Get multiple configuration values.

        Args:
            keys: List of configuration keys

        Returns:
            Dict of key-value pairs
        """
        return self._db.get_settings(keys)

    def delete(self, key: str):
        """
        Delete a configuration value.

        Args:
            key: Configuration key
        """
        self._db.delete_setting(key)

    # ===== Player settings =====

    def get_play_mode(self) -> int:
        """
        Get the saved play mode as integer.

        Returns:
            Play mode integer (0-5, see PlayMode enum)
        """
        return self.get(SettingKey.PLAYER_PLAY_MODE, 0)

    def set_play_mode(self, mode: int):
        """
        Set the play mode.

        Args:
            mode: Play mode integer (0-5)
        """
        self.set(SettingKey.PLAYER_PLAY_MODE, mode)

    def get_volume(self) -> int:
        """
        Get the saved volume level.

        Returns:
            Volume level (0-100)
        """
        return self.get(SettingKey.PLAYER_VOLUME, 70)

    def set_volume(self, volume: int):
        """
        Set the volume level.

        Args:
            volume: Volume level (0-100)
        """
        self.set(SettingKey.PLAYER_VOLUME, volume)

    def get_playback_source(self) -> str:
        """
        Get the playback source.

        Returns:
            "local" or "cloud"
        """
        return self.get(SettingKey.PLAYER_SOURCE, "local")

    def set_playback_source(self, source: str):
        """
        Set the playback source.

        Args:
            source: "local" or "cloud"
        """
        self.set(SettingKey.PLAYER_SOURCE, source)

    # ===== Local playback state =====

    def get_current_track_id(self) -> int:
        """
        Get the current local track ID.

        Returns:
            Track ID (0 if not set)
        """
        return self.get(SettingKey.PLAYER_CURRENT_TRACK_ID, 0)

    def set_current_track_id(self, track_id: int):
        """
        Set the current local track ID.

        Args:
            track_id: Track ID
        """
        self.set(SettingKey.PLAYER_CURRENT_TRACK_ID, track_id)

    def get_playback_position(self) -> int:
        """
        Get the playback position.

        Returns:
            Position in milliseconds
        """
        return self.get(SettingKey.PLAYER_POSITION, 0)

    def set_playback_position(self, position: int):
        """
        Set the playback position.

        Args:
            position: Position in milliseconds
        """
        self.set(SettingKey.PLAYER_POSITION, position)

    def get_was_playing(self) -> bool:
        """
        Get whether the player was playing when app closed.

        Returns:
            True if was playing
        """
        return self.get(SettingKey.PLAYER_WAS_PLAYING, False)

    def set_was_playing(self, was_playing: bool):
        """
        Set whether the player was playing.

        Args:
            was_playing: True if was playing
        """
        self.set(SettingKey.PLAYER_WAS_PLAYING, was_playing)

    # ===== Cloud settings =====

    def get_cloud_account_id(self) -> Optional[int]:
        """
        Get the current cloud account ID.

        Returns:
            Account ID or None
        """
        return self.get(SettingKey.CLOUD_ACCOUNT_ID)

    def set_cloud_account_id(self, account_id: int):
        """
        Set the current cloud account ID.

        Args:
            account_id: Account ID
        """
        self.set(SettingKey.CLOUD_ACCOUNT_ID, account_id)

    def get_cloud_download_dir(self) -> str:
        """
        Get the cloud drive download directory.

        Returns:
            Path to cloud download directory (default: ./data/cloud_downloads)
        """
        return self.get(SettingKey.CLOUD_DOWNLOAD_DIR, "data/cloud_downloads")

    def set_cloud_download_dir(self, dir_path: str):
        """
        Set the cloud drive download directory.

        Args:
            dir_path: Path to cloud download directory
        """
        self.set(SettingKey.CLOUD_DOWNLOAD_DIR, dir_path)

    def clear_cloud_account_id(self):
        """Clear the current cloud account ID."""
        self.delete(SettingKey.CLOUD_ACCOUNT_ID)

    # ===== UI settings =====

    def get_language(self) -> str:
        """
        Get the UI language.

        Returns:
            Language code ("en" or "zh")
        """
        return self.get(SettingKey.UI_LANGUAGE, "en")

    def set_language(self, language: str):
        """
        Set the UI language.

        Args:
            language: Language code ("en" or "zh")
        """
        self.set(SettingKey.UI_LANGUAGE, language)

    def get_geometry(self) -> Optional[bytes]:
        """
        Get the saved window geometry.

        Returns:
            Geometry bytes or None
        """
        import base64
        geometry_b64 = self.get(SettingKey.UI_GEOMETRY)
        if geometry_b64:
            try:
                return base64.b64decode(geometry_b64)
            except Exception:
                return None
        return None

    def set_geometry(self, geometry: bytes):
        """
        Set the window geometry.

        Args:
            geometry: Geometry bytes from saveGeometry()
        """
        import base64
        self.set(SettingKey.UI_GEOMETRY, base64.b64encode(geometry).decode('utf-8'))

    def get_splitter_state(self) -> Optional[bytes]:
        """
        Get the saved splitter state.

        Returns:
            Splitter state bytes or None
        """
        import base64
        state_b64 = self.get(SettingKey.UI_SPLITTER)
        if state_b64:
            try:
                return base64.b64decode(state_b64)
            except Exception:
                return None
        return None

    def set_splitter_state(self, state: bytes):
        """
        Set the splitter state.

        Args:
            state: Splitter state bytes from saveState()
        """
        import base64
        self.set(SettingKey.UI_SPLITTER, base64.b64encode(state).decode('utf-8'))

    # ===== AI settings =====

    def get_ai_enabled(self) -> bool:
        """
        Get whether AI enhancement is enabled.

        Returns:
            True if AI enhancement is enabled
        """
        return self.get(SettingKey.AI_ENABLED, False)

    def set_ai_enabled(self, enabled: bool):
        """
        Set whether AI enhancement is enabled.

        Args:
            enabled: True to enable AI enhancement
        """
        self.set(SettingKey.AI_ENABLED, enabled)

    def get_ai_base_url(self) -> str:
        """
        Get the AI API base URL.

        Returns:
            Base URL string
        """
        return self.get(SettingKey.AI_BASE_URL, "https://dashscope.aliyuncs.com/compatible-mode/v1")

    def set_ai_base_url(self, base_url: str):
        """
        Set the AI API base URL.

        Args:
            base_url: Base URL string
        """
        self.set(SettingKey.AI_BASE_URL, base_url)

    def get_ai_api_key(self) -> str:
        """
        Get the AI API key.

        Returns:
            API key string
        """
        return self.get(SettingKey.AI_API_KEY, "")

    def set_ai_api_key(self, api_key: str):
        """
        Set the AI API key.

        Args:
            api_key: API key string
        """
        self.set(SettingKey.AI_API_KEY, api_key)

    def get_ai_model(self) -> str:
        """
        Get the AI model name.

        Returns:
            Model name string
        """
        return self.get(SettingKey.AI_MODEL, "qwen-plus")

    def set_ai_model(self, model: str):
        """
        Set the AI model name.

        Args:
            model: Model name string
        """
        self.set(SettingKey.AI_MODEL, model)

    # ===== AcoustID settings =====

    def get_acoustid_enabled(self) -> bool:
        """
        Get whether AcoustID fingerprinting is enabled.

        Returns:
            True if AcoustID is enabled
        """
        return self.get(SettingKey.ACOUSTID_ENABLED, False)

    def set_acoustid_enabled(self, enabled: bool):
        """
        Set whether AcoustID fingerprinting is enabled.

        Args:
            enabled: True to enable AcoustID
        """
        self.set(SettingKey.ACOUSTID_ENABLED, enabled)

    def get_acoustid_api_key(self) -> str:
        """
        Get the AcoustID API key.

        Returns:
            AcoustID API key string
        """
        return self.get(SettingKey.ACOUSTID_API_KEY, "")

    def set_acoustid_api_key(self, api_key: str):
        """
        Set the AcoustID API key.

        Args:
            api_key: AcoustID API key string
        """
        self.set(SettingKey.ACOUSTID_API_KEY, api_key)
