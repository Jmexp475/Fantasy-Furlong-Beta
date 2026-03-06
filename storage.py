"""Persistence and audit storage."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Any


BASE = Path("data")
SESSIONS = BASE / "sessions"
AUDIT = BASE / "audit"
EXPORTS = BASE / "exports"


def ensure_dirs() -> None:
    SESSIONS.mkdir(parents=True, exist_ok=True)
    AUDIT.mkdir(parents=True, exist_ok=True)
    EXPORTS.mkdir(parents=True, exist_ok=True)


def session_file(meeting_id: str) -> Path:
    return SESSIONS / f"{meeting_id}.json"


def load_session(meeting_id: str) -> dict[str, Any] | None:
    path = session_file(meeting_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_session(session: dict[str, Any]) -> None:
    ensure_dirs()
    meeting_id = session["meeting"]["meeting_id"]
    path = session_file(meeting_id)
    path.write_text(json.dumps(session, indent=2), encoding="utf-8")


def audit_path(meeting_id: str) -> Path:
    return AUDIT / f"audit_{meeting_id}.log"


def append_audit(meeting_id: str, actor: str, action: str, payload: dict[str, Any]) -> None:
    ensure_dirs()
    line = {
        "at_utc": datetime.now(ZoneInfo("UTC")).isoformat(),
        "actor": actor,
        "action": action,
        "payload": payload,
    }
    with audit_path(meeting_id).open("a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")


def read_audit(meeting_id: str, limit: int = 500) -> list[dict[str, Any]]:
    path = audit_path(meeting_id)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
    return [json.loads(line) for line in lines if line.strip()]


def export_session(session: dict[str, Any]) -> Path:
    ensure_dirs()
    meeting_id = session["meeting"]["meeting_id"]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = EXPORTS / f"{meeting_id}_{ts}.json"
    path.write_text(json.dumps(session, indent=2), encoding="utf-8")
    return path


def normalise_api_session_ids(session: dict[str, Any]) -> bool:
    """Normalise API session race/runner IDs to API-native values without losing picks."""
    meeting = session.get("meeting", {})
    if meeting.get("source") != "api":
        return False

    races = meeting.get("races", [])
    picks = session.get("picks", [])
    score_breakdowns = session.get("score_breakdowns", [])
    odds_races = session.get("odds_snapshot", {}).get("races", [])

    race_id_map: dict[str, str] = {}
    runner_id_map_by_old_race: dict[str, dict[str, str]] = {}
    race_ids_normalised = 0
    runners_normalised = 0
    picks_remapped = 0
    changed = False

    # pass 1: normalise races/runners, build mapping tables
    for race in races:
        old_race_id = str(race.get("race_id", ""))
        api_race_id = str(race.get("api_race_id", "")).strip()
        new_race_id = api_race_id if api_race_id else old_race_id

        if api_race_id and old_race_id != new_race_id:
            race["race_id"] = new_race_id
            race_ids_normalised += 1
            changed = True

        race_id_map[old_race_id] = new_race_id
        race["api_race_id"] = new_race_id

        runner_map: dict[str, str] = {}
        for runner in race.get("runners", []):
            old_runner_id = str(runner.get("runner_id", ""))
            api_horse_id = str(runner.get("api_horse_id", "")).strip()
            new_runner_id = api_horse_id if api_horse_id else old_runner_id

            if api_horse_id and old_runner_id != new_runner_id:
                runner["runner_id"] = new_runner_id
                runners_normalised += 1
                changed = True

            runner["race_id"] = new_race_id
            runner_map[old_runner_id] = new_runner_id

        runner_id_map_by_old_race[old_race_id] = runner_map

        result_obj = race.get("results")
        if isinstance(result_obj, dict):
            if result_obj.get("race_id") != new_race_id:
                result_obj["race_id"] = new_race_id
                changed = True
            if isinstance(result_obj.get("placements"), list):
                mapped = [runner_map.get(str(rid), str(rid)) for rid in result_obj.get("placements", [])]
                if mapped != result_obj.get("placements"):
                    result_obj["placements"] = mapped
                    changed = True
            if isinstance(result_obj.get("dnf_runner_ids"), list):
                mapped = [runner_map.get(str(rid), str(rid)) for rid in result_obj.get("dnf_runner_ids", [])]
                if mapped != result_obj.get("dnf_runner_ids"):
                    result_obj["dnf_runner_ids"] = mapped
                    changed = True

    # pass 2: remap references
    for pick in picks:
        old_race_id = str(pick.get("race_id", ""))
        new_race_id = race_id_map.get(old_race_id, old_race_id)
        if new_race_id != old_race_id:
            pick["race_id"] = new_race_id
            changed = True

        old_runner_id = str(pick.get("runner_id", ""))
        new_runner_id = runner_id_map_by_old_race.get(old_race_id, {}).get(old_runner_id, old_runner_id)
        if new_runner_id != old_runner_id:
            pick["runner_id"] = new_runner_id
            picks_remapped += 1
            changed = True

    for sb in score_breakdowns:
        old_race_id = str(sb.get("race_id", ""))
        new_race_id = race_id_map.get(old_race_id, old_race_id)
        if new_race_id != old_race_id:
            sb["race_id"] = new_race_id
            changed = True

        old_runner_id = str(sb.get("runner_id", ""))
        new_runner_id = runner_id_map_by_old_race.get(old_race_id, {}).get(old_runner_id, old_runner_id)
        if new_runner_id != old_runner_id:
            sb["runner_id"] = new_runner_id
            changed = True

    for snap_race in odds_races:
        old_race_id = str(snap_race.get("race_id", ""))
        new_race_id = race_id_map.get(old_race_id, old_race_id)
        if new_race_id != old_race_id:
            snap_race["race_id"] = new_race_id
            changed = True

        rmap = runner_id_map_by_old_race.get(old_race_id, {})
        for snap_runner in snap_race.get("runners", []):
            old_runner_id = str(snap_runner.get("runner_id", ""))
            new_runner_id = rmap.get(old_runner_id, old_runner_id)
            if new_runner_id != old_runner_id:
                snap_runner["runner_id"] = new_runner_id
                changed = True

    # validation
    for race in races:
        rid = str(race.get("race_id", ""))
        if not rid.startswith("rac_"):
            raise ValueError(f"API session race_id is not normalised: {rid}")
        for runner in race.get("runners", []):
            api_horse_id = str(runner.get("api_horse_id", "")).strip()
            runner_id = str(runner.get("runner_id", ""))
            if api_horse_id and not runner_id.startswith("hrs_"):
                raise ValueError(f"API session runner_id is not normalised for horse {api_horse_id}: {runner_id}")

    race_runner_index = {
        str(race.get("race_id", "")): {str(rn.get("runner_id", "")) for rn in race.get("runners", [])}
        for race in races
    }
    for pick in picks:
        rid = str(pick.get("race_id", ""))
        rnid = str(pick.get("runner_id", ""))
        if rnid not in race_runner_index.get(rid, set()):
            raise ValueError(f"Pick points to missing runner after normalisation: pick={pick.get('pick_id')} race={rid} runner={rnid}")

    print(f"[API] ID normalisation: races={race_ids_normalised} runners={runners_normalised} picks_remapped={picks_remapped}")
    return changed
