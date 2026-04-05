"""
Tests for bug fix: Bug 2 - Credential.from_cookies_dict double-pop of musicid.

Previously, str_musicid always got empty string because musicid was already popped.
"""

from services.cloud.qqmusic.qr_login import Credential


class TestBug2DoublePop:
    """Bug 2: from_cookies_dict should not double-pop musicid."""

    def test_str_musicid_present_when_key_exists(self):
        """str_musicid should use the key value when present."""
        cookies = {
            "musicid": "12345",
            "str_musicid": "str_12345",
            "openid": "open_1",
            "musickey": "key_1",
        }
        cred = Credential.from_cookies_dict(cookies)
        assert cred.str_musicid == "str_12345"
        assert cred.musicid == 12345

    def test_str_musicid_fallback_to_musicid(self):
        """str_musicid should fall back to str(musicid) when key is absent."""
        cookies = {
            "musicid": "12345",
            "openid": "open_1",
            "musickey": "key_1",
        }
        cred = Credential.from_cookies_dict(cookies)
        assert cred.str_musicid == "12345"
        assert cred.musicid == 12345

    def test_musicid_zero_when_absent(self):
        """musicid should be 0 and str_musicid fallback to '0' when both absent."""
        cookies = {
            "openid": "open_1",
            "musickey": "key_1",
        }
        cred = Credential.from_cookies_dict(cookies)
        assert cred.musicid == 0
        assert cred.str_musicid == "0"

    def test_musicid_string_coerced_to_int(self):
        """String musicid should be coerced to int."""
        cookies = {
            "musicid": "99999",
            "str_musicid": "str_99999",
            "openid": "open_1",
            "musickey": "key_1",
        }
        cred = Credential.from_cookies_dict(cookies)
        assert cred.musicid == 99999
        assert cred.str_musicid == "str_99999"
