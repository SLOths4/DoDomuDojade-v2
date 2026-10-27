from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.events import Event
from app.users.models import User
from tests.conftest import ApiClient

pytestmark = pytest.mark.db

TODAY = date(2026, 10, 28)


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed = datetime(2026, 10, 28, 12, 0, tzinfo=clock.get_settings().tz)
    monkeypatch.setattr(clock, "now", lambda: fixed)


def payload(**overrides: Any) -> dict[str, Any]:
    return {
        "title": "Wycieczka",
        "text": "Zbiórka o 8:00 przed szkołą.",
        "validUntil": "2026-11-15",
    } | overrides


def event_types(db: Session) -> list[str]:
    return list(db.scalars(select(Event.type).order_by(Event.id)))


def test_requires_login(api: ApiClient) -> None:
    assert api.get("/api/announcements").status_code == 401


def test_staff_announcement_is_approved_immediately(moderator_api: ApiClient, db: Session) -> None:
    response = moderator_api.post("/api/announcements", json=payload(title="  Wycieczka  "))
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Wycieczka"
    assert body["status"] == "approved"
    assert body["author"]["username"] == "moderator"
    assert body["decidedBy"]["username"] == "moderator"
    assert event_types(db) == ["announcement.created"]


def test_valid_until_today_is_allowed_and_yesterday_is_not(moderator_api: ApiClient) -> None:
    assert (
        moderator_api.post(
            "/api/announcements", json=payload(validUntil=TODAY.isoformat())
        ).status_code
        == 201
    )
    past = moderator_api.post(
        "/api/announcements", json=payload(validUntil=(TODAY - timedelta(days=1)).isoformat())
    )
    assert past.status_code == 400
    assert past.json()["data"]["code"] == "VALID_UNTIL_OUT_OF_RANGE"
    assert past.json()["message"] == "Data ważności musi być między 2026-10-28 a 2027-10-28."


def test_field_limits_are_validated(moderator_api: ApiClient) -> None:
    response = moderator_api.post("/api/announcements", json=payload(title="abc", text="krótki"))
    assert response.status_code == 400
    assert response.json()["data"]["context"]["fields"] == {
        "title": "string_too_short",
        "text": "string_too_short",
    }


def test_missing_or_malformed_date_is_400_not_500(moderator_api: ApiClient) -> None:
    assert (
        moderator_api.post("/api/announcements", json=payload(validUntil="jutro")).status_code
        == 400
    )
    body = payload()
    del body["title"]
    assert moderator_api.post("/api/announcements", json=body).status_code == 400


def test_expired_announcement_text_can_still_be_edited(
    moderator_api: ApiClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = moderator_api.post("/api/announcements", json=payload(validUntil="2026-10-30")).json()
    later = datetime(2026, 11, 5, 9, 0, tzinfo=clock.get_settings().tz)
    monkeypatch.setattr(clock, "now", lambda: later)
    response = moderator_api.patch(
        f"/api/announcements/{created['id']}", json={"text": "Poprawiony tekst ogłoszenia."}
    )
    assert response.status_code == 200
    assert response.json()["text"] == "Poprawiony tekst ogłoszenia."
    moved = moderator_api.patch(
        f"/api/announcements/{created['id']}", json={"validUntil": "2026-11-01"}
    )
    assert moved.json()["data"]["code"] == "VALID_UNTIL_OUT_OF_RANGE"


def test_status_cannot_be_changed_through_edit(moderator_api: ApiClient) -> None:
    created = moderator_api.post("/api/announcements", json=payload()).json()
    response = moderator_api.patch(
        f"/api/announcements/{created['id']}", json={"status": "pending"}
    )
    assert response.status_code == 400


def test_public_proposal_flow(api: ApiClient, make_user: Callable[..., User], db: Session) -> None:
    proposal = api.post(
        "/api/announcements/proposals",
        json={"title": "Kiermasz", "text": "Kiermasz ciast w piątek."},
    )
    assert proposal.status_code == 201
    body = proposal.json()
    assert body["status"] == "pending"
    assert body["author"] is None
    assert body["validUntil"] == "2026-11-27"

    make_user("moderator")
    api.post("/api/auth/login", json={"username": "moderator", "password": "haslo-testowe-123"})
    pending = api.get("/api/announcements", params={"status": "pending"}).json()
    assert [a["id"] for a in pending] == [body["id"]]

    approved = api.post(f"/api/announcements/{body['id']}/approve").json()
    assert approved["status"] == "approved"
    assert approved["decidedBy"]["username"] == "moderator"
    rejected = api.post(f"/api/announcements/{body['id']}/reject").json()
    assert rejected["status"] == "rejected"
    assert event_types(db) == [
        "announcement.proposed",
        "announcement.approved",
        "announcement.rejected",
    ]


def test_proposals_are_rate_limited(api: ApiClient) -> None:
    body = {"title": "Kiermasz", "text": "Kiermasz ciast w piątek."}
    for _ in range(5):
        assert api.post("/api/announcements/proposals", json=body).status_code == 201
    blocked = api.post("/api/announcements/proposals", json=body)
    assert blocked.status_code == 429


def test_delete_and_not_found(moderator_api: ApiClient, db: Session) -> None:
    created = moderator_api.post("/api/announcements", json=payload()).json()
    assert moderator_api.delete(f"/api/announcements/{created['id']}").status_code == 204
    missing = moderator_api.get(f"/api/announcements/{created['id']}")
    assert missing.status_code == 404
    assert missing.json()["data"]["code"] == "ANNOUNCEMENT_NOT_FOUND"
    assert event_types(db) == ["announcement.created", "announcement.deleted"]


def test_deleting_the_decider_keeps_the_announcement(
    admin_api: ApiClient, make_user: Callable[..., User], db: Session
) -> None:
    moderator = make_user("odchodzi")
    other = ApiClient(admin_api.app, raise_server_exceptions=False)
    with other:
        other.get("/api/config")
        other.post(
            "/api/auth/login", json={"username": "odchodzi", "password": "haslo-testowe-123"}
        )
        created = other.post("/api/announcements", json=payload()).json()
    assert admin_api.delete(f"/api/users/{moderator.id}").status_code == 204
    kept = admin_api.get(f"/api/announcements/{created['id']}").json()
    assert kept["author"] is None
    assert kept["decidedBy"] is None
