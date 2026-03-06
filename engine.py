"""Odds and scoring engine."""
from __future__ import annotations

import math
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo
from typing import Any
from numeric_utils import safe_float, safe_int


def _round(value: float, dp: int = 2) -> float:
    quant = Decimal("1") / (Decimal("10") ** dp)
    return float(Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_UP))


def _safe_decimal(value: Any) -> float | None:
    """Return decimal odds if parseable and >=1.0, otherwise None."""
    parsed = safe_float(value)
    if parsed is None:
        return None
    return parsed if parsed >= 1.0 else None


def odds_multiplier(decimal_odds: Any, multiplier_type: str = "sqrt") -> float:
    dec = _safe_decimal(decimal_odds)
    if dec is None:
        return 0.0
    if multiplier_type == "sqrt":
        return math.sqrt(dec)
    # Backward compatible fallback if unknown config is provided.
    return math.sqrt(dec)


def paid_places_for_field_size(field_size: int, config: dict[str, Any]) -> int:
    for band in config["paid_places"]:
        if band["min"] <= field_size <= band["max"]:
            return safe_int(band["places"]) or 1
    return 1


def recompute_fair_odds_for_race(race: dict[str, Any], config: dict[str, Any]) -> None:
    valid = [r for r in race["runners"] if r.get("market_decimal")]
    if not valid:
        return
    implied = [1.0 / r["market_decimal"] for r in valid]
    total = sum(implied)
    divisor = safe_float(config["odds"].get("place_divisor")) or 1.0
    for runner in race["runners"]:
        if not runner.get("market_decimal"):
            runner["fair_decimal"] = None
            runner["place_decimal_fair"] = None
            runner["odds_status"] = "missing"
            runner["scoreable"] = False
            continue
        p = (1.0 / runner["market_decimal"]) / total
        fair = 1.0 / p
        place = 1.0 + ((fair - 1.0) / divisor)
        runner["fair_decimal"] = _round(fair, config.get("internal_dp", 6))
        runner["place_decimal_fair"] = _round(place, config.get("internal_dp", 6))
        runner["odds_status"] = "ok"
        runner["scoreable"] = True


def lock_due_races(session: dict[str, Any]) -> None:
    now = datetime.now(ZoneInfo("UTC"))
    for race in session["meeting"]["races"]:
        if race["locked"]:
            continue
        off = datetime.fromisoformat(race["scheduled_off_dt_utc"])
        if now >= off:
            race["locked"] = True
            race["status"] = "locked"
            for pick in session["picks"]:
                if pick["race_id"] == race["race_id"]:
                    pick["locked"] = True


def _score_pick(race: dict[str, Any], result: dict[str, Any], pick: dict[str, Any], config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
    runners = {r["runner_id"]: r for r in race["runners"]}
    runner = runners.get(pick["runner_id"])
    placement_map = {rid: idx + 1 for idx, rid in enumerate(result["placements"]) if rid}
    finish = placement_map.get(pick["runner_id"])
    paid_places = paid_places_for_field_size(len(race["runners"]), config)
    outcome = "none"
    points = 0.0
    stats = {"wins": 0, "placings": 0, "dnfs": 0}

    win_multiplier_type = config.get("odds", {}).get("win_multiplier", {}).get("type", "sqrt")
    place_multiplier_type = config.get("odds", {}).get("place_multiplier", {}).get("type", "sqrt")

    if pick["runner_id"] in result["dnf_runner_ids"]:
        # DNF penalty is unmultiplied and applied directly.
        penalty = config["scoring"]["dnf_penalty"]["points"]
        points += penalty
        outcome = "dnf"
        stats["dnfs"] = 1
    elif finish == 1:
        base = config["scoring"]["base_points"]["win"]
        fair = runner["fair_decimal"] if runner else None
        points += base * odds_multiplier(fair, win_multiplier_type)
        outcome = "win"
        stats["wins"] = 1
        stats["placings"] = 1
    elif finish and finish <= paid_places:
        base = config["scoring"]["base_points"]["place"]
        fair = runner["place_decimal_fair"] if runner else None
        points += base * odds_multiplier(fair, place_multiplier_type)
        outcome = "place"
        stats["placings"] = 1

    points = _round(points, 2)
    breakdown = {
        "score_id": f"sc_{pick['race_id']}_{pick['player_id']}",
        "meeting_id": pick["meeting_id"],
        "race_id": pick["race_id"],
        "player_id": pick["player_id"],
        "runner_id": pick["runner_id"],
        "finish_position": finish,
        "outcome": outcome,
        "points": points,
        "base_points": config["scoring"]["base_points"]["win"] if outcome == "win" else config["scoring"]["base_points"]["place"],
        "fair_decimal_used": runner["fair_decimal"] if runner else None,
        "computed_at_utc": datetime.now(ZoneInfo("UTC")).isoformat(),
    }
    return breakdown, stats


def rescore_session(session: dict[str, Any], config: dict[str, Any]) -> None:
    score_breakdowns: list[dict[str, Any]] = []
    tallies: dict[str, dict[str, Any]] = {
        p["player_id"]: {"player_name": p["name"], "points": 0.0, "wins": 0, "placings": 0, "dnfs": 0}
        for p in session["meeting"].get("players", [])
    }

    race_map = {r["race_id"]: r for r in session["meeting"]["races"]}
    for race in session["meeting"]["races"]:
        recompute_fair_odds_for_race(race, config)

    for pick in session["picks"]:
        race = race_map[pick["race_id"]]
        result = race.get("results")
        if not result:
            continue
        breakdown, stats = _score_pick(race, result, pick, config)
        score_breakdowns.append(breakdown)
        row = tallies[pick["player_id"]]
        row["points"] += breakdown["points"]
        row["wins"] += stats["wins"]
        row["placings"] += stats["placings"]
        row["dnfs"] += stats["dnfs"]

    ranking = sorted(tallies.items(), key=lambda item: (-item[1]["points"], -item[1]["wins"], -item[1]["placings"], item[1]["dnfs"], item[0]))
    leaderboard: list[dict[str, Any]] = []
    rank = 0
    prev = None
    for idx, (player_id, row) in enumerate(ranking, start=1):
        key = (row["points"], row["wins"], row["placings"], row["dnfs"])
        if key != prev:
            rank = idx
            prev = key
        leaderboard.append(
            {
                "player_id": player_id,
                "player_name": row["player_name"],
                "points": _round(row["points"], 2),
                "wins": row["wins"],
                "placings": row["placings"],
                "dnfs": row["dnfs"],
                "rank": rank,
            }
        )

    session["score_breakdowns"] = score_breakdowns
    session["leaderboard"] = leaderboard
