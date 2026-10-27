from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.errors import AppError
from app.main import create_app


class Payload(BaseModel):
    title: str


def make_client() -> TestClient:
    app = create_app()

    @app.post("/api/_test/validate")
    def validate(payload: Payload) -> Payload:
        return payload

    @app.get("/api/_test/app-error")
    def app_error() -> None:
        raise AppError("FORBIDDEN", 403)

    @app.get("/api/_test/crash")
    def crash() -> None:
        raise RuntimeError("boom")

    return TestClient(app, raise_server_exceptions=False)


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-Id"]


def test_request_id_is_echoed(client: TestClient) -> None:
    response = client.get("/api/health", headers={"X-Request-Id": "abc123"})
    assert response.headers["X-Request-Id"] == "abc123"


def test_not_found_uses_error_envelope(client: TestClient) -> None:
    response = client.get("/api/does-not-exist")
    body = response.json()
    assert response.status_code == 404
    assert body["status"] == "error"
    assert body["data"]["code"] == "NOT_FOUND"
    assert body["message"] == "Nie znaleziono."
    assert body["request_id"] == response.headers["X-Request-Id"]


def test_validation_error_is_400_with_fields() -> None:
    response = make_client().post("/api/_test/validate", json={})
    body = response.json()
    assert response.status_code == 400
    assert body["data"]["code"] == "VALIDATION_ERROR"
    assert body["data"]["context"]["fields"] == {"title": "missing"}


def test_app_error_message_follows_accept_language() -> None:
    response = make_client().get("/api/_test/app-error", headers={"Accept-Language": "en-GB,en"})
    assert response.status_code == 403
    assert response.json()["message"] == "You do not have permission to do this."


def test_unexpected_error_is_500_envelope() -> None:
    response = make_client().get("/api/_test/crash")
    assert response.status_code == 500
    assert response.json()["data"]["code"] == "INTERNAL_SERVER_ERROR"
