import pytest

from utils.normalization import normalize_online_provider_id


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        (None, None),
        ("", None),
        ("  ", None),
        ("online", None),
        (" Online ", None),
        ("qqmusic", "qqmusic"),
        (" qqmusic ", "qqmusic"),
        (123, "123"),
    ],
)
def test_normalize_online_provider_id(raw_value, expected):
    assert normalize_online_provider_id(raw_value) == expected
