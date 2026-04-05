"""Shared online-audio quality utilities used by host code and plugins."""

from __future__ import annotations

from typing import Dict


class SongFileType:
    MASTER = {"s": "AI00", "e": ".flac"}
    ATMOS_2 = {"s": "Q000", "e": ".flac"}
    ATMOS_51 = {"s": "Q001", "e": ".flac"}
    DOLBY = {"s": "RS01", "e": ".flac"}
    HIRES = {"s": "SQ00", "e": ".flac"}
    FLAC = {"s": "F000", "e": ".flac"}
    APE = {"s": "A000", "e": ".ape"}
    DTS = {"s": "D000", "e": ".dts"}
    MP3_320 = {"s": "M800", "e": ".mp3"}
    MP3_128 = {"s": "M500", "e": ".mp3"}
    OGG_640 = {"s": "O801", "e": ".ogg"}
    OGG_320 = {"s": "O800", "e": ".ogg"}
    OGG_192 = {"s": "O600", "e": ".ogg"}
    OGG_96 = {"s": "O400", "e": ".ogg"}
    AAC_320 = {"s": "C800", "e": ".m4a"}
    AAC_256 = {"s": "C700", "e": ".m4a"}
    AAC_192 = {"s": "C600", "e": ".m4a"}
    AAC_128 = {"s": "C500", "e": ".m4a"}
    AAC_96 = {"s": "C400", "e": ".m4a"}
    AAC_64 = {"s": "C300", "e": ".m4a"}
    AAC_48 = {"s": "C200", "e": ".m4a"}
    AAC_24 = {"s": "C100", "e": ".m4a"}


QUALITY_FALLBACK = [
    "master",
    "atmos_2",
    "atmos_51",
    "dolby",
    "hires",
    "flac",
    "ape",
    "dts",
    "ogg_640",
    "320",
    "ogg_320",
    "aac_320",
    "aac_256",
    "aac_192",
    "ogg_192",
    "128",
    "aac_128",
    "aac_96",
    "ogg_96",
    "aac_64",
    "aac_48",
    "aac_24",
]

_QUALITY_ALIASES = {
    "atmos": "atmos_2",
    "192": "ogg_192",
    "96": "ogg_96",
    "标准": "128",
    "hq高品质": "320",
    "sq无损品质": "flac",
    "臻品母带3.0": "master",
    "臻品全景声2.0": "atmos_2",
    "臻品音质2.0": "atmos_51",
    "ogg高品质": "ogg_320",
    "ogg标准": "ogg_192",
    "aac高品质": "aac_192",
    "aac标准": "aac_96",
}

_QUALITY_FILE_MAP = {
    "master": SongFileType.MASTER,
    "atmos_2": SongFileType.ATMOS_2,
    "atmos_51": SongFileType.ATMOS_51,
    "dolby": SongFileType.DOLBY,
    "hires": SongFileType.HIRES,
    "flac": SongFileType.FLAC,
    "ape": SongFileType.APE,
    "dts": SongFileType.DTS,
    "320": SongFileType.MP3_320,
    "128": SongFileType.MP3_128,
    "ogg_640": SongFileType.OGG_640,
    "ogg_320": SongFileType.OGG_320,
    "ogg_192": SongFileType.OGG_192,
    "ogg_96": SongFileType.OGG_96,
    "aac_320": SongFileType.AAC_320,
    "aac_256": SongFileType.AAC_256,
    "aac_192": SongFileType.AAC_192,
    "aac_128": SongFileType.AAC_128,
    "aac_96": SongFileType.AAC_96,
    "aac_64": SongFileType.AAC_64,
    "aac_48": SongFileType.AAC_48,
    "aac_24": SongFileType.AAC_24,
}

_QUALITY_LABEL_KEYS = {
    "master": "qqmusic_quality_master",
    "atmos_2": "qqmusic_quality_atmos_2",
    "atmos_51": "qqmusic_quality_atmos_51",
    "dolby": "qqmusic_quality_dolby",
    "hires": "qqmusic_quality_hires",
    "flac": "qqmusic_quality_flac",
    "ape": "qqmusic_quality_ape",
    "dts": "qqmusic_quality_dts",
    "ogg_640": "qqmusic_quality_ogg_640",
    "320": "qqmusic_quality_320",
    "ogg_320": "qqmusic_quality_ogg_320",
    "aac_320": "qqmusic_quality_aac_320",
    "aac_256": "qqmusic_quality_aac_256",
    "aac_192": "qqmusic_quality_aac_192",
    "ogg_192": "qqmusic_quality_ogg_192",
    "128": "qqmusic_quality_128",
    "aac_128": "qqmusic_quality_aac_128",
    "aac_96": "qqmusic_quality_aac_96",
    "ogg_96": "qqmusic_quality_ogg_96",
    "aac_64": "qqmusic_quality_aac_64",
    "aac_48": "qqmusic_quality_aac_48",
    "aac_24": "qqmusic_quality_aac_24",
}


def normalize_quality(quality: str) -> str:
    value = str(quality or "").strip().lower()
    return _QUALITY_ALIASES.get(value, value)


def parse_quality(quality: str) -> Dict[str, str]:
    normalized = normalize_quality(quality)
    return _QUALITY_FILE_MAP.get(normalized, SongFileType.MP3_128)


def get_selectable_qualities() -> list[str]:
    return list(QUALITY_FALLBACK)


def get_quality_label_key(quality: str) -> str:
    normalized = normalize_quality(quality)
    return _QUALITY_LABEL_KEYS.get(normalized, "")
