"""
QQ Music common utilities and constants.
"""

import random
import time
from enum import Enum
from typing import Dict


class SongFileType:
    """Song file type mappings for different quality levels."""

    MASTER = {'s': 'AI00', 'e': '.flac'}
    ATMOS_2 = {'s': 'Q000', 'e': '.flac'}
    ATMOS_51 = {'s': 'Q001', 'e': '.flac'}
    FLAC = {'s': 'F000', 'e': '.flac'}
    MP3_320 = {'s': 'M800', 'e': '.mp3'}
    MP3_128 = {'s': 'M500', 'e': '.mp3'}
    OGG_192 = {'s': 'O600', 'e': '.ogg'}
    OGG_96 = {'s': 'O400', 'e': '.ogg'}
    AAC_192 = {'s': 'C600', 'e': '.m4a'}
    AAC_96 = {'s': 'C400', 'e': '.m4a'}
    AAC_48 = {'s': 'C200', 'e': '.m4a'}


class SearchType(Enum):
    """Search type enumeration."""

    SONG = 0
    SINGER = 1
    ALBUM = 2
    PLAYLIST = 3
    MV = 4
    LYRIC = 7
    USER = 8


class APIConfig:
    """QQ Music API configuration."""

    VERSION = "13.2.5.8"
    VERSION_CODE = 13020508
    # Use musicu.fcg endpoint (no sign required for most APIs)
    ENDPOINT = "https://u.y.qq.com/cgi-bin/musicu.fcg"
    # Signed endpoint for specific APIs
    ENDPOINT_SIGNED = "https://u.y.qq.com/cgi-bin/musics.fcg"

    # Quality fallback order
    QUALITY_FALLBACK = ["master", "atmos_2", "atmos_51", "flac", "320", "128"]


def get_guid() -> str:
    """
    Generate random 32-character GUID.

    Returns:
        Random GUID string
    """
    chars = "abcdef1234567890"
    return ''.join(random.choice(chars) for _ in range(32))


def get_search_id() -> str:
    """
    Generate search ID.

    Returns:
        Search ID string
    """
    e = random.randint(1, 20)
    t = e * 18014398509481984
    n = random.randint(0, 4194303) * 4294967296
    r = int(time.time() * 1000) % (24 * 60 * 60 * 1000)
    return str(t + n + r)


def parse_search_type(type_str: str) -> SearchType:
    """
    Parse search type string to enum.

    Args:
        type_str: Search type string

    Returns:
        SearchType enum value
    """
    type_map = {
        'song': SearchType.SONG,
        'singer': SearchType.SINGER,
        'album': SearchType.ALBUM,
        'playlist': SearchType.PLAYLIST,
        'mv': SearchType.MV,
        'lyric': SearchType.LYRIC,
        'user': SearchType.USER,
    }
    return type_map.get(type_str.lower() if type_str else '', SearchType.SONG)


def parse_quality(quality: str) -> Dict[str, str]:
    """
    Parse quality string to file type mapping.

    Args:
        quality: Quality string (e.g., 'flac', '320', 'master')

    Returns:
        Dictionary with 's' (prefix) and 'e' (extension) keys
    """
    quality_map = {
        'master': SongFileType.MASTER,
        'atmos_2': SongFileType.ATMOS_2,
        'atmos': SongFileType.ATMOS_2,
        'atmos_51': SongFileType.ATMOS_51,
        'flac': SongFileType.FLAC,
        '320': SongFileType.MP3_320,
        '128': SongFileType.MP3_128,
        '192': SongFileType.OGG_192,
        '96': SongFileType.OGG_96,
    }
    return quality_map.get(str(quality).lower(), SongFileType.MP3_128)
