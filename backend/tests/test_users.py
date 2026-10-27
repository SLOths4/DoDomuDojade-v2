from collections.abc import Callable

import pytest

from app.users.models import Role, User
from tests.conftest import ApiClient, login

pytestmark = pytest.mark.db


def test_moderator_cannot_manage_users(moderator_api: ApiClient) -> None:
    response = moderator_api.get("/api/users")
    assert response.status_code == 403
    assert response.json()["data"]["code"] == "FORBIDDEN"


def test_admin_creates_user_who_must_change_password(admin_api: ApiClient, api: ApiClient) -> None:
    created = admin_api.post(
        "/api/users", json={"username": "  nauczyciel ", "password": "startowe-haslo"}
    )
    assert created.status_code == 201
    body = created.json()
    assert body["username"] == "nauczyciel"
    assert body["role"] == "moderator"
    assert body["mustChangePassword"] is True
    duplicate = admin_api.post(
        "/api/users", json={"username": "nauczyciel", "password": "startowe-haslo"}
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["message"] == "Login nauczyciel jest już zajęty."


def test_admin_updates_role_and_username(
    admin_api: ApiClient, make_user: Callable[..., User]
) -> None:
    user = make_user("ola")
    response = admin_api.patch(f"/api/users/{user.id}", json={"username": "ola2", "role": "admin"})
    assert response.status_code == 200
    assert response.json() == response.json() | {"username": "ola2", "role": "admin"}


def test_admin_cannot_change_own_role_or_delete_self(admin_api: ApiClient, admin: User) -> None:
    demote = admin_api.patch(f"/api/users/{admin.id}", json={"role": "moderator"})
    assert demote.json()["data"]["code"] == "CANNOT_CHANGE_OWN_ACCESS"
    delete = admin_api.delete(f"/api/users/{admin.id}")
    assert delete.json()["data"]["code"] == "CANNOT_DELETE_SELF"


def test_admin_can_deactivate_and_delete_another_admin(
    admin_api: ApiClient, make_user: Callable[..., User]
) -> None:
    other = make_user("drugi-admin", Role.ADMIN)
    response = admin_api.patch(f"/api/users/{other.id}", json={"isActive": False})
    assert response.json()["isActive"] is False
    assert admin_api.delete(f"/api/users/{other.id}").status_code == 204


def test_deactivation_logs_the_user_out(
    app_factory_client: Callable[[], ApiClient], admin: User, make_user: Callable[..., User]
) -> None:
    target = make_user("kasia")
    admin_client, user_client = app_factory_client(), app_factory_client()
    login(admin_client, "admin")
    login(user_client, "kasia")
    assert user_client.get("/api/auth/me").status_code == 200
    admin_client.patch(f"/api/users/{target.id}", json={"isActive": False})
    assert user_client.get("/api/auth/me").status_code == 401


def test_password_reset_forces_change_and_ends_sessions(
    app_factory_client: Callable[[], ApiClient], admin: User, make_user: Callable[..., User]
) -> None:
    target = make_user("tomek")
    admin_client, user_client = app_factory_client(), app_factory_client()
    login(admin_client, "admin")
    login(user_client, "tomek")
    reset = admin_client.post(
        f"/api/users/{target.id}/password", json={"newPassword": "tymczasowe-haslo"}
    )
    assert reset.status_code == 204
    assert user_client.get("/api/auth/me").status_code == 401
    relogged = login(user_client, "tomek", "tymczasowe-haslo")
    assert relogged.json()["mustChangePassword"] is True


def test_delete_unknown_user_is_404(admin_api: ApiClient) -> None:
    response = admin_api.delete("/api/users/999999")
    assert response.status_code == 404
    assert response.json()["data"]["code"] == "USER_NOT_FOUND"
