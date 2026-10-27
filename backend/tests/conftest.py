import os

os.environ["SCHEDULER_ENABLED"] = "false"

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core import rate_limit
from app.core.config import get_settings
from app.core.db import get_db, get_engine, get_sessionmaker
from app.core.security import hash_password
from app.main import create_app
from app.users.models import Role, User

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"
PASSWORD = "haslo-testowe-123"


class ApiClient(TestClient):
    """Test client that echoes the CSRF cookie back in the header, like the frontend does."""

    def request(self, method: str, url: httpx._types.URLTypes, **kwargs: Any) -> httpx.Response:  # type: ignore[override]
        token = self.cookies.get("csrf_token")
        if token and method.upper() not in {"GET", "HEAD", "OPTIONS"}:
            headers = dict(kwargs.pop("headers", None) or {})
            headers.setdefault("X-CSRF-Token", token)
            kwargs["headers"] = headers
        return super().request(method, url, **kwargs)


@pytest.fixture(autouse=True)
def _reset_rate_limits() -> None:
    rate_limit.login_failures.reset()
    rate_limit.proposals.reset()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(), raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL nie jest ustawione")
    return url


@pytest.fixture(scope="session")
def db_engine() -> Engine:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL nie jest ustawione")
    os.environ["DATABASE_URL"] = url
    for cached in (get_settings, get_engine, get_sessionmaker):
        cached.cache_clear()
    config = Config(str(ALEMBIC_INI))
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    return get_engine()


@pytest.fixture
def db(db_engine: Engine) -> Iterator[Session]:
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def app(db: Session) -> FastAPI:
    application = create_app()
    application.dependency_overrides[get_db] = lambda: db
    return application


@pytest.fixture
def make_user(db: Session) -> Callable[..., User]:
    def make(
        username: str,
        role: Role = Role.MODERATOR,
        must_change_password: bool = False,
        is_active: bool = True,
    ) -> User:
        user = User(
            username=username,
            password_hash=hash_password(PASSWORD),
            role=role,
            must_change_password=must_change_password,
            is_active=is_active,
        )
        db.add(user)
        db.commit()
        return user

    return make


@pytest.fixture
def api(app: FastAPI) -> Iterator[ApiClient]:
    with ApiClient(app, raise_server_exceptions=False) as test_client:
        test_client.get("/api/config")
        yield test_client


def login(client: ApiClient, username: str, password: str = PASSWORD) -> httpx.Response:
    return client.post("/api/auth/login", json={"username": username, "password": password})


@pytest.fixture
def admin(make_user: Callable[..., User]) -> User:
    return make_user("admin", Role.ADMIN)


@pytest.fixture
def admin_api(api: ApiClient, admin: User) -> ApiClient:
    assert login(api, admin.username).status_code == 200
    return api


@pytest.fixture
def moderator_api(api: ApiClient, make_user: Callable[..., User]) -> ApiClient:
    user = make_user("moderator", Role.MODERATOR)
    assert login(api, user.username).status_code == 200
    return api


@pytest.fixture
def app_factory_client(app: FastAPI) -> Iterator[Callable[[], ApiClient]]:
    """Several independent browsers (separate cookie jars) talking to the same app."""
    clients: list[ApiClient] = []

    def make() -> ApiClient:
        new_client = ApiClient(app, raise_server_exceptions=False)
        new_client.__enter__()
        new_client.get("/api/config")
        clients.append(new_client)
        return new_client

    yield make
    for opened in clients:
        opened.__exit__(None, None, None)
