"""
Tests for SqliteSettingsRepository.
"""

import os
import sqlite3
import tempfile

import pytest

from repositories.settings_repository import SqliteSettingsRepository


@pytest.fixture
def temp_db():
    """Create a temporary database for testing settings storage."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()

    yield db_path

    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def settings_repo(temp_db):
    """Create a settings repository with temporary database."""
    return SqliteSettingsRepository(temp_db)


class TestSqliteSettingsRepository:
    """Test SqliteSettingsRepository."""

    def test_string_literals_round_trip_without_type_drift(self, settings_repo):
        """String values that look like JSON scalars should stay strings after reload."""
        settings_repo.set("quality", "320")
        settings_repo.set("flag_text", "true")
        settings_repo.set("null_text", "null")

        assert settings_repo.get("quality") == "320"
        assert settings_repo.get("flag_text") == "true"
        assert settings_repo.get("null_text") == "null"

    def test_get_all_preserves_string_literals(self, settings_repo):
        """Bulk reads should preserve string literals exactly as written."""
        settings_repo.set("quality", "320")
        settings_repo.set("flag_text", "true")
        settings_repo.set("null_text", "null")

        values = settings_repo.get_all(["quality", "flag_text", "null_text"])

        assert values == {
            "quality": "320",
            "flag_text": "true",
            "null_text": "null",
        }

    def test_non_string_types_keep_their_original_types(self, settings_repo):
        """Structured and scalar non-string values should still deserialize correctly."""
        settings_repo.set("enabled", True)
        settings_repo.set("volume", 70)
        settings_repo.set("filters", ["a", "b"])
        settings_repo.set("metadata", {"mode": "shuffle"})

        assert settings_repo.get("enabled") is True
        assert settings_repo.get("volume") == 70
        assert settings_repo.get("filters") == ["a", "b"]
        assert settings_repo.get("metadata") == {"mode": "shuffle"}
