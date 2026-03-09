from __future__ import annotations

import pytest

b = pytest.importorskip("backend_api")


def test_default_racedays_are_cheltenham_four_day_festival():
    payload = b._default_racedays_payload()
    assert payload == {
        "raceDays": [
            {"course": "Cheltenham", "date": "2026-03-10"},
            {"course": "Cheltenham", "date": "2026-03-11"},
            {"course": "Cheltenham", "date": "2026-03-12"},
            {"course": "Cheltenham", "date": "2026-03-13"},
        ]
    }


def test_refresh_attempts_loading_all_four_configured_cheltenham_days(monkeypatch):
    configured = [
        {"slot": 1, "course": "Cheltenham", "date": "2026-03-10", "label": "Day 1"},
        {"slot": 2, "course": "Cheltenham", "date": "2026-03-11", "label": "Day 2"},
        {"slot": 3, "course": "Cheltenham", "date": "2026-03-12", "label": "Day 3"},
        {"slot": 4, "course": "Cheltenham", "date": "2026-03-13", "label": "Day 4"},
    ]
    called_days: list[str] = []

    def fake_fetch(local_day: str, course: str):
        called_days.append(local_day)
        assert course == "Cheltenham"
        return ({"meeting": {"meeting_id": "festival_current", "course": "Cheltenham", "source": "api", "races": []}}, 123)

    class FakeClient:
        def __init__(self, u, p):
            pass

        def fetch_results(self, start_date=None, end_date=None, course=None):
            return []

    monkeypatch.setattr(b.STATE, "user", "u")
    monkeypatch.setattr(b.STATE, "password", "p")
    monkeypatch.setattr(b.STATE, "_load_configured_race_days", lambda: configured)
    monkeypatch.setattr(b.STATE, "_load_persisted_session_candidates", lambda: [])
    monkeypatch.setattr(b.STATE, "_fetch_racecards_session", fake_fetch)
    monkeypatch.setattr(b, "TheRacingApiClient", FakeClient)
    monkeypatch.setattr(b, "save_session", lambda session: None)
    monkeypatch.setattr(b, "_write_json", lambda path, payload: None)

    out = b.STATE.refresh_once(force=True)
    assert out["ok"] is True
    assert called_days == ["2026-03-10", "2026-03-11", "2026-03-12", "2026-03-13"]
