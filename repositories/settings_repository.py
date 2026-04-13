"""
SQLite implementation of SettingsRepository.
"""

from typing import Any, Dict, List, TYPE_CHECKING

from repositories.base_repository import BaseRepository
from system.setting_value_codec import decode_setting_value, encode_setting_value

if TYPE_CHECKING:
    from infrastructure.database import DatabaseManager


class SqliteSettingsRepository(BaseRepository):
    """SQLite implementation of SettingsRepository."""

    def __init__(self, db_path: str = "Harmony.db", db_manager: "DatabaseManager | None" = None):
        super().__init__(db_path, db_manager)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a setting value by key.

        Args:
            key: Setting key
            default: Default value if not found

        Returns:
            Setting value or default
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()

        if row:
            return decode_setting_value(row["value"])
        return default

    def set(self, key: str, value: Any) -> bool:
        """
        Set a setting value.

        Args:
            key: Setting key
            value: Setting value (will be JSON serialized)

        Returns:
            True if set successfully
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        value_str = encode_setting_value(value)

        cursor.execute(
            """
            INSERT OR REPLACE INTO settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """,
            (key, value_str),
        )
        conn.commit()
        return cursor.rowcount > 0

    def set_many(self, values: Dict[str, Any]) -> bool:
        """
        Set multiple setting values in a single transaction.

        Args:
            values: Mapping of setting keys to values

        Returns:
            True if all values are persisted successfully
        """
        if not values:
            return True

        conn = self._get_connection()
        cursor = conn.cursor()
        payload = [
            (key, encode_setting_value(value))
            for key, value in values.items()
        ]

        try:
            cursor.executemany(
                """
                INSERT OR REPLACE INTO settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                """,
                payload,
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        return True

    def get_all(self, keys: List[str]) -> Dict[str, Any]:
        """
        Get multiple setting values.

        Args:
            keys: List of setting keys

        Returns:
            Dict of key-value pairs
        """
        if not keys:
            return {}

        conn = self._get_connection()
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(keys))
        cursor.execute(
            f"SELECT key, value FROM settings WHERE key IN ({placeholders})",
            keys,
        )
        rows = cursor.fetchall()

        result = {}
        for row in rows:
            result[row["key"]] = decode_setting_value(row["value"])
        return result

    def delete(self, key: str) -> bool:
        """
        Delete a setting.

        Args:
            key: Setting key

        Returns:
            True if deleted successfully
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM settings WHERE key = ?", (key,))
        conn.commit()
        return cursor.rowcount > 0
