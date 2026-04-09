from plugins.builtin.qqmusic.lib.common import get_quality_label_key, parse_quality


def test_parse_quality_and_label_lookup_work_in_shared_module():
    assert parse_quality("flac") == {"s": "F000", "e": ".flac"}
    assert get_quality_label_key("ogg_320") == "qqmusic_quality_ogg_320"
