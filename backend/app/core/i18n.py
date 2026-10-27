import json
from functools import cache
from pathlib import Path
from typing import Literal, cast

Locale = Literal["pl", "en"]
LOCALES: tuple[Locale, ...] = ("pl", "en")
DEFAULT_LOCALE: Locale = "pl"

_LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"


@cache
def _messages(locale: Locale) -> dict[str, str]:
    data = json.loads((_LOCALES_DIR / f"{locale}.json").read_text(encoding="utf-8"))
    return cast(dict[str, str], data)


def translate(key: str, locale: Locale = DEFAULT_LOCALE, **params: object) -> str:
    template = _messages(locale).get(key) or _messages(DEFAULT_LOCALE).get(key) or key
    try:
        return template.format(**params)
    except (KeyError, IndexError):
        return template


def locale_from_header(accept_language: str | None) -> Locale:
    """Pick the first supported language from an Accept-Language header."""
    if not accept_language:
        return DEFAULT_LOCALE
    weighted: list[tuple[float, str]] = []
    for part in accept_language.split(","):
        lang, _, q = part.strip().partition(";q=")
        try:
            weight = float(q) if q else 1.0
        except ValueError:
            weight = 0.0
        weighted.append((weight, lang[:2].lower()))
    for _, lang in sorted(weighted, key=lambda item: -item[0]):
        if lang in LOCALES:
            return lang
    return DEFAULT_LOCALE
