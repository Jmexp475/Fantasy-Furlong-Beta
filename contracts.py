"""Canonical contracts and validation helpers for Fantasy Furlong."""
from __future__ import annotations

from typing import Any

CONTRACTS: dict[str, set[str]] = {
    "Meeting": {"meeting_id", "name", "course", "date_local", "timezone", "races", "players", "status", "snapshot_id"},
    "Race": {"race_id", "meeting_id", "race_index", "name", "off_time_local", "scheduled_off_dt_utc", "status", "locked", "rescore_count", "runners", "results", "day"},
    "Runner": {"runner_id", "race_id", "number", "horse_name", "market_odds", "market_decimal", "fair_decimal", "place_decimal_fair", "odds_status", "scoreable", "allow_pick"},
    "OddsSnapshot": {"snapshot_id", "meeting_id", "captured_at_utc", "races"},
    "Pick": {"pick_id", "meeting_id", "race_id", "player_id", "runner_id", "locked", "picked_at_utc"},
    "Result": {"result_id", "race_id", "status", "placements", "dnf_runner_ids", "is_official", "updated_at_utc"},
    "ScoreBreakdown": {"score_id", "meeting_id", "race_id", "player_id", "runner_id", "finish_position", "outcome", "points", "base_points", "fair_decimal_used", "computed_at_utc"},
    "LeaderboardRow": {"player_id", "player_name", "points", "wins", "placings", "dnfs", "rank"},
}


class ContractError(ValueError):
    """Raised when an object does not match required contract keys."""


def _validate_shape(name: str, obj: dict[str, Any]) -> None:
    required = CONTRACTS[name]
    missing = sorted(required.difference(obj.keys()))
    if missing:
        raise ContractError(f"{name} missing required fields: {missing}")


def validate_against_contracts(session: dict[str, Any]) -> None:
    """Validate top-level session payload against canonical JSON contracts."""
    if "meeting" not in session:
        raise ContractError("Session missing 'meeting'")
    if "odds_snapshot" not in session:
        raise ContractError("Session missing 'odds_snapshot'")

    meeting = session["meeting"]
    _validate_shape("Meeting", meeting)

    for race in meeting["races"]:
        _validate_shape("Race", race)
        for runner in race["runners"]:
            _validate_shape("Runner", runner)
        if race.get("results"):
            _validate_shape("Result", race["results"])

    _validate_shape("OddsSnapshot", session["odds_snapshot"])

    for pick in session.get("picks", []):
        _validate_shape("Pick", pick)

    for sb in session.get("score_breakdowns", []):
        _validate_shape("ScoreBreakdown", sb)

    for row in session.get("leaderboard", []):
        _validate_shape("LeaderboardRow", row)
