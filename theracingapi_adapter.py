"""Adapt TheRacingAPI responses to Fantasy Furlong canonical session objects."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from engine import paid_places_for_field_size, recompute_fair_odds_for_race
from numeric_utils import safe_float, safe_int
import re


NON_NUMERIC_DNF_STATUSES = {"PU", "UR", "F", "BD", "DSQ", "RO", "RR", "VOID", "REF", "SU", "DNF"}


def _extract_result_off_dt(result_obj: dict[str, Any]) -> str | None:
    for key in ("off_dt", "off_time", "scheduled_off", "race_off"):
        val = result_obj.get(key)
        if val:
            return str(val)
    return None


def _normalise_off_key(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00")).astimezone(ZoneInfo("UTC"))
        return dt.strftime("%Y-%m-%dT%H:%M")
    except Exception:
        return None


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _as_float(value: Any) -> float | None:
    val = safe_float(value)
    if val is None:
        return None
    return val if val > 1.0 else None


def _off_dt_from_race(race: dict[str, Any]) -> str:
    for key in ("off_dt", "off_time", "off_time_utc"):
        raw = race.get(key)
        if raw:
            try:
                return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).astimezone(ZoneInfo("UTC")).isoformat()
            except Exception:
                continue
    # fallback to now UTC when malformed
    return datetime.now(ZoneInfo("UTC")).isoformat()


def _pick_runner_odds(runner: dict[str, Any]) -> tuple[str | None, float | None]:
    odds_rows = runner.get("odds") or []
    chosen: dict[str, Any] | None = None

    for row in odds_rows:
        if str(row.get("bookmaker", "")).strip().lower() == "bet365":
            dec = _as_float(row.get("decimal"))
            if dec:
                chosen = row
                break
    if chosen is None:
        for row in odds_rows:
            if _as_float(row.get("decimal")):
                chosen = row
                break

    if not chosen:
        return None, None

    frac = chosen.get("fractional")
    dec = _as_float(chosen.get("decimal"))
    display = str(frac).strip() if frac not in (None, "", "-") else str(chosen.get("decimal")).strip()
    return display if display else None, dec


def find_course_id(courses: list[dict[str, Any]], name: str = "Southwell") -> str | int:
    if not courses:
        raise ValueError("No courses returned from API")
    needle = name.strip().lower()

    exact = [c for c in courses if str(c.get("course", c.get("name", ""))).strip().lower() == needle]
    pool = exact if exact else [c for c in courses if needle in str(c.get("course", c.get("name", ""))).strip().lower()]
    if not pool:
        raise ValueError(f"Course '{name}' not found in API response")

    course = pool[0]
    course_id = course.get("course_id") or course.get("id")
    if course_id is None:
        raise ValueError("Matched course does not include course_id")
    return course_id


def adapt_racecards_to_session(
    racecards_json: dict[str, Any],
    target_course_id: str | int,
    target_course_name: str,
    target_date_local: str,
    timezone: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    racecards = racecards_json.get("racecards", []) if isinstance(racecards_json, dict) else []
    meeting_id = f"meet_{target_date_local}_{_slugify(target_course_name)}"
    snapshot_id = f"odds_{target_date_local}_0900"

    races: list[dict[str, Any]] = []
    for race in racecards:
        race_course_id = race.get("course_id") or race.get("course", {}).get("course_id")
        race_region = str(race.get("region", "")).upper()
        race_date = race.get("date")
        if str(race_course_id) != str(target_course_id):
            continue
        if race_region and race_region != "GB":
            continue
        if race_date and str(race_date) != target_date_local:
            continue

        race_index = len(races) + 1
        off_utc = _off_dt_from_race(race)
        off_local = datetime.fromisoformat(off_utc).astimezone(ZoneInfo(timezone)).strftime("%H:%M")
        race_id = str(race.get("race_id", "")).strip()
        if not race_id:
            raise ValueError("API racecard record missing race_id")

        canonical_race = {
            "race_id": race_id,
            "meeting_id": meeting_id,
            "race_index": race_index,
            "name": race.get("race_name") or race.get("race") or f"Race {race_index}",
            "off_time_local": off_local,
            "scheduled_off_dt_utc": off_utc,
            "status": "open",
            "locked": False,
            "rescore_count": 0,
            "runners": [],
            "results": None,
            "day": 1,
            "api_race_id": race.get("race_id") or race_id,
        }

        raw_runners = race.get("runners", [])
        for idx, runner in enumerate(raw_runners, start=1):
            market_odds, market_decimal = _pick_runner_odds(runner)
            runner_id = str(runner.get("horse_id", "")).strip()
            if not runner_id:
                raise ValueError(f"API runner missing horse_id for race_id={race_id}")
            quotes = runner.get("quotes") if isinstance(runner.get("quotes"), list) else []
            canonical_race["runners"].append(
                {
                    "runner_id": runner_id,
                    "race_id": race_id,
                    "number": idx,
                    "horse_name": runner.get("horse") or runner.get("horse_name") or f"Runner {idx}",
                    "trainer": runner.get("trainer", ""),
                    "jockey": runner.get("jockey", ""),
                    "silk_url": runner.get("silk_url"),
                    "form": runner.get("form", ""),
                    "age": runner.get("age"),
                    "sex_code": runner.get("sex_code", ""),
                    "owner": runner.get("owner", ""),
                    "lbs": runner.get("lbs"),
                    "ofr": runner.get("ofr"),
                    "sire": runner.get("sire", ""),
                    "dam": runner.get("dam", ""),
                    "quotes": [str(q) for q in quotes if q],
                    "market_odds": market_odds,
                    "market_decimal": market_decimal,
                    "fair_decimal": None,
                    "place_decimal_fair": None,
                    "odds_status": "ok" if market_decimal else "missing",
                    "scoreable": bool(market_decimal),
                    "allow_pick": True,
                    "api_horse_id": runner.get("horse_id"),
                }
            )

        recompute_fair_odds_for_race(canonical_race, config)
        scoreable = [r for r in canonical_race["runners"] if r.get("scoreable")]
        canonical_race["status"] = "open" if len(scoreable) >= 2 else "awaiting_odds"
        races.append(canonical_race)

    races.sort(key=lambda r: r["scheduled_off_dt_utc"])
    for idx, race in enumerate(races, start=1):
        race["race_index"] = idx

    meeting = {
        "meeting_id": meeting_id,
        "name": f"{target_course_name} API",
        "course": target_course_name,
        "date_local": target_date_local,
        "timezone": timezone,
        "races": races,
        "players": [],
        "status": "racecard_loaded" if races else "empty",
        "snapshot_id": snapshot_id,
        "source": "api",
    }

    snapshot = {
        "snapshot_id": snapshot_id,
        "meeting_id": meeting_id,
        "captured_at_utc": datetime.now(ZoneInfo("UTC")).isoformat(),
        "races": [
            {
                "race_id": race["race_id"],
                "runners": [
                    {"runner_id": r["runner_id"], "market_odds": r["market_odds"], "market_decimal": r["market_decimal"]}
                    for r in race["runners"]
                ],
            }
            for race in races
        ],
    }

    return {
        "meeting": meeting,
        "odds_snapshot": snapshot,
        "picks": [],
        "score_breakdowns": [],
        "leaderboard": [],
        "api_meta": {
            "course_id": target_course_id,
            "course_name": target_course_name,
            "date_local": target_date_local,
            "timezone": timezone,
        },
    }


def _result_is_official(result_rec: dict[str, Any]) -> bool:
    if isinstance(result_rec.get("is_official"), bool):
        return bool(result_rec["is_official"])
    status = str(result_rec.get("status", "")).strip().lower()
    return status in {"official", "final", "result", "complete"}


def apply_results_to_session(session: dict[str, Any], results_list: list[dict[str, Any]], cfg: dict[str, Any]) -> int:
    races = session.get("meeting", {}).get("races", [])
    if not races:
        return 0

    results_by_race_id = {str(item.get("race_id")): item for item in results_list if item.get("race_id") is not None}
    session_race_ids = [str(r.get("race_id")) for r in races[:5]]
    result_race_ids = [str(r.get("race_id")) for r in results_list[:5]]
    print(f"[API] Session race_ids (first 5): {session_race_ids}")
    print(f"[API] Result race_ids (first 5): {result_race_ids}")

    max_rescore_count = safe_int(cfg.get("settlement", {}).get("max_rescore_count", 1)) or 1
    now_utc = datetime.now(ZoneInfo("UTC")).isoformat()
    matched_count = 0
    settled_count = 0
    skip_reasons: list[str] = []
    updated_count = 0

    for race in races:
        race_id = str(race.get("race_id"))
        result_rec = results_by_race_id.get(race_id)
        if not result_rec:
            continue
        matched_count += 1

        is_official = _result_is_official(result_rec)
        current = race.get("results") or {}
        if race.get("status") == "settled" and bool(current.get("is_official")) and (safe_int(race.get("rescore_count", 0)) or 0) >= max_rescore_count and is_official:
            continue

        runner_ids = {str(rn.get("runner_id")) for rn in race.get("runners", [])}
        winners: dict[int, str] = {}
        dnfs: list[str] = []
        for item in result_rec.get("runners", []):
            horse_id = str(item.get("horse_id", "")).strip()
            if not horse_id:
                continue
            position = str(item.get("position", "")).strip().upper()
            if position.isdigit():
                parsed_pos = safe_int(position)
                if parsed_pos is not None:
                    winners[parsed_pos] = horse_id
            elif position:
                dnfs.append(horse_id)

        paid_places = min(4, paid_places_for_field_size(len(race.get("runners", [])), cfg))
        placements = [winners.get(i, "") for i in range(1, paid_places + 1)]
        available_places = sum(1 for rid in placements if rid)
        missing_runner_ids = [rid for rid in placements if rid and rid not in runner_ids]

        status = "official" if is_official else "provisional"
        prev_result = race.get("results") or {}
        new_signature = (tuple(placements), tuple(sorted(set(dnfs))), is_official)
        old_signature = (
            tuple(prev_result.get("placements", [])),
            tuple(sorted(set(prev_result.get("dnf_runner_ids", [])))),
            bool(prev_result.get("is_official")),
        )
        if new_signature == old_signature:
            continue

        if missing_runner_ids:
            race_status = "settling"
            skip_reasons.append(f"{race_id}: placed horse IDs missing in race runners: {missing_runner_ids[:3]}")
        elif available_places < paid_places:
            race_status = "settling"
            skip_reasons.append(f"{race_id}: placements incomplete ({available_places}/{paid_places})")
        else:
            blocked = any(rid and next((rn for rn in race["runners"] if rn["runner_id"] == rid and rn["odds_status"] == "missing"), None) for rid in placements)
            race_status = "awaiting_odds" if blocked else "settled"
            if race_status == "settled":
                settled_count += 1

        race["results"] = {
            "result_id": f"res_{race_id}",
            "race_id": race_id,
            "status": status,
            "placements": placements,
            "dnf_runner_ids": sorted(set(dnfs)),
            "dnfs": sorted(set(dnfs)),
            "is_official": is_official,
            "updated_at_utc": now_utc,
            "settled_at_utc": now_utc,
        }
        if is_official and (not bool(prev_result.get("is_official")) or tuple(prev_result.get("placements", [])) != tuple(placements)):
            race["rescore_count"] = (safe_int(race.get("rescore_count", 0)) or 0) + 1
        race["status"] = race_status
        race["locked"] = race_status in {"settled", "awaiting_odds", "settling"}
        updated_count += 1

    print(f"[API] Matched results by race_id: {matched_count}")
    if matched_count and settled_count == 0 and skip_reasons:
        print("[API] Matched races but 0 settled. Reasons:", "; ".join(skip_reasons[:5]))
    return updated_count


def adapt_results_to_result_objects(
    results_json_list: list[dict[str, Any]],
    meeting_session: dict[str, Any],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Backward-compatible helper retained for existing call sites/tests."""
    races = meeting_session.get("meeting", {}).get("races", [])
    results_by_race_id = {str(item.get("race_id")): item for item in results_json_list if item.get("race_id") is not None}
    updates: list[dict[str, Any]] = []
    for race in races:
        result_rec = results_by_race_id.get(str(race.get("race_id")))
        if not result_rec:
            continue
        runners = result_rec.get("runners", [])
        winners: dict[int, str] = {}
        dnfs: list[str] = []
        for item in runners:
            horse_id = str(item.get("horse_id", "")).strip()
            position = str(item.get("position", "")).strip().upper()
            if not horse_id:
                continue
            if position.isdigit():
                parsed_pos = safe_int(position)
                if parsed_pos is not None:
                    winners[parsed_pos] = horse_id
            elif position:
                dnfs.append(horse_id)
        paid_places = min(4, paid_places_for_field_size(len(race.get("runners", [])), config))
        placements = [winners.get(i, "") for i in range(1, paid_places + 1)]
        updates.append(
            {
                "result_id": f"res_{race['race_id']}",
                "race_id": race["race_id"],
                "status": "official" if _result_is_official(result_rec) else "provisional",
                "placements": placements,
                "dnf_runner_ids": sorted(set(dnfs)),
                "is_official": _result_is_official(result_rec),
                "updated_at_utc": datetime.now(ZoneInfo("UTC")).isoformat(),
            }
        )
    return updates
