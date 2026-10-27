from pathlib import Path
from typing import Annotated

import typer
from alembic import command
from alembic.config import Config
from sqlalchemy import select

from app.core.db import get_sessionmaker
from app.core.security import MIN_PASSWORD_LENGTH, hash_password
from app.maintenance import cleanup as cleanup_db
from app.users.models import Role, User

app = typer.Typer(help="DoDomuDojadę: polecenia administracyjne.", no_args_is_help=True)
user_app = typer.Typer(help="Użytkownicy.", no_args_is_help=True)
app.add_typer(user_app, name="user")

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


@app.command()
def migrate() -> None:
    """Aktualizuje schemat bazy do najnowszej wersji."""
    command.upgrade(Config(str(ALEMBIC_INI)), "head")


@app.command()
def cleanup() -> None:
    """Usuwa stare odrzucone ogłoszenia i stare wpisy dziennika zdarzeń."""
    with get_sessionmaker()() as session:
        result = cleanup_db(session)
    typer.echo(
        f"Usunięto odrzucone ogłoszenia: {result['rejected_announcements']}, "
        f"zdarzenia: {result['events']}."
    )


@user_app.command("add")
def user_add(
    username: str,
    role: Annotated[Role, typer.Option(help="Rola użytkownika.")] = Role.ADMIN,
    password: Annotated[
        str, typer.Option(prompt=True, confirmation_prompt=True, hide_input=True)
    ] = "",
) -> None:
    """Dodaje użytkownika."""
    username = username.strip()
    if not username:
        typer.echo("Login nie może być pusty.", err=True)
        raise typer.Exit(1)
    if len(password) < MIN_PASSWORD_LENGTH:
        typer.echo(f"Hasło musi mieć co najmniej {MIN_PASSWORD_LENGTH} znaków.", err=True)
        raise typer.Exit(1)
    with get_sessionmaker()() as session:
        if session.scalar(select(User).where(User.username == username)):
            typer.echo(f"Użytkownik {username} już istnieje.", err=True)
            raise typer.Exit(1)
        session.add(User(username=username, password_hash=hash_password(password), role=role))
        session.commit()
    typer.echo(f"Dodano użytkownika {username} ({role.value}).")


if __name__ == "__main__":
    app()
