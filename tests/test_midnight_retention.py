from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pytest

b = pytest.importorskip("backend_api")


def _write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _race(race_id: str, runner_id: str, horse: str, course: str, day: str, slot: int, off: str, status: str = "settled") -> dict:
    return {
        "race_id": race_id,
        "name": race_id,
        "off_time_local": "13:00",
        "scheduled_off_dt_utc": off,
        "status": status,
        "_ff_course": course,
        "_ff_date": day,
        "_ff_slot": slot,
        "runners": [
            {
                "runner_id": runner_id,
                "horse_name": horse,
                "market_odds": "2/1",
                "market_decimal": 3.0,
                "fair_decimal": 3.0,
                "place_decimal_fair": 2.0,
                "odds_status": "ok",
                "scoreable": True,
                "trainer": "T",
                "jockey": "J",
                "quotes": ["Q"],
            }
        ],
        "results": {"placements": [runner_id], "dnf_runner_ids": [], "is_official": True},
    }


def test_refresh_keeps_previous_day_data_and_scores(monkeypatch, tmp_path):
    web = tmp_path / "web"
    _write_json(web / "users.json", [{"id": "u1", "displayName": "Alice", "isAdmin": False, "avatar": "A"}])

    today = b._utc_now().astimezone(b.STATE.local_tz).date()
    prev = (today - timedelta(days=1)).isoformat()
    today_s = today.isoformat()

    _write_json(web / "picks.json", [{"userId": "u1", "raceId": "race_prev", "runnerId": "hrs_prev"}])

    configured = [
        {"slot": 1, "course": "Warwick", "date": prev, "label": "Day 1"},
        {"slot": 2, "course": "Warwick", "date": today_s, "label": "Day 2"},
    ]

    persisted_session = {
        "meeting": {
            "meeting_id": "festival_current",
            "course": "Warwick",
            "source": "api",
            "races": [
                _race("race_prev", "hrs_prev", "Yesterday Horse", "Warwick", prev, 1, f"{prev}T13:00:00+00:00", status="settled")
            ],
        }
    }

    today_session = {
        "meeting": {
            "meeting_id": "festival_current",
            "course": "Warwick",
            "source": "api",
            "races": [
                _race("race_today", "hrs_today", "Today Horse", "Warwick", today_s, 2, f"{today_s}T13:00:00+00:00", status="open")
            ],
        }
    }

    monkeypatch.setattr(b, "WEB", web)
    monkeypatch.setattr(b.STATE, "user", "u")
    monkeypatch.setattr(b.STATE, "password", "p")
    monkeypatch.setattr(b.STATE, "_load_configured_race_days", lambda: configured)
    monkeypatch.setattr(b.STATE, "_load_persisted_session_candidates", lambda: [persisted_session])
    monkeypatch.setattr(b.STATE, "_fetch_racecards_session", lambda local_day, course: (today_session, 1))

    class FakeClient:
        def __init__(self, u, p):
            pass

        def fetch_results(self, start_date=None, end_date=None, course=None):
            return []

    monkeypatch.setattr(b, "TheRacingApiClient", FakeClient)
    monkeypatch.setattr(b, "save_session", lambda session: None)
    monkeypatch.setattr(b, "_write_json", lambda path, payload: None)

    out = b.STATE.refresh_once(force=True)
    assert out["ok"] is True

    snap = b.STATE.snapshot()
    race_ids = {r["id"] for r in snap["races"]}
    assert "race_prev" in race_ids
    assert "race_today" in race_ids

    day1 = next(d for d in snap["meeting"]["raceDays"] if d["date"] == prev)
    assert day1["status"] == "loaded"
    assert any(r["id"] == "race_prev" for r in day1["races"])

    board = b.STATE.leaderboard()
    alice = next(row for row in board if row["userId"] == "u1")
    assert alice["totalPoints"] > 0
