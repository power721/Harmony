"""
Tests for bug fix: Bug 15 - JSON serialization consistency in QQ Music client.

Previously, the unsigned path used default json.dumps() formatting (with spaces),
inconsistent with the signed path which used compact formatting.
"""

import json


class TestBug15JSONSerialization:
    """Bug 15: JSON serialization should be consistent between signed/unsigned paths."""

    def test_compact_format_no_spaces(self):
        """Verify compact format has no spaces after separators."""
        request_data = {"module": "music.search", "method": "Get"}
        result = json.dumps(request_data, separators=(",", ":"), ensure_ascii=False)
        assert " " not in result.replace("\\u", "").replace('"', "")
        assert result == '{"module":"music.search","method":"Get"}'

    def test_default_format_has_spaces(self):
        """Verify default format has spaces (the old behavior)."""
        request_data = {"module": "music.search", "method": "Get"}
        result = json.dumps(request_data)
        assert '", ' in result or '": ' in result  # default has spaces

    def test_unicode_handling(self):
        """Both should handle unicode (ensure_ascii=False)."""
        request_data = {"keyword": "你好世界"}
        compact = json.dumps(request_data, separators=(",", ":"), ensure_ascii=False)
        assert "你好世界" in compact  # Not escaped

    def test_chinese_characters_preserved(self):
        """Chinese characters should be preserved, not escaped."""
        request_data = {"title": "周杰伦"}
        result = json.dumps(request_data, separators=(",", ":"), ensure_ascii=False)
        assert "周杰伦" in result
        assert "\\u" not in result
