from __future__ import annotations

import json
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
_testclient = pytest.importorskip("fastapi.testclient")
TestClient = _testclient.TestClient
b = pytest.importorskip("backend_api")


def _write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_anonymous_public_endpoints_and_me_401(monkeypatch, tmp_path):
    web = tmp_path / "web"
    monkeypatch.setattr(b, "WEB", web)
    _write_json(web / "users.json", [])
    _write_json(web / "picks.json", [])

    client = TestClient(b.app)

    assert client.get("/api/meeting").status_code == 200
    assert client.get("/api/races").status_code == 200
    assert client.get("/api/configured-racedays").status_code == 200
    assert client.get("/api/leaderboard").status_code == 200

    me = client.get("/api/me")
    assert me.status_code == 401


def test_post_picks_requires_user_session(monkeypatch, tmp_path):
    web = tmp_path / "web"
    monkeypatch.setattr(b, "WEB", web)
    _write_json(web / "users.json", [{"id": "u_1", "displayName": "Alice", "isAdmin": False, "avatar": "A"}])
    _write_json(web / "picks.json", [])

    client = TestClient(b.app)
    payload = {"user_id": "u_1", "race_id": "r_1", "runner_id": "h_1"}
    res = client.post("/api/picks", json=payload)
    assert res.status_code == 401


def test_leaderboard_does_not_500_with_orphan_picks(monkeypatch, tmp_path):
    web = tmp_path / "web"
    monkeypatch.setattr(b, "WEB", web)
    _write_json(web / "users.json", [])
    _write_json(web / "picks.json", [{"userId": "u_missing", "raceId": "race_1", "runnerId": "runner_1"}])

    with b.STATE._lock:
        b.STATE._cache["session"] = {
            "meeting": {
                "meeting_id": "meeting_1",
                "races": [{"race_id": "race_1", "runners": [], "results": {"placements": [], "dnf_runner_ids": []}}],
            },
            "picks": [],
            "leaderboard": [],
        }
    client = TestClient(b.app)
    res = client.get("/api/leaderboard")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_wrong_course_race_is_not_mapped_into_configured_day(monkeypatch):
    monkeypatch.setattr(b.STATE, "race_day_states", [{"slot": 1, "course": "Warwick", "date": "2026-03-08", "status": "loaded", "races": [], "last_refresh": None, "last_error": None, "next_check_utc": None}])
    session = {
        "meeting": {
            "meeting_id": "m1",
            "course": "Warwick",
            "races": [
                {
                    "race_id": "r1",
                    "name": "Bad mapped race",
                    "off_time_local": "13:00",
                    "scheduled_off_dt_utc": "2026-03-08T13:00:00+00:00",
                    "status": "open",
                    "runners": [],
                    "results": {},
                    "_ff_day_index": 0,
                    "_ff_slot": 1,
                    "_ff_course": "Ayr",
                    "_ff_date": "2026-03-08",
                }
            ],
        }
    }
    _meeting, races = b.STATE._to_frontend_model(session)
    assert races == []


def test_users_cleanup_removes_legacy_npc_seed(monkeypatch, tmp_path):
    web = tmp_path / "web"
    monkeypatch.setattr(b, "WEB", web)
    seeded = [
        {"id": "u_you", "displayName": "You", "isAdmin": True, "avatar": "Y"},
        {"id": "u_p1", "displayName": "Player 1", "isAdmin": False, "avatar": "P"},
        {"id": "u_real", "displayName": "Alice", "isAdmin": False, "avatar": "A"},
    ]
    _write_json(web / "users.json", seeded)

    users = b.STATE.users()
    assert users == [{"id": "u_real", "displayName": "Alice", "isAdmin": False, "avatar": "A"}]
    persisted = b._read_json(web / "users.json", [])
    assert persisted == users


def test_fetch_racecards_allows_future_iso_day_token(monkeypatch):
    called = {}

    class FakeClient:
        def __init__(self, username, password):
            pass
        def list_courses(self, region_codes=None):
            return [{"course": "Warwick", "course_id": 99}]
        def fetch_racecards_standard(self, day, course_ids=None, region_codes=None):
            called["day"] = day
            called["course_ids"] = course_ids
            return {"racecards": []}

    monkeypatch.setattr(b, "TheRacingApiClient", FakeClient)
    monkeypatch.setattr(b, "find_course_id", lambda courses, name='Warwick': 99)
    monkeypatch.setattr(
        b,
        "adapt_racecards_to_session",
        lambda racecards_json, target_course_id, target_course_name, target_date_local, timezone, config: {"meeting": {"races": []}},
    )

    b.STATE.user = "u"
    b.STATE.password = "p"
    b.STATE.target_course = "Warwick"
    b.STATE.course_id = None

    session, cid = b.STATE._fetch_racecards_session("2026-03-11", "Warwick")
    assert cid == 99
    assert called["day"] == "2026-03-11"
    assert session.get("meeting", {}).get("races", []) == []
