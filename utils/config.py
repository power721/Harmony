"""
Configuration manager for the music player.
"""

import json
from pathlib import Path
from typing import Any, Dict


class ConfigManager:
    """Manage application configuration."""

    def __init__(self, config_path: str = None):
        """
        Initialize config manager.

        Args:
            config_path: Path to config file (default: ~/.config/harmony_player/config.json)
        """
        if config_path is None:
            config_dir = Path.home() / ".config" / "harmony_player"
            config_dir.mkdir(parents=True, exist_ok=True)
            config_path = str(config_dir / "config.json")

        self._config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._load()

    def _load(self):
        """Load configuration from file."""
        if self._config_path.exists():
            try:
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading config: {e}")
                self._config = {}
        else:
            self._config = {}

    def _save(self):
        """Save configuration to file."""
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=4)
        except IOError as e:
            print(f"Error saving config: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self._config.get(key, default)

    def set(self, key: str, value: Any):
        """
        Set a configuration value.

        Args:
            key: Configuration key
            value: Value to set
        """
        self._config[key] = value
        self._save()

    def get_play_mode(self) -> int:
        """
        Get the saved play mode as integer.

        Returns:
            Play mode integer (0=Sequential, 1=Loop, 2=PlaylistLoop, 3=Random)
        """
        return self.get("play_mode", 0)  # 0 = SEQUENTIAL

    def set_play_mode(self, mode: int):
        """
        Set the play mode.

        Args:
            mode: Play mode integer (0=Sequential, 1=Loop, 2=PlaylistLoop, 3=Random)
        """
        self.set("play_mode", mode)

    def get_volume(self) -> int:
        """
        Get the saved volume level.

        Returns:
            Volume level (0-100)
        """
        return self.get("volume", 70)

    def set_volume(self, volume: int):
        """
        Set the volume level.

        Args:
            volume: Volume level (0-100)
        """
        self.set("volume", volume)

    def get_cloud_download_dir(self) -> str:
        """
        Get the cloud drive download directory.

        Returns:
            Path to cloud download directory (default: ./data/cloud_downloads)
        """
        return self.get("cloud_download_dir", "data/cloud_downloads")

    def set_cloud_download_dir(self, dir_path: str):
        """
        Set the cloud drive download directory.

        Args:
            dir_path: Path to cloud download directory
        """
        self.set("cloud_download_dir", dir_path)

    def get_cloud_playback_state(self) -> dict:
        """
        Get the saved cloud playback state.

        Returns:
            Dict with keys: account_id, file_path, file_fid, or empty dict if not set
        """
        return self.get("cloud_playback_state", {})

    def set_cloud_playback_state(self, account_id: int, file_path: str, file_fid: str):
        """
        Set the cloud playback state.

        Args:
            account_id: Cloud account ID
            file_path: Full path of the file in cloud drive
            file_fid: File ID in cloud drive
        """
        state = {
            "account_id": account_id,
            "file_path": file_path,
            "file_fid": file_fid
        }
        self.set("cloud_playback_state", state)

    def clear_cloud_playback_state(self):
        """Clear the saved cloud playback state."""
        self.set("cloud_playback_state", {})

    def get_cloud_was_playing(self) -> bool:
        """
        Get whether cloud was playing when app closed.

        Returns:
            True if cloud was playing, False otherwise
        """
        return self.get("cloud_was_playing", False)

    def set_cloud_was_playing(self, was_playing: bool):
        """
        Set whether cloud was playing.

        Args:
            was_playing: True if cloud was playing, False otherwise
        """
        self.set("cloud_was_playing", was_playing)
