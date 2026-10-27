from collections.abc import Callable

import pytest

from app.users.models import Role, User
from tests.conftest import PASSWORD, ApiClient, login

pytestmark = pytest.mark.db


def test_login_returns_profile_and_me_works(api: ApiClient, admin: User) -> None:
    response = login(api, "admin")
    assert response.status_code == 200
    assert response.json()["username"] == "admin"
    assert response.json()["mustChangePassword"] is False
    assert api.get("/api/auth/me").json()["role"] == "admin"


def test_me_without_session_is_401(api: ApiClient) -> None:
    response = api.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["data"]["code"] == "UNAUTHENTICATED"


def test_wrong_password_and_unknown_user_look_the_same(api: ApiClient, admin: User) -> None:
    wrong = login(api, "admin", "zle-haslo-123")
    unknown = login(api, "nikt", "zle-haslo-123")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["data"]["code"] == unknown.json()["data"]["code"] == "INVALID_CREDENTIALS"


def test_inactive_user_cannot_log_in(api: ApiClient, make_user: Callable[..., User]) -> None:
    make_user("byly", is_active=False)
    assert login(api, "byly").status_code == 401


def test_login_is_rate_limited_after_five_failures(api: ApiClient, admin: User) -> None:
    for _ in range(5):
        assert login(api, "admin", "zle-haslo-123").status_code == 401
    blocked = login(api, "admin")
    assert blocked.status_code == 429
    assert blocked.json()["data"]["code"] == "TOO_MANY_ATTEMPTS"


def test_login_rotates_csrf_token(api: ApiClient, admin: User) -> None:
    before = api.cookies.get("csrf_token")
    login(api, "admin")
    assert api.cookies.get("csrf_token") != before


def test_logout_ends_session(admin_api: ApiClient) -> None:
    assert admin_api.post("/api/auth/logout").status_code == 204
    assert admin_api.get("/api/auth/me").status_code == 401


def test_forced_password_change_blocks_everything_else(
    api: ApiClient, make_user: Callable[..., User]
) -> None:
    make_user("nowy", Role.ADMIN, must_change_password=True)
    login(api, "nowy")
    assert api.get("/api/auth/me").status_code == 200
    blocked = api.get("/api/users")
    assert blocked.status_code == 403
    assert blocked.json()["data"]["code"] == "PASSWORD_CHANGE_REQUIRED"
    assert api.get("/api/announcements").status_code == 403

    changed = api.post(
        "/api/auth/password",
        json={"currentPassword": PASSWORD, "newPassword": "zupelnie-nowe-haslo"},
    )
    assert changed.status_code == 204
    assert api.get("/api/users").status_code == 200


def test_password_change_validates_current_and_new(admin_api: ApiClient) -> None:
    wrong = admin_api.post(
        "/api/auth/password", json={"currentPassword": "zle", "newPassword": "inne-haslo-123"}
    )
    assert wrong.json()["data"]["code"] == "INVALID_PASSWORD"
    same = admin_api.post(
        "/api/auth/password", json={"currentPassword": PASSWORD, "newPassword": PASSWORD}
    )
    assert same.json()["data"]["code"] == "PASSWORD_UNCHANGED"
    short = admin_api.post(
        "/api/auth/password", json={"currentPassword": PASSWORD, "newPassword": "krotkie"}
    )
    assert short.status_code == 400
    assert short.json()["data"]["context"]["fields"] == {"newPassword": "string_too_short"}


def test_password_change_invalidates_other_sessions(
    app_factory_client: Callable[[], ApiClient], admin: User
) -> None:
    first, second = app_factory_client(), app_factory_client()
    login(first, "admin")
    login(second, "admin")
    first.post(
        "/api/auth/password",
        json={"currentPassword": PASSWORD, "newPassword": "zupelnie-nowe-haslo"},
    )
    assert first.get("/api/auth/me").status_code == 200
    assert second.get("/api/auth/me").status_code == 401


def test_profile_locale_can_be_changed(admin_api: ApiClient) -> None:
    response = admin_api.patch("/api/auth/me", json={"locale": "en"})
    assert response.json()["locale"] == "en"
    assert admin_api.patch("/api/auth/me", json={"locale": "de"}).status_code == 400


def test_can_log_in_again_after_session_was_invalidated(
    app_factory_client: Callable[[], ApiClient], admin: User
) -> None:
    first, second = app_factory_client(), app_factory_client()
    login(first, "admin")
    login(second, "admin")
    first.post(
        "/api/auth/password",
        json={"currentPassword": PASSWORD, "newPassword": "zupelnie-nowe-haslo"},
    )
    assert second.get("/api/auth/me").status_code == 401
    assert login(second, "admin", "zupelnie-nowe-haslo").status_code == 200


def test_timestamps_use_the_school_timezone(admin_api: ApiClient) -> None:
    created_at = admin_api.get("/api/auth/me").json()["createdAt"]
    assert created_at.endswith(("+01:00", "+02:00"))
