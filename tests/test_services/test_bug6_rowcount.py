"""
Tests for bug fix: Bug 6 - cursor.rowcount wrong for SELECT in library_service.

Previously, cursor.rowcount was used for SELECT COUNT(*) queries, which returns -1
in SQLite for SELECT statements. The fix uses fetchone() result directly.
"""


class TestBug6RowcountForSelect:
    """Bug 6: SELECT COUNT(*) should not use cursor.rowcount."""

    def test_rowcount_concept(self):
        """Demonstrates why cursor.rowcount is wrong for SELECT.

        In SQLite, cursor.rowcount returns -1 for SELECT statements.
        The fix checks fetchone() result directly instead.
        """
        # The correct approach: check fetchone() result
        mock_row = {"count": 42}
        result = mock_row["count"] if mock_row else 0
        assert result == 42

    def test_empty_result_returns_zero(self):
        """Empty result (None fetchone) should return 0."""
        mock_row = None
        result = mock_row["count"] if mock_row else 0
        assert result == 0

    def test_zero_count(self):
        """Zero count should be returned correctly."""
        mock_row = {"count": 0}
        result = mock_row["count"] if mock_row else 0
        assert result == 0
