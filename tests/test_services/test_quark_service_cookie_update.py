"""QuarkDriveService cookie update behavior tests."""

from services.cloud.quark_service import QuarkDriveService


def test_update_cookie_from_response_replaces_puus():
    """Response __puus should override existing cookie value."""
    original = "__puus=old; sid=abc"
    updated = QuarkDriveService._update_cookie_from_response(
        original,
        {"__puus": "new"},
    )

    assert "__puus=new" in updated
    assert "sid=abc" in updated


def test_update_cookie_from_response_keeps_cookie_when_missing_puus():
    """Without __puus response cookie should remain unchanged."""
    original = "__puus=old; sid=abc"
    updated = QuarkDriveService._update_cookie_from_response(
        original,
        {"sid": "xyz"},
    )

    assert updated == original
