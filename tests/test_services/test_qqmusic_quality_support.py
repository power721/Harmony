from services.cloud.qqmusic.client import QQMusicClient
from services.cloud.qqmusic.common import (
    APIConfig,
    parse_quality,
    get_selectable_qualities,
    get_quality_label_key,
)


def test_parse_quality_supports_more_codes():
    assert parse_quality("ogg_640") == {"s": "O801", "e": ".ogg"}
    assert parse_quality("aac_320") == {"s": "C800", "e": ".m4a"}
    assert parse_quality("aac_256") == {"s": "C700", "e": ".m4a"}
    assert parse_quality("aac_128") == {"s": "C500", "e": ".m4a"}
    assert parse_quality("aac_64") == {"s": "C300", "e": ".m4a"}
    assert parse_quality("aac_24") == {"s": "C100", "e": ".m4a"}
    assert parse_quality("ape") == {"s": "A000", "e": ".ape"}
    assert parse_quality("dts") == {"s": "D000", "e": ".dts"}
    assert parse_quality("dolby") == {"s": "RS01", "e": ".flac"}
    assert parse_quality("hires") == {"s": "SQ00", "e": ".flac"}


def test_parse_quality_supports_chinese_quality_names():
    assert parse_quality("标准") == {"s": "M500", "e": ".mp3"}
    assert parse_quality("HQ高品质") == {"s": "M800", "e": ".mp3"}
    assert parse_quality("SQ无损品质") == {"s": "F000", "e": ".flac"}
    assert parse_quality("臻品母带3.0") == {"s": "AI00", "e": ".flac"}
    assert parse_quality("臻品全景声2.0") == {"s": "Q000", "e": ".flac"}
    assert parse_quality("臻品音质2.0") == {"s": "Q001", "e": ".flac"}
    assert parse_quality("OGG高品质") == {"s": "O800", "e": ".ogg"}
    assert parse_quality("OGG标准") == {"s": "O600", "e": ".ogg"}
    assert parse_quality("AAC高品质") == {"s": "C600", "e": ".m4a"}
    assert parse_quality("AAC标准") == {"s": "C400", "e": ".m4a"}


def test_quality_fallback_contains_extended_quality_levels():
    assert "ogg_640" in APIConfig.QUALITY_FALLBACK
    assert "aac_320" in APIConfig.QUALITY_FALLBACK
    assert "aac_24" in APIConfig.QUALITY_FALLBACK
    assert "hires" in APIConfig.QUALITY_FALLBACK
    assert "dolby" in APIConfig.QUALITY_FALLBACK


def test_get_song_url_accepts_chinese_quality_name():
    client = QQMusicClient()
    captured = {"filename": None}

    def fake_make_request(module, method, params, _retry=False, use_sign=False):
        captured["filename"] = params["filename"][0]
        return {"midurlinfo": [{"songmid": "abc", "purl": "abc.mp3"}]}

    client._make_request = fake_make_request

    result = client.get_song_url("abc", quality="HQ高品质")

    assert result["quality"] == "320"
    assert result["file_type"] == {"s": "M800", "e": ".mp3"}
    assert result["extension"] == ".mp3"
    assert captured["filename"].startswith("M800")


def test_get_song_url_returns_file_type_for_fallback_quality():
    client = QQMusicClient()

    def fake_make_request(module, method, params, _retry=False, use_sign=False):
        requested = params["filename"][0]
        if requested.startswith("O800"):
            return {"midurlinfo": [{"songmid": "abc", "purl": "abc.ogg"}]}
        return {"midurlinfo": [{"songmid": "abc", "purl": ""}]}

    client._make_request = fake_make_request

    result = client.get_song_url("abc", quality="hires")

    assert result["quality"] == "ogg_320"
    assert result["file_type"] == {"s": "O800", "e": ".ogg"}
    assert result["extension"] == ".ogg"


def test_selectable_quality_list_includes_extended_levels():
    qualities = get_selectable_qualities()
    assert "master" in qualities
    assert "atmos_2" in qualities
    assert "atmos_51" in qualities
    assert "flac" in qualities
    assert "320" in qualities
    assert "128" in qualities
    assert "ogg_320" in qualities
    assert "aac_192" in qualities
    assert "dolby" in qualities
    assert "hires" in qualities


def test_quality_label_keys_exist_for_extended_levels():
    assert get_quality_label_key("master") == "qqmusic_quality_master"
    assert get_quality_label_key("atmos_2") == "qqmusic_quality_atmos_2"
    assert get_quality_label_key("atmos_51") == "qqmusic_quality_atmos_51"
    assert get_quality_label_key("ogg_320") == "qqmusic_quality_ogg_320"
    assert get_quality_label_key("aac_192") == "qqmusic_quality_aac_192"
    assert get_quality_label_key("dolby") == "qqmusic_quality_dolby"
    assert get_quality_label_key("hires") == "qqmusic_quality_hires"
