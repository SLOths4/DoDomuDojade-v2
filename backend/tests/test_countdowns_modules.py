from datetime import datetime, time

import pytest

from app.core import clock
from app.modules.service import in_window
from tests.conftest import ApiClient

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=clock.get_settings().tz)


@pytest.fixture
def fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now", lambda: NOW)


@pytest.mark.parametrize(
    ("start", "end", "at", "expected"),
    [
        (time(8), time(16), time(12), True),
        (time(8), time(16), time(16), True),
        (time(8), time(16), time(17), False),
        (time(22), time(6), time(23), True),
        (time(22), time(6), time(5, 59), True),
        (time(22), time(6), time(12), False),
        (time(0), time(0), time(13), True),
    ],
)
def test_module_window(start: time, end: time, at: time, expected: bool) -> None:
    assert in_window(start, end, at) is expected


@pytest.mark.db
@pytest.mark.usefixtures("fixed_clock")
def test_countdown_crud(moderator_api: ApiClient) -> None:
    created = moderator_api.post(
        "/api/countdowns", json={"title": "Ferie zimowe", "countTo": "2027-01-19T08:00:00+01:00"}
    )
    assert created.status_code == 201
    countdown = created.json()
    assert countdown["author"]["username"] == "moderator"

    updated = moderator_api.patch(f"/api/countdowns/{countdown['id']}", json={"title": "Ferie!"})
    assert updated.json()["title"] == "Ferie!"
    assert [c["id"] for c in moderator_api.get("/api/countdowns").json()] == [countdown["id"]]
    assert moderator_api.delete(f"/api/countdowns/{countdown['id']}").status_code == 204
    assert moderator_api.get(f"/api/countdowns/{countdown['id']}").status_code == 404


@pytest.mark.db
@pytest.mark.usefixtures("fixed_clock")
def test_countdown_must_be_in_future_and_timezone_aware(moderator_api: ApiClient) -> None:
    past = moderator_api.post(
        "/api/countdowns", json={"title": "Wczoraj", "countTo": "2026-10-27T08:00:00+01:00"}
    )
    assert past.json()["data"]["code"] == "COUNT_TO_IN_PAST"
    naive = moderator_api.post(
        "/api/countdowns", json={"title": "Bez strefy", "countTo": "2027-01-19T08:00:00"}
    )
    assert naive.status_code == 400


@pytest.mark.db
def test_modules_seeded_and_listed(moderator_api: ApiClient) -> None:
    modules = moderator_api.get("/api/modules").json()
    assert {m["name"] for m in modules} == {
        "announcement",
        "calendar",
        "countdown",
        "departures",
        "weather",
        "quote",
        "word",
    }
    assert all(m["startTime"] == m["endTime"] == "00:00:00" for m in modules)


@pytest.mark.db
def test_moderator_cannot_update_modules(moderator_api: ApiClient) -> None:
    module_id = moderator_api.get("/api/modules").json()[0]["id"]
    response = moderator_api.patch(f"/api/modules/{module_id}", json={"isActive": False})
    assert response.status_code == 403


@pytest.mark.db
def test_admin_updates_module_window(admin_api: ApiClient) -> None:
    module_id = admin_api.get("/api/modules").json()[0]["id"]
    response = admin_api.patch(
        f"/api/modules/{module_id}",
        json={"isActive": False, "startTime": "22:00", "endTime": "06:30"},
    )
    assert response.status_code == 200
    assert (
        response.json() | {"isActive": False, "startTime": "22:00:00", "endTime": "06:30:00"}
        == response.json()
    )
