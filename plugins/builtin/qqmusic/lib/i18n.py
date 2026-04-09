from __future__ import annotations

import json
import logging
from pathlib import Path

_current_language = "en"
_translations: dict[str, dict[str, str]] = {}


def _translations_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "translations"


def load_translations() -> None:
    global _translations

    directory = _translations_dir()
    for lang in ("en", "zh"):
        path = directory / f"{lang}.json"
        if not path.exists():
            _translations[lang] = {}
            continue
        try:
            _translations[lang] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logging.warning("Failed to load QQ Music plugin translations for %s: %s", lang, exc)
            _translations[lang] = {}


def set_language(lang: str) -> None:
    global _current_language
    _current_language = lang if lang in ("en", "zh") else "en"


def get_language() -> str:
    return _current_language


def t(key: str, default: str | None = None) -> str:
    translations = _translations.get(_current_language, {})
    if key in translations:
        return translations[key]
    if _current_language != "en":
        fallback = _translations.get("en", {})
        if key in fallback:
            return fallback[key]
    return default if default is not None else key


load_translations()
