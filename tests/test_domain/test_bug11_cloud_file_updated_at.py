"""
Tests for bug fix: Bug 11 - CloudFile.updated_at initialization.

Previously CloudFile.__post_init__ only initialized created_at, not updated_at.
"""

import pytest
from datetime import datetime
from domain.cloud import CloudFile


class TestBug11CloudFileUpdatedAt:
    """Bug 11: CloudFile should auto-initialize updated_at."""

    def test_default_initialization_sets_both_timestamps(self):
        """Both created_at and updated_at should be auto-set."""
        cf = CloudFile()
        assert isinstance(cf.created_at, datetime)
        assert isinstance(cf.updated_at, datetime)

    def test_explicit_created_at_keeps_value(self):
        """Explicit created_at should be preserved."""
        explicit = datetime(2025, 1, 1, 12, 0, 0)
        cf = CloudFile(created_at=explicit)
        assert cf.created_at == explicit
        assert isinstance(cf.updated_at, datetime)  # Still auto-set

    def test_explicit_updated_at_keeps_value(self):
        """Explicit updated_at should be preserved."""
        explicit = datetime(2025, 6, 1, 12, 0, 0)
        cf = CloudFile(updated_at=explicit)
        assert cf.updated_at == explicit

    def test_both_explicit_values_preserved(self):
        """Both explicit timestamps should be preserved."""
        created = datetime(2025, 1, 1)
        updated = datetime(2025, 6, 1)
        cf = CloudFile(created_at=created, updated_at=updated)
        assert cf.created_at == created
        assert cf.updated_at == updated

    def test_updated_at_auto_set_after_created_at(self):
        """Auto-set updated_at should be >= created_at."""
        cf = CloudFile()
        assert cf.updated_at >= cf.created_at
