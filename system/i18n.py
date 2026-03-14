"""
Internationalization (i18n) module for the music player.
Supports English and Chinese languages.
"""

import json
from pathlib import Path
from typing import Dict, Optional

_current_language: str = "en"
_translations: Dict[str, Dict[str, str]] = {}


def _get_translations_dir() -> Path:
    """Get the translations directory."""
    return Path(__file__).parent.parent / "translations"


def load_translations():
    """Load all translation files."""
    global _translations

    translations_dir = _get_translations_dir()
    translations_dir.mkdir(exist_ok=True)

    # Load English
    en_file = translations_dir / "en.json"
    if en_file.exists():
        with open(en_file, "r", encoding="utf-8") as f:
            _translations["en"] = json.load(f)
    else:
        _translations["en"] = {}

    # Load Chinese
    zh_file = translations_dir / "zh.json"
    if zh_file.exists():
        with open(zh_file, "r", encoding="utf-8") as f:
            _translations["zh"] = json.load(f)
    else:
        _translations["zh"] = {}


def set_language(lang: str):
    """Set the current language."""
    global _current_language
    if lang in ("en", "zh"):
        _current_language = lang
    else:
        _current_language = "en"


def get_language() -> str:
    """Get the current language."""
    return _current_language


def t(key: str, default: Optional[str] = None) -> str:
    """
    Translate a key to the current language.

    Args:
        key: The translation key
        default: Default text if key not found

    Returns:
        Translated text or default/key if not found
    """
    if _current_language not in _translations:
        return default if default is not None else key

    translations = _translations[_current_language]

    if key in translations:
        return translations[key]

    # Fallback to English if key not in current language
    if _current_language != "en" and "en" in _translations:
        if key in _translations["en"]:
            return _translations["en"][key]

    return default if default is not None else key


def get_available_languages() -> list:
    """Get list of available languages."""
    return [
        ("en", "English"),
        ("zh", "中文"),
    ]


# Initialize translations on module import
load_translations()
