"""Fantasy Furlong desktop application entrypoint."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import json
import os
import uuid
import threading
import time
from datetime import datetime
from tkinter import messagebox
from zoneinfo import ZoneInfo

import ttkbootstrap as tb

from contracts import validate_against_contracts
from engine import lock_due_races, rescore_session
from master_config_loader import MasterConfigError, load_master_config, load_racing_api_credentials
from storage import ensure_dirs, load_session, normalise_api_session_ids, save_session
from theracingapi_adapter import adapt_racecards_to_session, apply_results_to_session, find_course_id
from theracingapi_client import TheRacingApiClient, TheRacingApiRequestError
from ui_components import FurlongUI


class FurlongApp:
    def __init__(self) -> None:
        self.root = tb.Window(themename="darkly")
        self.root.title("Fantasy Furlong")
        self.root.geometry("1300x820")
        self.root.minsize(1200, 800)

        self.config = self._load_config_or_exit()
        ensure_dirs()

        self.api_username, self.api_password, self.api_credentials_source = load_racing_api_credentials(ROOT, self.config)
        self.debug_api = os.getenv("DEBUG_API", "0") == "1"
        print(f"[API] Credentials loaded from: {self.api_credentials_source}")
        print(f"[API] Username present: {bool(self.api_username)}, Password present: {bool(self.api_password)}")
        if self.debug_api:
            print("[API DEBUG] base_url=https://api.theracingapi.com/v1")
        self.api_missing_message = "API disconnected: Missing RACING_API_USERNAME/RACING_API_PASSWORD. Create secrets/racingapi.env"

        self.session: dict | None = None
        self.selected_race_id: str | None = None
        self.api_meta: dict | None = None
        self.api_loading = False
        self.results_watcher_started = False

        self.ui = FurlongUI(self)
        if not (self.api_username and self.api_password):
            print(self.api_missing_message)
            self.ui.set_api_banner(self.api_missing_message)
            self.ui.set_api_connected(False, None)
        else:
            self.ui.set_api_banner("API connected — ready")
            self.ui.set_api_connected(True, datetime.now().strftime("%H:%M"))

        self._load_any_existing_session()
        self._tick_locking()

    def _load_config_or_exit(self) -> dict:
        candidates = [Path("/mnt/data/Master_config_V1.txt"), Path("Master_config_V1.txt")]
        for path in candidates:
            try:
                if path.exists():
                    return load_master_config(path)
            except MasterConfigError as exc:
                messagebox.showerror("Config error", str(exc))
                raise SystemExit(1)
        messagebox.showerror("Config error", "Master_config_V1.txt not found. Please place it at /mnt/data or project root.")
        raise SystemExit(1)

    def _load_any_existing_session(self) -> None:
        sessions = sorted(Path("data/sessions").glob("*.json"))
        if not sessions:
            return
        self.session = load_session(sessions[-1].stem)
        if not self.session:
            return

        if normalise_api_session_ids(self.session):
            save_session(self.session)

        # restore API context for persisted API sessions so polling can continue after restart
        self.api_meta = self.session.get("api_meta")
        if self.session.get("meeting", {}).get("source") == "api" and self.api_meta and self.api_username and self.api_password:
            self.ui.set_api_banner("API connected — restoring results watcher")
            self.ui.set_api_connected(True, datetime.now().strftime("%H:%M"))
            self._start_results_watcher_once()

        self.ui.refresh_all()

    def start_new_session(self, meeting: dict, snapshot: dict) -> None:
        session = {
            "meeting": meeting,
            "odds_snapshot": snapshot,
            "picks": [],
            "score_breakdowns": [],
            "leaderboard": [],
        }
        validate_against_contracts(session)
        self.session = session
        save_session(session)

    def replace_session(self, session: dict) -> None:
        validate_against_contracts(session)
        self.session = session
        save_session(session)


    def add_player(self, name: str) -> None:
        if not self.session:
            return
        clean_name = (name or "").strip()
        if not clean_name:
            return

        player = {
            "player_id": str(uuid.uuid4()),
            "name": clean_name,
        }

        self.session["meeting"].setdefault("players", [])
        self.session["meeting"]["players"].append(player)

        save_session(self.session)
        self.ui.refresh_players()
        self.ui.refresh_all()

    def remove_player(self, player_id: str) -> None:
        if not self.session:
            return

        players = self.session["meeting"].get("players", [])
        self.session["meeting"]["players"] = [p for p in players if p.get("player_id") != player_id]

        # clear current player if removed
        selected_player_id = self.ui._selected_player_id() if hasattr(self.ui, "_selected_player_id") else None
        if selected_player_id and all(p.get("player_id") != selected_player_id for p in self.session["meeting"]["players"]):
            self.ui.current_player.set("")

        save_session(self.session)
        self.ui.refresh_players()
        self.ui.refresh_all()

    def _tick_locking(self) -> None:
        if self.session:
            lock_due_races(self.session)
            save_session(self.session)
            self.ui.refresh_all()
        self.root.after(1000, self._tick_locking)

    def _load_api_session(self, use_sample: bool) -> tuple[dict, dict]:
        target_course = "Southwell"
        target_date_local = "2026-03-02"
        timezone = self.config["timezone"]

        if use_sample:
            racecards_path = Path("/mnt/data/2026-03-01_racecards (1).json")
            if not racecards_path.exists():
                raise RuntimeError("Sample racecards file missing: /mnt/data/2026-03-01_racecards (1).json")
            racecards_json = json.loads(racecards_path.read_text(encoding="utf-8"))
            sample_courses = [{"course": rc.get("course") or rc.get("course_name"), "course_id": rc.get("course_id")} for rc in racecards_json.get("racecards", [])]
            course_id = find_course_id(sample_courses, target_course)
            print("[API] Course matched:", course_id)
        else:
            username = self.api_username or os.getenv("RACING_API_USERNAME", "")
            password = self.api_password or os.getenv("RACING_API_PASSWORD", "")
            if not username or not password:
                raise RuntimeError(self.api_missing_message)

            client = TheRacingApiClient(username=username, password=password)
            courses = client.list_courses(region_codes=["gb"])
            course_id = find_course_id(courses, target_course)
            print("[API] Course matched:", course_id)
            racecards_json = client.fetch_racecards_standard(day="tomorrow", course_ids=[course_id], region_codes=["gb"])

        adapted = adapt_racecards_to_session(
            racecards_json=racecards_json,
            target_course_id=course_id,
            target_course_name=target_course,
            target_date_local=target_date_local,
            timezone=timezone,
            config=self.config,
        )
        normalise_api_session_ids(adapted)
        validate_against_contracts(adapted)

        races = adapted["meeting"]["races"]
        print("[API] Races loaded:", len(races))
        print("[API] Session race_ids (first 5):", [str(r.get("race_id")) for r in races[:5]])
        first_runners = races[0].get("runners", []) if races else []
        print("[API] Session first-race runner_ids (first 5):", [str(rn.get("runner_id")) for rn in first_runners[:5]])

        meta = {
            "course_id": course_id,
            "course_name": target_course,
            "date_local": target_date_local,
            "use_sample": use_sample,
            "last_sync": datetime.now().strftime("%H:%M"),
        }
        return adapted, meta

    def load_southwell_from_api(self, use_sample: bool = False) -> None:
        if self.api_loading:
            return
        if not use_sample and not (self.api_username and self.api_password):
            print(self.api_missing_message)
            self.ui.set_api_banner(self.api_missing_message)
            self.ui.set_api_connected(False, None)
            messagebox.showerror("API credentials missing", self.api_missing_message)
            return
        self.api_loading = True
        self.ui.set_api_banner("Connecting to API…")

        def worker() -> None:
            try:
                loaded_session, meta = self._load_api_session(use_sample=use_sample)

                def apply_loaded() -> None:
                    self.replace_session(loaded_session)
                    self.api_meta = meta
                    self.ui.set_api_connected(True, meta["last_sync"])
                    self.ui.refresh_all()
                    self._start_results_watcher_once()
                    self.api_loading = False

                self.root.after(0, apply_loaded)
            except TheRacingApiRequestError as exc:
                err_msg = f"API disconnected: {exc.exc_type} status={exc.status_code}"
                body_snippet = exc.body_snippet[:200]

                def on_err() -> None:
                    self.api_loading = False
                    self.ui.set_api_banner(err_msg)
                    self.ui.set_api_connected(False, None)
                    messagebox.showerror("API load failed", f"{err_msg}\n{body_snippet}")

                self.root.after(0, on_err)
            except Exception as exc:
                err_msg = str(exc)

                def on_err() -> None:
                    self.api_loading = False
                    self.ui.set_api_banner(err_msg)
                    self.ui.set_api_connected(False, None)
                    messagebox.showerror("API load failed", err_msg)

                self.root.after(0, on_err)

        threading.Thread(target=worker, daemon=True).start()

    def _start_results_watcher_once(self) -> None:
        if self.results_watcher_started:
            return
        self.results_watcher_started = True

        def watcher() -> None:
            while True:
                try:
                    print("[API] Polling results... (every 5 minutes)")
                    updated_count = self._poll_results_once()
                    if updated_count:
                        self.root.after(0, self._on_results_updated)
                except Exception as exc:
                    print("[API watcher]", exc)
                time.sleep(300)

        threading.Thread(target=watcher, daemon=True).start()

    def _poll_results_once(self) -> int:
        if not self.session or not self.api_meta:
            return 0
        if self.session.get("meeting", {}).get("source") != "api":
            return 0

        races = self.session["meeting"]["races"]
        if not races:
            return 0

        if not self.api_meta.get("use_sample"):
            first_off = min(datetime.fromisoformat(r["scheduled_off_dt_utc"]) for r in races)
            if datetime.now(ZoneInfo("UTC")) < first_off:
                return 0

        target_date = self.api_meta["date_local"]
        course_id = self.api_meta["course_id"]

        if self.api_meta.get("use_sample"):
            path = Path("/mnt/data/2026-02-22_2026-03-01_results.json")
            if not path.exists():
                print("[API] sample results file missing")
                return 0
            payload = json.loads(path.read_text(encoding="utf-8"))
            results_list = payload if isinstance(payload, list) else payload.get("results", [])
        else:
            username = self.api_username or os.getenv("RACING_API_USERNAME", "")
            password = self.api_password or os.getenv("RACING_API_PASSWORD", "")
            if not username or not password:
                print(self.api_missing_message)
                self.root.after(0, lambda: self.ui.set_api_banner(self.api_missing_message))
                return 0
            client = TheRacingApiClient(username=username, password=password)
            try:
                results_list = client.fetch_results(start_date=target_date, end_date=target_date, course=[course_id])
            except TheRacingApiRequestError as exc:
                self.root.after(0, lambda m=f"API disconnected: {exc.exc_type} status={exc.status_code}": self.ui.set_api_banner(m))
                self.root.after(0, lambda: self.ui.set_api_connected(False, None))
                raise

        if self.debug_api:
            print(f"[API DEBUG] results payload count={len(results_list)}")

        updated_count = apply_results_to_session(self.session, results_list, self.config)
        if updated_count > 0:
            rescore_session(self.session, self.config)
            save_session(self.session)
            print("[API] Results updated:", updated_count)
            return updated_count

        self.root.after(0, lambda: self.ui.set_api_banner("API connected — no official results yet"))
        self.root.after(0, lambda: self.ui.set_api_connected(True, datetime.now().strftime("%H:%M")))
        print("[API] Results updated:", 0)
        return 0

    def _on_results_updated(self) -> None:
        if self.api_meta:
            self.api_meta["last_sync"] = datetime.now().strftime("%H:%M")
            self.ui.set_api_connected(True, self.api_meta["last_sync"])
            self.ui.set_api_banner("API connected")
        self.ui.refresh_all()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    FurlongApp().run()
