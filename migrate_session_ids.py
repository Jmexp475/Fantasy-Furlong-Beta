#!/usr/bin/env python3
"""Safe, lossless migration of Fantasy Furlong session IDs for API-loaded sessions.

Usage:
  python migrate_session_ids.py /path/to/session.json [--results /path/to/results.json]

Writes:
  /path/to/session_migrated.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_results_list(results_payload: Any) -> list[dict[str, Any]]:
    if isinstance(results_payload, list):
        return [x for x in results_payload if isinstance(x, dict)]
    if isinstance(results_payload, dict):
        items = results_payload.get("results", [])
        if isinstance(items, list):
            return [x for x in items if isinstance(x, dict)]
    return []


def _derive_race_mapping(session: dict[str, Any], results_list: list[dict[str, Any]] | None) -> dict[str, str]:
    races = session.get("meeting", {}).get("races", [])
    mapping: dict[str, str] = {}

    # Preferred deterministic source: api_race_id already stored on races.
    missing_api = []
    for race in races:
        old = str(race.get("race_id", "")).strip()
        api = str(race.get("api_race_id", "")).strip()
        if old and api:
            mapping[old] = api
        else:
            missing_api.append(old)

    if not missing_api:
        return mapping

    # Fallback: map by race order against results order when api_race_id is absent.
    if not results_list:
        raise RuntimeError(
            "Cannot complete migration: some races are missing api_race_id and no results JSON was provided."
        )

    session_races = sorted(races, key=lambda r: str(r.get("scheduled_off_dt_utc", "")))

    def results_sort_key(r: dict[str, Any]) -> str:
        for key in ("off_dt", "off_time", "scheduled_off", "race_off"):
            if r.get(key):
                return str(r.get(key))
        return ""

    sorted_results = sorted(results_list, key=results_sort_key) if any(results_sort_key(r) for r in results_list) else results_list
    result_ids = [str(r.get("race_id", "")).strip() for r in sorted_results if str(r.get("race_id", "")).strip()]

    if len(result_ids) < len(session_races):
        raise RuntimeError(
            f"Cannot complete fallback mapping: session has {len(session_races)} races but only {len(result_ids)} result race_ids available."
        )

    for race, result_id in zip(session_races, result_ids):
        old = str(race.get("race_id", "")).strip()
        if old and old not in mapping:
            mapping[old] = result_id

    return mapping


def migrate_session(session: dict[str, Any], results_list: list[dict[str, Any]] | None = None) -> tuple[dict[str, Any], dict[str, str]]:
    race_map = _derive_race_mapping(session, results_list)

    runner_map_by_race: dict[str, dict[str, str]] = {}
    races = session.get("meeting", {}).get("races", [])

    for race in races:
        old_race_id = str(race.get("race_id", ""))
        new_race_id = race_map.get(old_race_id, old_race_id)
        race["race_id"] = new_race_id
        race["api_race_id"] = new_race_id

        runner_map: dict[str, str] = {}
        for runner in race.get("runners", []):
            old_runner_id = str(runner.get("runner_id", ""))
            candidate = (
                str(runner.get("api_horse_id", "")).strip()
                or str(runner.get("horse_id", "")).strip()
                or (old_runner_id if old_runner_id.startswith("hrs_") else "")
            )
            if not candidate:
                candidate = old_runner_id

            runner["runner_id"] = candidate
            runner["race_id"] = new_race_id
            runner_map[old_runner_id] = candidate

        runner_map_by_race[old_race_id] = runner_map

        result_obj = race.get("results")
        if isinstance(result_obj, dict):
            result_obj["race_id"] = new_race_id
            if "placements" in result_obj and isinstance(result_obj["placements"], list):
                result_obj["placements"] = [runner_map.get(x, x) for x in result_obj["placements"]]
            if "dnf_runner_ids" in result_obj and isinstance(result_obj["dnf_runner_ids"], list):
                result_obj["dnf_runner_ids"] = [runner_map.get(x, x) for x in result_obj["dnf_runner_ids"]]

    snap = session.get("odds_snapshot", {})
    for race in snap.get("races", []):
        old_race_id = str(race.get("race_id", ""))
        new_race_id = race_map.get(old_race_id, old_race_id)
        race["race_id"] = new_race_id
        rmap = runner_map_by_race.get(old_race_id, {})
        for runner in race.get("runners", []):
            rid = str(runner.get("runner_id", ""))
            runner["runner_id"] = rmap.get(rid, rid)

    for pick in session.get("picks", []):
        old_race_id = str(pick.get("race_id", ""))
        new_race_id = race_map.get(old_race_id, old_race_id)
        old_runner_id = str(pick.get("runner_id", ""))
        new_runner_id = runner_map_by_race.get(old_race_id, {}).get(old_runner_id, old_runner_id)

        pick["race_id"] = new_race_id
        pick["runner_id"] = new_runner_id

        pick_id = str(pick.get("pick_id", ""))
        if pick_id:
            pick_id = pick_id.replace(old_race_id, new_race_id)
            pick_id = pick_id.replace(old_runner_id, new_runner_id)
            pick["pick_id"] = pick_id

    for sb in session.get("score_breakdowns", []):
        old_race_id = str(sb.get("race_id", ""))
        new_race_id = race_map.get(old_race_id, old_race_id)
        old_runner_id = str(sb.get("runner_id", ""))
        new_runner_id = runner_map_by_race.get(old_race_id, {}).get(old_runner_id, old_runner_id)
        sb["race_id"] = new_race_id
        sb["runner_id"] = new_runner_id
        score_id = str(sb.get("score_id", ""))
        if score_id:
            sb["score_id"] = score_id.replace(old_race_id, new_race_id).replace(old_runner_id, new_runner_id)

    # Integrity checks
    race_to_runner_ids = {
        str(r["race_id"]): {str(rn.get("runner_id")) for rn in r.get("runners", [])}
        for r in session.get("meeting", {}).get("races", [])
    }
    for pick in session.get("picks", []):
        rid = str(pick.get("race_id", ""))
        rnid = str(pick.get("runner_id", ""))
        if rnid not in race_to_runner_ids.get(rid, set()):
            raise RuntimeError(f"Integrity check failed: pick {pick.get('pick_id')} points to missing runner {rnid} in race {rid}")

    return session, race_map


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_json", type=Path)
    parser.add_argument("--results", type=Path, default=None, help="Optional /results payload JSON (list or {'results': [...]})")
    args = parser.parse_args()

    session = _load_json(args.input_json)
    results_list = _extract_results_list(_load_json(args.results)) if args.results else None

    migrated, race_map = migrate_session(session, results_list)

    output_path = args.input_json.with_name(f"{args.input_json.stem}_migrated{args.input_json.suffix}")
    output_path.write_text(json.dumps(migrated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    races = migrated.get("meeting", {}).get("races", [])
    print("Race mapping (old -> new):")
    for old_id, new_id in race_map.items():
        print(f"  {old_id} -> {new_id}")
    print(f"Total races migrated: {len(race_map)}")
    print("Session race_ids (first 5):", [str(r.get("race_id")) for r in races[:5]])
    first_runners = races[0].get("runners", []) if races else []
    print("First-race runner_ids (first 5):", [str(rn.get("runner_id")) for rn in first_runners[:5]])
    print(f"Picks preserved: {len(migrated.get('picks', []))}")
    print(f"Wrote migrated session: {output_path}")


if __name__ == "__main__":
    main()
