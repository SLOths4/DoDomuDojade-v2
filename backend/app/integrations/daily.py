"""Quote and word of the day from Wikimedia projects, alternating Polish and English by day."""

import json
import logging
import re
from dataclasses import dataclass
from datetime import date
from functools import cache
from pathlib import Path
from typing import Any

import mwparserfromhell
from mwparserfromhell.wikicode import Wikicode
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.http import http_client
from app.display.models import Quote, Word

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "display" / "data"
EN_MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]
PL_MONTHS_GENITIVE = [
    "stycznia",
    "lutego",
    "marca",
    "kwietnia",
    "maja",
    "czerwca",
    "lipca",
    "sierpnia",
    "września",
    "października",
    "listopada",
    "grudnia",
]


@dataclass(frozen=True)
class DailyQuote:
    text: str
    author: str
    source: str


@dataclass(frozen=True)
class DailyWord:
    word: str
    ipa: str | None
    definition: str
    source: str


def language_for(day: date) -> str:
    return "pl" if day.toordinal() % 2 == 0 else "en"


def _plain(code: str | Wikicode) -> str:
    wikicode = mwparserfromhell.parse(str(code))
    for template in wikicode.filter_templates(recursive=False):
        name = str(template.name).strip().lower()
        if name == "cap" and template.has(1):
            wikicode.replace(template, str(template.get(1).value).strip().capitalize())
        elif name in {"l", "m"} and template.has(2):
            wikicode.replace(template, str(template.get(2).value).strip())
    text = wikicode.strip_code(normalize=True, collapse=True)
    return re.sub(r"\s+", " ", text).strip(" ;")


def parse_wikicytaty(raw: str) -> DailyQuote | None:
    text = re.search(r"'''''(.+?)'''''", raw, re.S)
    author = re.search(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", raw.split("|-", 1)[-1])
    if not text or not author:
        return None
    return DailyQuote(
        text=_plain(text.group(1).replace("<br />", " ").replace("<br>", " ")),
        author=(author.group(2) or author.group(1)).strip(),
        source="Wikicytaty",
    )


def _template_params(raw: str, name_prefix: str) -> dict[str, str] | None:
    for template in mwparserfromhell.parse(raw).filter_templates(recursive=False):
        if str(template.name).strip().startswith(name_prefix):
            return {str(p.name).strip(): str(p.value).strip() for p in template.params}
    return None


def parse_wikiquote(raw: str) -> DailyQuote | None:
    params = _template_params(raw, "Wikiquote:Quote of the day")
    if not params or not params.get("quote") or not params.get("author"):
        return None
    return DailyQuote(
        text=_plain(params["quote"]), author=_plain(params["author"]), source="Wikiquote"
    )


def parse_wikislownik(raw: str) -> DailyWord | None:
    params = _template_params(raw, "Słowo dnia")
    if not params or not params.get("hasło"):
        return None
    meaning = re.search(r"\(1\.1\)(.+)", params.get("znaczenie", ""))
    if not meaning:
        return None
    definition = mwparserfromhell.parse(meaning.group(1))
    for template in definition.filter_templates(recursive=False):
        definition.remove(template)  # register labels such as {{książk}}
    ipa = re.search(r"\{\{IPA\d?\|([^}|]+)", params.get("wymowa", ""))
    return DailyWord(
        word=params["hasło"],
        ipa=f"/{ipa.group(1).strip()}/" if ipa else None,
        definition=_plain(definition),
        source="Wikisłownik",
    )


def parse_wiktionary(raw: str) -> DailyWord | None:
    for template in mwparserfromhell.parse(raw).filter_templates(recursive=False):
        if str(template.name).strip() == "WOTD" and template.has(3):
            first_sense = str(template.get(3).value).split("\n#")[0]
            return DailyWord(
                word=str(template.get(1).value).strip(),
                ipa=None,
                definition=_plain(first_sense),
                source="Wiktionary",
            )
    return None


def _raw_page(host: str, title: str) -> str:
    response = http_client().get(
        f"https://{host}/w/index.php", params={"title": title, "action": "raw"}
    )
    response.raise_for_status()
    return response.text


def _english_ipa(word: str) -> str | None:
    try:
        response = http_client().get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}")
        if response.status_code != 200:
            return None
        entry = response.json()[0]
        phonetic = entry.get("phonetic") or next(
            (p["text"] for p in entry.get("phonetics", []) if p.get("text")), None
        )
        return str(phonetic) if phonetic else None
    except Exception:
        logger.warning("No pronunciation for %s", word)
        return None


def fetch_quote(day: date, language: str) -> DailyQuote | None:
    if language == "pl":
        title = f"Szablon:Cytat_dnia/{day.day}_{PL_MONTHS_GENITIVE[day.month - 1]}"
        return parse_wikicytaty(_raw_page("pl.wikiquote.org", title))
    title = f"Wikiquote:Quote_of_the_day/{EN_MONTHS[day.month - 1]}_{day.day},_{day.year}"
    return parse_wikiquote(_raw_page("en.wikiquote.org", title))


def fetch_word(day: date, language: str) -> DailyWord | None:
    if language == "pl":
        title = f"Wikisłownik:Słowo_dnia/Rozkład/{day:%Y/%m/%d}"
        return parse_wikislownik(_raw_page("pl.wiktionary.org", title))
    title = f"Wiktionary:Word_of_the_day/{day.year}/{EN_MONTHS[day.month - 1]}_{day.day}"
    word = parse_wiktionary(_raw_page("en.wiktionary.org", title))
    if word is not None and " " not in word.word:
        word = DailyWord(word.word, _english_ipa(word.word), word.definition, word.source)
    return word


@cache
def _fallback(kind: str, language: str) -> list[dict[str, Any]]:
    data = json.loads((DATA_DIR / f"{kind}_{language}.json").read_text(encoding="utf-8"))
    return list(data)


def fallback_quote(day: date, language: str) -> DailyQuote:
    items = _fallback("quotes", language)
    item = items[day.toordinal() % len(items)]
    return DailyQuote(item["text"], item["author"], "lokalna lista")


def fallback_word(day: date, language: str) -> DailyWord:
    items = _fallback("words", language)
    item = items[day.toordinal() % len(items)]
    return DailyWord(item["word"], item.get("ipa"), item["definition"], "lokalna lista")


def ensure_daily(db: Session, day: date) -> bool:
    """Store today's quote and word if missing; returns True when something was added."""
    language = language_for(day)
    added = False
    if db.scalar(select(Quote).where(Quote.day == day)) is None:
        try:
            quote = fetch_quote(day, language) or fallback_quote(day, language)
        except Exception:
            logger.exception("Quote of the day unavailable; using the local list")
            quote = fallback_quote(day, language)
        db.add(
            Quote(
                day=day,
                language=language,
                text=quote.text,
                author=quote.author,
                source=quote.source,
            )
        )
        added = True
    if db.scalar(select(Word).where(Word.day == day)) is None:
        try:
            word = fetch_word(day, language) or fallback_word(day, language)
        except Exception:
            logger.exception("Word of the day unavailable; using the local list")
            word = fallback_word(day, language)
        db.add(
            Word(
                day=day,
                language=language,
                word=word.word,
                ipa=word.ipa,
                definition=word.definition,
                source=word.source,
            )
        )
        added = True
    db.commit()
    return added
