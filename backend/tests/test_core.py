import json
from pathlib import Path

from app.core.i18n import locale_from_header, translate
from app.core.security import hash_password, verify_password

LOCALES = Path(__file__).resolve().parent.parent / "app" / "locales"


def test_password_roundtrip() -> None:
    password_hash = hash_password("tajne-haslo")
    assert verify_password("tajne-haslo", password_hash)
    assert not verify_password("inne-haslo", password_hash)


def test_verify_password_rejects_malformed_hash() -> None:
    assert not verify_password("cokolwiek", "not-a-bcrypt-hash")


def test_locale_from_header() -> None:
    assert locale_from_header(None) == "pl"
    assert locale_from_header("en-US,en;q=0.9,pl;q=0.8") == "en"
    assert locale_from_header("de-DE,pl;q=0.5") == "pl"
    assert locale_from_header("fr") == "pl"


def test_translate_falls_back_to_polish_then_key() -> None:
    assert translate("errors.NOT_FOUND", "en") == "Not found."
    assert translate("missing.key", "en") == "missing.key"


def test_locales_have_the_same_keys() -> None:
    pl = json.loads((LOCALES / "pl.json").read_text(encoding="utf-8"))
    en = json.loads((LOCALES / "en.json").read_text(encoding="utf-8"))
    assert pl.keys() == en.keys()
