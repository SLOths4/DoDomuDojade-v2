from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from typer.testing import CliRunner

from app.cli import app as cli_app
from app.core.config import get_settings
from app.core.db import get_engine, get_sessionmaker

pytestmark = pytest.mark.db

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


@pytest.fixture
def migrated_db(database_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", database_url)
    for cached in (get_settings, get_engine, get_sessionmaker):
        cached.cache_clear()
    config = Config(str(ALEMBIC_INI))
    command.downgrade(config, "base")
    command.upgrade(config, "head")


def test_models_match_migrations(migrated_db: None) -> None:
    command.check(Config(str(ALEMBIC_INI)))


def test_cli_adds_user(migrated_db: None) -> None:
    runner = CliRunner()
    result = runner.invoke(cli_app, ["user", "add", "admin", "--password", "bardzo-tajne"])
    assert result.exit_code == 0, result.output
    duplicate = runner.invoke(cli_app, ["user", "add", "admin", "--password", "bardzo-tajne"])
    assert duplicate.exit_code == 1


def test_cli_rejects_short_password(migrated_db: None) -> None:
    result = CliRunner().invoke(cli_app, ["user", "add", "ktos", "--password", "krotkie"])
    assert result.exit_code == 1
