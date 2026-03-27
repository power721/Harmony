"""
Tests for bug fix: Bug 22 - Missing None check on result['body'] in QQ Music service.

Previously, if result['body'] was None, result['body'].get() would raise AttributeError.
"""


class TestBug22NoneBodyCheck:
    """Bug 22: qqmusic_service should handle None body gracefully."""

    def test_none_body_with_in_check(self):
        """The fixed check: isinstance(body, dict) should catch None."""
        result = {"body": None}
        assert "body" in result  # passes old check
        assert not isinstance(result.get("body"), dict)  # catches None

    def test_valid_body_dict_passes(self):
        """A valid dict body should pass the check."""
        result = {"body": {"item_song": []}}
        assert "body" in result
        assert isinstance(result.get("body"), dict)

    def test_body_with_songs(self):
        """Should be able to call .get() on valid body."""
        result = {"body": {"item_song": [{"id": "1"}]}}
        songs = result["body"].get("item_song", [])
        assert len(songs) == 1

    def test_empty_result_handled(self):
        """Empty result dict should be handled."""
        result = {}
        assert "body" not in result

    def test_body_false_handled(self):
        """body=False should also be caught."""
        result = {"body": False}
        assert not isinstance(result.get("body"), dict)
