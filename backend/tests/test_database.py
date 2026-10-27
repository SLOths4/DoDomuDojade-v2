import uuid
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, delete
from typer.testing import CliRunner

from app.cli import app as cli_app
from app.core.db import get_sessionmaker
from app.users.models import User
from tests.conftest import ALEMBIC_INI

pytestmark = pytest.mark.db


def test_models_match_migrations(db_engine: Engine) -> None:
    command.check(Config(str(ALEMBIC_INI)))


@pytest.fixture
def cli_username(db_engine: Engine) -> Iterator[str]:
    username = f"cli-{uuid.uuid4().hex[:8]}"
    yield username
    with get_sessionmaker()() as session:
        session.execute(delete(User).where(User.username == username))
        session.commit()


def test_cli_adds_user(cli_username: str) -> None:
    runner = CliRunner()
    args = ["user", "add", cli_username, "--password", "bardzo-tajne"]
    result = runner.invoke(cli_app, args)
    assert result.exit_code == 0, result.output
    assert runner.invoke(cli_app, args).exit_code == 1


def test_cli_rejects_short_password(cli_username: str) -> None:
    result = CliRunner().invoke(cli_app, ["user", "add", cli_username, "--password", "krotkie"])
    assert result.exit_code == 1


def test_cli_cleanup_runs(db_engine: Engine) -> None:
    result = CliRunner().invoke(cli_app, ["cleanup"])
    assert result.exit_code == 0, result.output
    assert "Usunięto" in result.output
