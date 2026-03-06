"""Modern AppShell UI for Fantasy Furlong desktop app."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import os
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any
from zoneinfo import ZoneInfo

from excel_importer import import_racecard_xlsx, parse_odds_to_decimal, slugify
from engine import paid_places_for_field_size, recompute_fair_odds_for_race, rescore_session
from storage import SESSIONS, append_audit, export_session, read_audit, save_session


STATUS_COLORS = {
    "open": "success",
    "locked": "warning",
    "settled": "secondary",
    "awaiting_odds": "danger",
    "settling": "info",
}


@dataclass
class UploadSummary:
    file_name: str = ""
    loaded_at: str = ""
    warnings: int = 0
    meeting_text: str = ""
    races: int = 0
    runners: int = 0


class FurlongUI:
    """AppShell controller and pages."""

    def __init__(self, app: Any):
        self.app = app
        self.root = app.root
        self.current_page = "Home"
        self.day_filter = 1
        self.selected_runner_id: str | None = None
        self.upload_summary = UploadSummary()

        self.current_player = tk.StringVar(value="")
        self.player_name_to_id: dict[str, str] = {}
        self.player_id_to_name: dict[str, str] = {}
        self.meeting_badge = tk.StringVar(value="No meeting loaded")
        self.chip_racecard = tk.StringVar(value="Racecard: Not loaded")
        self.chip_odds = tk.StringVar(value="Odds: Awaiting")
        self.chip_picks = tk.StringVar(value="Picks: Open")
        self.chip_api = tk.StringVar(value="API: Disconnected")
        self.chip_sync = tk.StringVar(value="Last Sync: --:--")

        self.home_next_race = tk.StringVar(value="No upcoming race")
        self.home_meeting_summary = tk.StringVar(value="Load a racecard to begin")
        self.session_info_text = tk.StringVar(value="Session not loaded")
        self.my_pick_text = tk.StringVar(value="No pick selected")
        self.dashboard_race_title = tk.StringVar(value="Select a race")
        self.dashboard_points_guide = tk.StringVar(value="Select a runner to see projected returns")
        self.table_header = tk.StringVar(value="Live standings: 0 of 0 races settled")
        self.upload_status = tk.StringVar(value="No upload performed")
        self.player_name_var = tk.StringVar(value="Player name")
        self._player_placeholder_active = True

        self._configure_styles()
        self._build_shell()

    def _configure_styles(self) -> None:
        style = ttk.Style()
        bg = "#0e1b14"
        card = "#173225"
        accent = "#d5b46a"
        self.root.configure(bg=bg)

        style.configure("App.TFrame", background=bg)
        style.configure("Card.TFrame", background=card, borderwidth=1, relief="solid")
        style.configure("Header.TFrame", background="#10261a")
        style.configure("CardTitle.TLabel", background=card, foreground="#f1e7cf", font=("Segoe UI", 12, "bold"))
        style.configure("Muted.TLabel", background=card, foreground="#d2d2c9")
        style.configure("MainTitle.TLabel", background="#10261a", foreground="#f4e9c9", font=("Segoe UI", 24, "bold"))
        style.configure("Badge.TLabel", background="#244737", foreground="#f4e9c9", padding=(10, 4), font=("Segoe UI", 10, "bold"))
        style.configure("Gold.TButton", font=("Segoe UI", 10, "bold"))
        style.map("Gold.TButton", background=[("!disabled", accent)], foreground=[("!disabled", "#1b1b1b")])

    def _build_shell(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        self.header = ttk.Frame(self.root, style="Header.TFrame", padding=(14, 10))
        self.header.grid(row=0, column=0, sticky="nsew")
        self.header.columnconfigure(2, weight=1)
        self._build_header()

        self.nav = ttk.Frame(self.root, style="Header.TFrame", padding=(12, 4))
        self.nav.grid(row=1, column=0, sticky="ew")
        self._build_nav()

        self.page_container = ttk.Frame(self.root, style="App.TFrame", padding=(12, 12))
        self.page_container.grid(row=2, column=0, sticky="nsew")
        self.page_container.columnconfigure(0, weight=1)
        self.page_container.rowconfigure(0, weight=1)

        self.pages: dict[str, ttk.Frame] = {
            "Home": self._build_home_page(),
            "Dashboard": self._build_dashboard_page(),
            "Tables": self._build_tables_page(),
            "Admin": self._build_admin_page(),
            "Uploads": self._build_uploads_page(),
        }
        self._show_page("Home")

    def _build_header(self) -> None:
        ttk.Label(self.header, text="🐎 FURLONG", style="MainTitle.TLabel").grid(row=0, column=0, padx=(0, 12), sticky="w")
        ttk.Label(self.header, textvariable=self.meeting_badge, style="Badge.TLabel").grid(row=0, column=1, sticky="w")

        chips = ttk.Frame(self.header, style="Header.TFrame")
        chips.grid(row=0, column=2, sticky="e")
        for idx, var in enumerate((self.chip_racecard, self.chip_odds, self.chip_picks, self.chip_api, self.chip_sync)):
            ttk.Label(chips, textvariable=var, style="Badge.TLabel").grid(row=0, column=idx, padx=4)

        player_box = ttk.Frame(self.header, style="Header.TFrame")
        player_box.grid(row=0, column=3, padx=(12, 0), sticky="e")
        ttk.Label(player_box, text="Current Player", style="Badge.TLabel").grid(row=0, column=0, padx=(0, 4))
        self.header_player_combo = ttk.Combobox(player_box, textvariable=self.current_player, state="readonly", width=18)
        self.header_player_combo.grid(row=0, column=1)
        self.header_player_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh_all())

    def _build_nav(self) -> None:
        self.nav_buttons: dict[str, ttk.Button] = {}
        for idx, name in enumerate(["Home", "Dashboard", "Tables", "Admin", "Uploads"]):
            btn = ttk.Button(self.nav, text=name, command=lambda p=name: self._show_page(p), style="Gold.TButton")
            btn.grid(row=0, column=idx, padx=4, ipadx=8)
            self.nav_buttons[name] = btn

    def _build_home_page(self) -> ttk.Frame:
        frame = ttk.Frame(self.page_container, style="App.TFrame")
        frame.columnconfigure(0, weight=3)
        frame.columnconfigure(1, weight=2)
        frame.rowconfigure(1, weight=1)

        banner = ttk.Frame(frame, style="Card.TFrame", padding=12)
        banner.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        ttk.Label(banner, text="FURLONG FESTIVAL HUB", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(banner, text="Test desktop control center for races, picks and settlement", style="Muted.TLabel").grid(row=1, column=0, sticky="w")

        left = ttk.Frame(frame, style="App.TFrame")
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        left.columnconfigure(0, weight=1)

        next_card = ttk.Frame(left, style="Card.TFrame", padding=12)
        next_card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(next_card, text="Next Race", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(next_card, textvariable=self.home_next_race, style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(6, 6))
        ttk.Button(next_card, text="Go to Dashboard", command=lambda: self._show_page("Dashboard"), style="Gold.TButton").grid(row=2, column=0, sticky="w")

        self.players_card = ttk.Frame(left, style="Card.TFrame", padding=12)
        self.players_card.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        self.players_card.columnconfigure(0, weight=1)
        ttk.Label(self.players_card, text="Players", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")

        right = ttk.Frame(frame, style="App.TFrame")
        right.grid(row=1, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)

        my_pick = ttk.Frame(right, style="Card.TFrame", padding=12)
        my_pick.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(my_pick, text="My Pick", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(my_pick, textvariable=self.my_pick_text, style="Muted.TLabel", wraplength=320).grid(row=1, column=0, sticky="w", pady=6)

        session = ttk.Frame(right, style="Card.TFrame", padding=12)
        session.grid(row=1, column=0, sticky="ew")
        ttk.Label(session, text="Session Info", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(session, textvariable=self.session_info_text, style="Muted.TLabel", wraplength=320).grid(row=1, column=0, sticky="w", pady=6)

        upload_cta = ttk.Frame(frame, style="Card.TFrame", padding=12)
        upload_cta.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Button(upload_cta, text="Upload Excel Racecard (.xlsx)", command=lambda: self._show_page("Uploads"), style="Gold.TButton").grid(row=0, column=0, sticky="ew")

        return frame

    def _build_dashboard_page(self) -> ttk.Frame:
        frame = ttk.Frame(self.page_container, style="App.TFrame")
        frame.columnconfigure(0, weight=3)
        frame.columnconfigure(1, weight=7)
        frame.rowconfigure(1, weight=1)

        day_bar = ttk.Frame(frame, style="Card.TFrame", padding=8)
        day_bar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        self.day_buttons: list[ttk.Button] = []
        for idx in range(1, 5):
            btn = ttk.Button(day_bar, text=f"Day {idx}", command=lambda d=idx: self._set_day(d), style="Gold.TButton")
            btn.grid(row=0, column=idx - 1, padx=4)
            self.day_buttons.append(btn)

        race_card = ttk.Frame(frame, style="Card.TFrame", padding=10)
        race_card.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        race_card.rowconfigure(1, weight=1)
        race_card.columnconfigure(0, weight=1)
        ttk.Label(race_card, text="Race List", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")

        self.race_listbox = tk.Listbox(race_card, bg="#1a3428", fg="#efe8d0", selectbackground="#d5b46a", selectforeground="#1b1b1b")
        self.race_listbox.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        race_scroll = ttk.Scrollbar(race_card, orient="vertical", command=self.race_listbox.yview)
        race_scroll.grid(row=1, column=1, sticky="ns")
        self.race_listbox.configure(yscrollcommand=race_scroll.set)
        self.race_listbox.bind("<<ListboxSelect>>", self._on_select_race)

        detail = ttk.Frame(frame, style="Card.TFrame", padding=10)
        detail.grid(row=1, column=1, sticky="nsew")
        detail.rowconfigure(2, weight=1)
        detail.columnconfigure(0, weight=1)

        ttk.Label(detail, textvariable=self.dashboard_race_title, style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        self.race_state_label = ttk.Label(detail, text="Picks Open", style="Muted.TLabel")
        self.race_state_label.grid(row=1, column=0, sticky="w", pady=(0, 6))

        cols = ("no", "horse", "market", "fair", "pick")
        self.runner_tree = ttk.Treeview(detail, columns=cols, show="headings", height=15)
        self.runner_tree.heading("no", text="No")
        self.runner_tree.heading("horse", text="Horse")
        self.runner_tree.heading("market", text="Market Odds")
        self.runner_tree.heading("fair", text="Fair Odds")
        self.runner_tree.heading("pick", text="Pick")
        self.runner_tree.column("no", width=45, anchor="center")
        self.runner_tree.column("horse", width=280)
        self.runner_tree.column("market", width=160)
        self.runner_tree.column("fair", width=100, anchor="center")
        self.runner_tree.column("pick", width=80, anchor="center")
        self.runner_tree.grid(row=2, column=0, sticky="nsew")
        runner_scroll = ttk.Scrollbar(detail, orient="vertical", command=self.runner_tree.yview)
        runner_scroll.grid(row=2, column=1, sticky="ns")
        self.runner_tree.configure(yscrollcommand=runner_scroll.set)
        self.runner_tree.bind("<<TreeviewSelect>>", self._on_select_runner)

        btn_row = ttk.Frame(detail, style="Card.TFrame")
        btn_row.grid(row=3, column=0, sticky="ew", pady=(8, 6))
        ttk.Button(btn_row, text="Pick Highlighted Runner", command=self._pick_selected_runner, style="Gold.TButton").grid(row=0, column=0, sticky="w")

        guide = ttk.Frame(detail, style="Card.TFrame", padding=10)
        guide.grid(row=4, column=0, sticky="ew")
        ttk.Label(guide, text="Points Return Guide", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(guide, textvariable=self.dashboard_points_guide, style="Muted.TLabel", wraplength=620).grid(row=1, column=0, sticky="w", pady=(6, 0))

        return frame

    def _build_tables_page(self) -> ttk.Frame:
        frame = ttk.Frame(self.page_container, style="App.TFrame")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        top = ttk.Frame(frame, style="Card.TFrame", padding=10)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(top, text="Leaderboard", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(top, textvariable=self.table_header, style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Button(top, text="Refresh", command=self.refresh_all, style="Gold.TButton").grid(row=0, column=1, rowspan=2, padx=8)

        cols = ("rank", "player", "points", "wins", "placings", "dnfs")
        self.leaderboard_tree = ttk.Treeview(frame, columns=cols, show="headings")
        for col, text in zip(cols, ["Rank", "Player", "Total Points", "Wins", "Placings", "DNFs"]):
            self.leaderboard_tree.heading(col, text=text)
        self.leaderboard_tree.grid(row=1, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.leaderboard_tree.yview)
        scroll.grid(row=1, column=1, sticky="ns")
        self.leaderboard_tree.configure(yscrollcommand=scroll.set)

        self.leaderboard_tree.tag_configure("top1", background="#d5b46a", foreground="#1b1b1b")
        self.leaderboard_tree.tag_configure("top2", background="#b6b6b6", foreground="#1b1b1b")
        self.leaderboard_tree.tag_configure("top3", background="#c88b4a", foreground="#1b1b1b")
        return frame

    def _build_admin_page(self) -> ttk.Frame:
        frame = ttk.Frame(self.page_container, style="App.TFrame")
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(1, weight=1)

        top = ttk.Frame(frame, style="Card.TFrame", padding=10)
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        ttk.Label(top, text="Admin Controls", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")

        missing_card = ttk.Frame(frame, style="Card.TFrame", padding=10)
        missing_card.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        missing_card.columnconfigure(0, weight=1)
        missing_card.rowconfigure(1, weight=1)
        ttk.Label(missing_card, text="Missing Odds Queue", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        self.missing_list = tk.Listbox(missing_card, bg="#1a3428", fg="#efe8d0", selectbackground="#d5b46a")
        self.missing_list.grid(row=1, column=0, sticky="nsew", pady=(8, 6))
        row = ttk.Frame(missing_card, style="Card.TFrame")
        row.grid(row=2, column=0, sticky="ew")
        self.manual_odds_entry = ttk.Entry(row)
        self.manual_odds_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        row.columnconfigure(0, weight=1)
        ttk.Button(row, text="Apply Odds", command=self._apply_manual_odds, style="Gold.TButton").grid(row=0, column=1)

        result_card = ttk.Frame(frame, style="Card.TFrame", padding=10)
        result_card.grid(row=1, column=1, sticky="nsew")
        result_card.columnconfigure(1, weight=1)
        ttk.Label(result_card, text="Result Override", style="CardTitle.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")

        ttk.Label(result_card, text="Race", style="Muted.TLabel").grid(row=1, column=0, sticky="w")
        self.result_race_combo = ttk.Combobox(result_card, state="readonly")
        self.result_race_combo.grid(row=1, column=1, sticky="ew", pady=3)
        self.result_race_combo.bind("<<ComboboxSelected>>", self._refresh_result_runner_options)

        self.place_combos: list[ttk.Combobox] = []
        for idx in range(1, 5):
            ttk.Label(result_card, text=f"Place {idx}", style="Muted.TLabel").grid(row=idx + 1, column=0, sticky="w")
            cb = ttk.Combobox(result_card, state="readonly")
            cb.grid(row=idx + 1, column=1, sticky="ew", pady=3)
            self.place_combos.append(cb)

        ttk.Label(result_card, text="DNF Runner IDs (comma)", style="Muted.TLabel").grid(row=6, column=0, sticky="w")
        self.dnf_entry = ttk.Entry(result_card)
        self.dnf_entry.grid(row=6, column=1, sticky="ew", pady=3)

        self.official_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(result_card, text="Official", variable=self.official_var).grid(row=7, column=1, sticky="w")
        ttk.Button(result_card, text="Save Result", command=self._save_result_override, style="Gold.TButton").grid(row=8, column=1, sticky="e", pady=6)

        bottom = ttk.Frame(frame, style="Card.TFrame", padding=10)
        bottom.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        bottom.columnconfigure(3, weight=1)
        ttk.Button(bottom, text="Force Rescore", command=self._force_rescore, style="Gold.TButton").grid(row=0, column=0, padx=4)
        ttk.Button(bottom, text="Export Session JSON", command=self._export_json, style="Gold.TButton").grid(row=0, column=1, padx=4)
        ttk.Button(bottom, text="Toggle Selected Race Lock", command=self._toggle_race_lock, style="Gold.TButton").grid(row=0, column=2, padx=4)
        self.lock_race_combo = ttk.Combobox(bottom, state="readonly", width=24)
        self.lock_race_combo.grid(row=0, column=3, sticky="e")

        audit = ttk.Frame(frame, style="Card.TFrame", padding=10)
        audit.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(10, 0))
        audit.rowconfigure(1, weight=1)
        audit.columnconfigure(0, weight=1)
        ttk.Label(audit, text="Audit (last 10)", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        self.audit_text = tk.Text(audit, height=8, bg="#10261a", fg="#efe8d0")
        self.audit_text.grid(row=1, column=0, sticky="nsew", pady=(6, 0))

        return frame

    def _build_uploads_page(self) -> ttk.Frame:
        frame = ttk.Frame(self.page_container, style="App.TFrame")
        frame.columnconfigure(0, weight=1)

        card = ttk.Frame(frame, style="Card.TFrame", padding=14)
        card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        card.columnconfigure(0, weight=1)
        ttk.Label(card, text="Upload Excel Racecard (.xlsx)", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(card, textvariable=self.upload_status, style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 8))
        ttk.Button(card, text="Upload Excel Racecard (.xlsx)", command=self.upload_xlsx, style="Gold.TButton").grid(row=2, column=0, sticky="w")

        self.use_sample_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(card, text="Use sample JSON files instead of live API", variable=self.use_sample_var).grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Button(
            card,
            text="Load Southwell (GB) — 2026-03-02 from API",
            command=self.load_southwell_from_api,
            style="Gold.TButton",
        ).grid(row=4, column=0, sticky="w", pady=(8, 0))
        self.api_banner_var = tk.StringVar(value="")
        ttk.Label(card, textvariable=self.api_banner_var, style="Muted.TLabel").grid(row=5, column=0, sticky="w", pady=(6, 0))

        summary = ttk.Frame(frame, style="Card.TFrame", padding=12)
        summary.grid(row=1, column=0, sticky="ew")
        self.upload_summary_label = ttk.Label(summary, text="No upload summary available", style="Muted.TLabel", wraplength=980)
        self.upload_summary_label.grid(row=0, column=0, sticky="w")

        tools = ttk.Frame(frame, style="Card.TFrame", padding=12)
        tools.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(tools, text="Open Sessions Folder", command=self._open_sessions_folder, style="Gold.TButton").grid(row=0, column=0, padx=4)
        ttk.Button(tools, text="Export Current Session", command=self._export_json, style="Gold.TButton").grid(row=0, column=1, padx=4)

        self.create_players_panel(frame)

        return frame

    def create_players_panel(self, parent: ttk.Frame) -> None:
        panel = ttk.Frame(parent, style="Card.TFrame", padding=12)
        panel.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        panel.columnconfigure(0, weight=1)

        ttk.Label(panel, text="Players", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))

        entry_row = ttk.Frame(panel, style="Card.TFrame")
        entry_row.grid(row=1, column=0, sticky="ew")
        entry_row.columnconfigure(0, weight=1)

        self.player_name_entry = ttk.Entry(entry_row, textvariable=self.player_name_var)
        self.player_name_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.player_name_entry.bind("<FocusIn>", self._on_player_entry_focus_in)
        self.player_name_entry.bind("<FocusOut>", self._on_player_entry_focus_out)

        ttk.Button(entry_row, text="+ Add Player", bootstyle="success", command=self._on_add_player_clicked).grid(row=0, column=1)

        self.players_list_frame = ttk.Frame(panel, style="Card.TFrame")
        self.players_list_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.players_list_frame.columnconfigure(0, weight=1)

    def create_player_row(self, player: dict[str, Any], row_index: int) -> None:
        row = ttk.Frame(self.players_list_frame, style="Card.TFrame")
        row.grid(row=row_index, column=0, sticky="ew", pady=2)
        row.columnconfigure(0, weight=1)

        ttk.Label(row, text=player.get("name", "Unknown"), style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(
            row,
            text="Remove",
            bootstyle="danger-outline",
            command=lambda pid=player.get("player_id", ""): self.app.remove_player(pid),
        ).grid(row=0, column=1, sticky="e")

    def refresh_players(self) -> None:
        if not hasattr(self, "players_list_frame"):
            return
        for child in self.players_list_frame.winfo_children():
            child.destroy()

        session = self.app.session
        players = session.get("meeting", {}).get("players", []) if session else []
        if not players:
            ttk.Label(self.players_list_frame, text="No players yet", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
            return

        for idx, player in enumerate(players):
            self.create_player_row(player, idx)

    def _on_add_player_clicked(self) -> None:
        name = self.player_name_var.get().strip()
        if self._player_placeholder_active:
            name = ""
        if not name:
            return
        self.app.add_player(name)
        self.player_name_var.set("Player name")
        self._player_placeholder_active = True
        self.refresh_players()

    def _on_player_entry_focus_in(self, _event: Any) -> None:
        if self._player_placeholder_active:
            self.player_name_var.set("")
            self._player_placeholder_active = False

    def _on_player_entry_focus_out(self, _event: Any) -> None:
        if not self.player_name_var.get().strip():
            self.player_name_var.set("Player name")
            self._player_placeholder_active = True
    
    def _show_page(self, page_name: str) -> None:
        self.current_page = page_name
        for name, frame in self.pages.items():
            if name == page_name:
                frame.grid(row=0, column=0, sticky="nsew")
            else:
                frame.grid_forget()
        for name, btn in self.nav_buttons.items():
            btn.configure(text=f"• {name}" if name == page_name else name)

    def _set_day(self, day: int) -> None:
        self.day_filter = day
        self.refresh_dashboard()

    def upload_xlsx(self) -> None:
        if not self.app.config:
            return
        if self.app.session and not messagebox.askyesno("Replace session", "A session is already loaded. Replace it with Excel data?"):
            return
        path = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx")])
        if not path:
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Import Meeting")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.columnconfigure(1, weight=1)

        vals = {
            "meeting": tk.StringVar(value="Huntingdon Test"),
            "course": tk.StringVar(value="Huntingdon"),
            "date_local": tk.StringVar(value=date.today().isoformat()),
        }
        for idx, (key, var) in enumerate(vals.items()):
            ttk.Label(dialog, text=key.replace("_", " ").title()).grid(row=idx, column=0, sticky="w", padx=10, pady=6)
            ttk.Entry(dialog, textvariable=var).grid(row=idx, column=1, sticky="ew", padx=10, pady=6)

        status = ttk.Label(dialog, text="", foreground="#d5b46a")
        status.grid(row=3, column=0, columnspan=2, sticky="w", padx=10)

        def submit() -> None:
            try:
                status.configure(text="Importing racecard... please wait")
                dialog.update_idletasks()
                meeting, snapshot, warnings = import_racecard_xlsx(
                    path,
                    vals["meeting"].get(),
                    vals["course"].get(),
                    vals["date_local"].get(),
                    self.app.config,
                )
                self.app.start_new_session(meeting, snapshot)
                self.upload_summary = UploadSummary(
                    file_name=Path(path).name,
                    loaded_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    warnings=len(warnings),
                    meeting_text=f"{meeting['name']} ({meeting['course']}) {meeting['date_local']}",
                    races=len(meeting["races"]),
                    runners=sum(len(r["runners"]) for r in meeting["races"]),
                )
                self.upload_status.set(f"Last file: {self.upload_summary.file_name} at {self.upload_summary.loaded_at}")
                if warnings:
                    messagebox.showwarning("Import warnings", "\n".join(warnings[:8]))
                dialog.destroy()
                self.refresh_all()
            except Exception as exc:
                messagebox.showerror("Import failed", str(exc))

        ttk.Button(dialog, text="Import", command=submit, style="Gold.TButton").grid(row=4, column=1, sticky="e", padx=10, pady=10)

    def load_southwell_from_api(self) -> None:
        if self.app.session and not messagebox.askyesno("Replace session", "A session is already loaded. Replace it with API data?"):
            return
        self.app.load_southwell_from_api(use_sample=bool(getattr(self, "use_sample_var", tk.BooleanVar(value=False)).get()))

    def set_api_banner(self, text: str) -> None:
        if hasattr(self, "api_banner_var"):
            self.api_banner_var.set(text)

    def set_api_connected(self, connected: bool, last_sync_hhmm: str | None) -> None:
        self.chip_api.set("API: Connected" if connected else "API: Disconnected")
        self.chip_sync.set(f"Last Sync: {last_sync_hhmm}" if last_sync_hhmm else "Last Sync: --:--")

    def refresh_all(self) -> None:
        self._refresh_header()
        self._refresh_home()
        self.refresh_dashboard()
        self._refresh_tables()
        self._refresh_admin()
        self._refresh_uploads()
        self.refresh_players()

    def _selected_player_id(self) -> str | None:
        selected_name = self.current_player.get().strip()
        return self.player_name_to_id.get(selected_name)

    def _set_current_player_by_id(self, player_id: str | None) -> None:
        if not player_id:
            self.current_player.set("")
            return
        player_name = self.player_id_to_name.get(player_id, "")
        self.current_player.set(player_name)

    def _refresh_header(self) -> None:
        session = self.app.session
        if not session:
            self.meeting_badge.set("No meeting loaded")
            self.chip_racecard.set("Racecard: Not loaded")
            self.chip_odds.set("Odds: Awaiting")
            self.chip_picks.set("Picks: Open")
            self.chip_api.set("API: Disconnected")
            self.chip_sync.set("Last Sync: --:--")
            self.player_name_to_id = {}
            self.player_id_to_name = {}
            self.header_player_combo["values"] = []
            return

        meeting = session["meeting"]
        self.meeting_badge.set(f"{meeting['course']} • {meeting['date_local']}")
        self.chip_racecard.set("Racecard: Loaded")
        has_missing = any(rn["odds_status"] == "missing" for race in meeting["races"] for rn in race["runners"])
        self.chip_odds.set("Odds: Awaiting odds" if has_missing else "Odds: Ready")

        selected_race = self._selected_race()
        if selected_race and selected_race["locked"]:
            self.chip_picks.set("Picks: Locked")
        else:
            self.chip_picks.set("Picks: Open")

        if meeting.get("source") == "api" and getattr(self.app, "api_meta", None):
            self.chip_api.set("API: Connected")
            self.chip_sync.set(f"Last Sync: {self.app.api_meta.get('last_sync', '--:--')}")
        players = meeting.get("players", [])
        self.player_name_to_id = {p.get("name", p.get("player_id", "")): p.get("player_id", "") for p in players if p.get("player_id")}
        self.player_id_to_name = {pid: name for name, pid in self.player_name_to_id.items()}
        player_names = list(self.player_name_to_id.keys())
        self.header_player_combo["values"] = player_names
        if player_names and self.current_player.get() not in player_names:
            self.current_player.set(player_names[0])

    def _refresh_home(self) -> None:
        session = self.app.session
        for child in self.players_card.winfo_children()[1:]:
            child.destroy()
        if not session:
            self.home_next_race.set("No race loaded")
            self.home_meeting_summary.set("Load a racecard to begin")
            self.session_info_text.set("Session not loaded")
            self.my_pick_text.set("No pick selected")
            return

        meeting = session["meeting"]
        races = meeting["races"]
        settled = sum(1 for race in races if race["status"] == "settled")
        self.home_meeting_summary.set(f"Meeting {meeting['name']} • {len(races)} races")
        self.session_info_text.set(
            f"{meeting['course']} on {meeting['date_local']}\nRaces: {len(races)} | Runners: {sum(len(r['runners']) for r in races)} | Settled: {settled}"
        )

        next_race = self._next_race()
        if next_race:
            off = datetime.fromisoformat(next_race["scheduled_off_dt_utc"])
            now = datetime.now(ZoneInfo("UTC"))
            countdown = max(0, int((off - now).total_seconds()))
            self.home_next_race.set(f"{next_race['name']} ({next_race['off_time_local']}) • T-{countdown}s • {next_race['status']}")
        else:
            self.home_next_race.set("No upcoming race")

        player_map = {p["player_id"]: p.get("name", p["player_id"]) for p in meeting.get("players", [])}
        stats = {pid: {"points": 0.0, "wins": 0} for pid in player_map}
        for row in session.get("leaderboard", []):
            if row["player_id"] in stats:
                stats[row["player_id"]]["points"] = row["points"]
                stats[row["player_id"]]["wins"] = row["wins"]

        for r_idx, (pid, pname) in enumerate(player_map.items(), start=1):
            text = f"{pname}  • {stats[pid]['points']} pts • {stats[pid]['wins']} wins"
            ttk.Button(self.players_card, text=text, command=lambda p=pid: self._set_current_player_by_id(p)).grid(row=r_idx, column=0, sticky="ew", pady=2)

        race = self._selected_race() or next_race
        player_id = self._selected_player_id()
        if race and player_id:
            pick = next((p for p in session["picks"] if p["race_id"] == race["race_id"] and p["player_id"] == player_id), None)
            if pick:
                runner = next((r for r in race["runners"] if r["runner_id"] == pick["runner_id"]), None)
                self.my_pick_text.set(f"{race['name']}: {runner['horse_name'] if runner else pick['runner_id']}")
            else:
                self.my_pick_text.set(f"{race['name']}: No pick yet")

    def refresh_dashboard(self) -> None:
        session = self.app.session
        self.race_listbox.delete(0, tk.END)
        self.runner_tree.delete(*self.runner_tree.get_children())
        if not session:
            self.dashboard_race_title.set("Select a race")
            self.dashboard_points_guide.set("Select a runner to see projected returns")
            return

        races = sorted([r for r in session["meeting"]["races"] if int(r.get("day", 1)) == self.day_filter], key=lambda r: r["scheduled_off_dt_utc"])
        if not races:
            self.dashboard_race_title.set(f"Day {self.day_filter}: no races assigned")
            self.dashboard_points_guide.set("No runners available")
            return

        for race in races:
            pick_txt = self._picked_horse_text(race)
            self.race_listbox.insert(tk.END, f"{race['off_time_local']} | {race['name']} | {race['status']} | {pick_txt}")

        if not self.app.selected_race_id or all(r["race_id"] != self.app.selected_race_id for r in races):
            self.app.selected_race_id = races[0]["race_id"]
            self.selected_runner_id = None
            self.race_listbox.selection_set(0)

        self._refresh_selected_race_detail()

    def _refresh_selected_race_detail(self) -> None:
        race = self._selected_race()
        self.runner_tree.delete(*self.runner_tree.get_children())
        if not race:
            self.selected_runner_id = None
            self.dashboard_race_title.set("Select a race")
            self.race_state_label.configure(text="Picks Open")
            self.dashboard_points_guide.set("Select a runner to see projected returns")
            return

        self.dashboard_race_title.set(f"{race['name']} • {race['off_time_local']}")
        self.race_state_label.configure(text=("Picks Locked" if race["locked"] else "Picks Open"))
        current_player = self._selected_player_id()
        current_pick_id = None
        if current_player:
            pick = next((p for p in self.app.session["picks"] if p["race_id"] == race["race_id"] and p["player_id"] == current_player), None)
            current_pick_id = pick["runner_id"] if pick else None

        for runner in race["runners"]:
            market = runner["market_odds"] or "—"
            if runner["market_decimal"]:
                market = f"{market} ({runner['market_decimal']:.2f})"
            fair = "—" if runner["fair_decimal"] is None else f"{runner['fair_decimal']:.2f}"
            pick_state = "✓" if current_pick_id == runner["runner_id"] else "Pick"
            item_id = self.runner_tree.insert("", tk.END, iid=runner["runner_id"], values=(runner["number"], runner["horse_name"], market, fair, pick_state))
            tags: tuple[str, ...] = ()
            if runner["odds_status"] == "missing":
                tags = tags + ("missing",)
            if runner["runner_id"] == self.selected_runner_id:
                tags = tags + ("selected_runner",)
            if tags:
                self.runner_tree.item(item_id, tags=tags)

        self.runner_tree.tag_configure("missing", foreground="#f9b47a")
        self.runner_tree.tag_configure("selected_runner", background="#2d5f45", foreground="#f4e9c9")

        if self.selected_runner_id and self.runner_tree.exists(self.selected_runner_id):
            self.runner_tree.selection_set(self.selected_runner_id)
            self.runner_tree.focus(self.selected_runner_id)
            self.runner_tree.see(self.selected_runner_id)
            self._update_points_guide_for_runner(self.selected_runner_id)
        else:
            self.dashboard_points_guide.set("Select a runner to see projected returns")

    def _refresh_tables(self) -> None:
        session = self.app.session
        self.leaderboard_tree.delete(*self.leaderboard_tree.get_children())
        if not session:
            self.table_header.set("Live standings: 0 of 0 races settled")
            return
        races = session["meeting"]["races"]
        settled = sum(1 for race in races if race["status"] == "settled")
        self.table_header.set(f"{session['meeting']['name']} • Live standings: {settled} of {len(races)} races settled")

        for row in session.get("leaderboard", []):
            tag = ""
            if row["rank"] == 1:
                tag = "top1"
            elif row["rank"] == 2:
                tag = "top2"
            elif row["rank"] == 3:
                tag = "top3"
            self.leaderboard_tree.insert("", tk.END, values=(row["rank"], row["player_name"], row["points"], row["wins"], row["placings"], row["dnfs"]), tags=(tag,))

    def _refresh_admin(self) -> None:
        session = self.app.session
        self.missing_list.delete(0, tk.END)
        self.audit_text.delete("1.0", tk.END)
        if not session:
            self.result_race_combo["values"] = []
            self.lock_race_combo["values"] = []
            return

        race_ids = [r["race_id"] for r in session["meeting"]["races"]]
        self.result_race_combo["values"] = race_ids
        self.lock_race_combo["values"] = race_ids

        for race in session["meeting"]["races"]:
            for runner in race["runners"]:
                if runner["odds_status"] == "missing":
                    self.missing_list.insert(tk.END, f"{race['race_id']}|{runner['runner_id']}|{runner['horse_name']}")

        meeting_id = session["meeting"]["meeting_id"]
        for row in read_audit(meeting_id, limit=10):
            self.audit_text.insert(tk.END, f"{row['at_utc']} | {row['actor']} | {row['action']} | {row['payload']}\n")

    def _refresh_uploads(self) -> None:
        if not self.upload_summary.file_name:
            self.upload_summary_label.configure(text="No upload summary available")
            return
        self.upload_summary_label.configure(
            text=(
                f"Meeting: {self.upload_summary.meeting_text}\n"
                f"Races loaded: {self.upload_summary.races} | Runners loaded: {self.upload_summary.runners}\n"
                f"Warnings: {self.upload_summary.warnings} | File: {self.upload_summary.file_name} @ {self.upload_summary.loaded_at}"
            )
        )

    def _on_select_race(self, _event: Any) -> None:
        session = self.app.session
        if not session:
            return
        selection = self.race_listbox.curselection()
        if not selection:
            return
        races = sorted([r for r in session["meeting"]["races"] if int(r.get("day", 1)) == self.day_filter], key=lambda r: r["scheduled_off_dt_utc"])
        if selection[0] < len(races):
            new_race_id = races[selection[0]]["race_id"]
            if new_race_id != self.app.selected_race_id:
                self.selected_runner_id = None
            self.app.selected_race_id = new_race_id
            self._refresh_selected_race_detail()
            self._refresh_header()
            self._refresh_home()

    def _on_select_runner(self, _event: Any) -> None:
        selection = self.runner_tree.selection()
        if not selection:
            return
        self.selected_runner_id = selection[0]
        self._update_points_guide_for_runner(self.selected_runner_id)

    def _update_points_guide_for_runner(self, runner_id: str) -> None:
        race = self._selected_race()
        if not race:
            return
        runner = next((r for r in race["runners"] if r["runner_id"] == runner_id), None)
        if not runner or runner["odds_status"] == "missing":
            self.dashboard_points_guide.set("Missing odds for this runner. Projections hidden until odds are supplied.")
            return

        paid = paid_places_for_field_size(len(race["runners"]), self.app.config)
        base_win = self.app.config["scoring"]["base_points"]["win"]
        base_place = self.app.config["scoring"]["base_points"]["place"]
        win_points = base_win * (float(runner["fair_decimal"]) ** 0.5)
        place_points = base_place * (float(runner["place_decimal_fair"]) ** 0.5)
        dnf_penalty = self.app.config["scoring"]["dnf_penalty"]["points"]
        lines = [
            f"Runner: {runner['horse_name']}",
            f"Projected Win: {win_points:.2f} pts",
            f"Projected Place (paid positions 2-{paid}): {place_points:.2f} pts",
            f"DNF: {dnf_penalty:+.0f} pts (unmultiplied)",
        ]
        self.dashboard_points_guide.set("\n".join(lines))

    def _pick_selected_runner(self) -> None:
        session = self.app.session
        race = self._selected_race()
        player_id = self._selected_player_id()
        if not session or not race or not player_id:
            return
        if race["locked"]:
            messagebox.showwarning("Race Locked", "Picks are locked for this race.")
            return
        selection = self.runner_tree.selection()
        if not selection:
            return
        runner_id = selection[0]

        for pick in list(session["picks"]):
            if pick["race_id"] == race["race_id"] and pick["player_id"] == player_id:
                session["picks"].remove(pick)
        session["picks"].append(
            {
                "pick_id": f"pick_{race['race_id']}_{player_id}",
                "meeting_id": session["meeting"]["meeting_id"],
                "race_id": race["race_id"],
                "player_id": player_id,
                "runner_id": runner_id,
                "locked": False,
                "picked_at_utc": datetime.now(ZoneInfo("UTC")).isoformat(),
            }
        )
        append_audit(session["meeting"]["meeting_id"], player_id, "pick", {"race_id": race["race_id"], "runner_id": runner_id})
        save_session(session)
        self._refresh_after_pick(runner_id)

    def _refresh_after_pick(self, runner_id: str) -> None:
        self.selected_runner_id = runner_id
        self._refresh_header()
        self._refresh_home()
        self._refresh_tables()
        self._refresh_runner_pick_marks()
        if self.runner_tree.exists(runner_id):
            self.runner_tree.selection_set(runner_id)
            self.runner_tree.focus(runner_id)
            self.runner_tree.see(runner_id)
            self._update_points_guide_for_runner(runner_id)

    def _refresh_runner_pick_marks(self) -> None:
        race = self._selected_race()
        session = self.app.session
        if not race or not session:
            return
        player_id = self._selected_player_id()
        current_pick_id = None
        if player_id:
            pick = next((p for p in session["picks"] if p["race_id"] == race["race_id"] and p["player_id"] == player_id), None)
            current_pick_id = pick["runner_id"] if pick else None
        for runner in race["runners"]:
            rid = runner["runner_id"]
            if not self.runner_tree.exists(rid):
                continue
            vals = list(self.runner_tree.item(rid, "values"))
            if len(vals) >= 5:
                vals[4] = "✓" if current_pick_id == rid else "Pick"
                self.runner_tree.item(rid, values=tuple(vals))

    def _apply_manual_odds(self) -> None:
        session = self.app.session
        if not session:
            return
        sel = self.missing_list.curselection()
        if not sel:
            return
        race_id, runner_id, _horse = self.missing_list.get(sel[0]).split("|", 2)
        dec = parse_odds_to_decimal(self.manual_odds_entry.get().strip())
        if not dec:
            messagebox.showerror("Invalid Odds", "Use fractional (e.g. 9/4) or decimal > 1.")
            return
        race = next(r for r in session["meeting"]["races"] if r["race_id"] == race_id)
        runner = next(r for r in race["runners"] if r["runner_id"] == runner_id)
        runner["market_odds"] = self.manual_odds_entry.get().strip()
        runner["market_decimal"] = dec
        recompute_fair_odds_for_race(race, self.app.config)
        if race["status"] == "awaiting_odds":
            race["status"] = "open"
        append_audit(session["meeting"]["meeting_id"], "admin", "manual_odds_entry", {"runner_id": runner_id, "odds": runner["market_odds"]})
        save_session(session)
        self.refresh_all()

    def _refresh_result_runner_options(self, _event: Any = None) -> None:
        session = self.app.session
        if not session:
            return
        race_id = self.result_race_combo.get()
        race = next((r for r in session["meeting"]["races"] if r["race_id"] == race_id), None)
        values = [""]
        if race:
            values.extend([f"{rn['runner_id']} | {rn['horse_name']}" for rn in race["runners"]])
        for combo in self.place_combos:
            combo["values"] = values

    def _save_result_override(self) -> None:
        session = self.app.session
        if not session:
            return
        race_id = self.result_race_combo.get()
        if not race_id:
            return
        race = next(r for r in session["meeting"]["races"] if r["race_id"] == race_id)

        if self.official_var.get() and race["rescore_count"] >= self.app.config["settlement"]["max_rescore_count"]:
            messagebox.showwarning("Rescore limit", "Max official rescore count reached.")
            return

        placements = []
        for cb in self.place_combos:
            val = cb.get().strip()
            placements.append(val.split(" | ")[0] if val else "")
        dnf_ids = [item.strip() for item in self.dnf_entry.get().split(",") if item.strip()]
        status = "official" if self.official_var.get() else "provisional"

        race["results"] = {
            "result_id": f"res_{race_id}",
            "race_id": race_id,
            "status": status,
            "placements": placements,
            "dnf_runner_ids": dnf_ids,
            "is_official": self.official_var.get(),
            "updated_at_utc": datetime.now(ZoneInfo("UTC")).isoformat(),
        }
        race["status"] = "settling"
        blocked = any(
            rid and next((r for r in race["runners"] if r["runner_id"] == rid and r["odds_status"] == "missing"), None)
            for rid in placements
        )
        race["status"] = "awaiting_odds" if blocked else "settled"
        if self.official_var.get():
            race["rescore_count"] += 1

        rescore_session(session, self.app.config)
        append_audit(session["meeting"]["meeting_id"], "admin", "result_override", {"race_id": race_id, "placements": placements, "dnf_ids": dnf_ids, "status": status})
        save_session(session)
        self.refresh_all()

    def _force_rescore(self) -> None:
        if not self.app.session:
            return
        if not messagebox.askyesno("Force rescore", "Recompute leaderboard now?"):
            return
        rescore_session(self.app.session, self.app.config)
        append_audit(self.app.session["meeting"]["meeting_id"], "admin", "force_rescore", {})
        save_session(self.app.session)
        self.refresh_all()

    def _toggle_race_lock(self) -> None:
        session = self.app.session
        if not session:
            return
        race_id = self.lock_race_combo.get()
        if not race_id:
            return
        race = next(r for r in session["meeting"]["races"] if r["race_id"] == race_id)
        race["locked"] = not race["locked"]
        race["status"] = "locked" if race["locked"] else "open"
        for pick in session["picks"]:
            if pick["race_id"] == race_id:
                pick["locked"] = race["locked"]
        append_audit(session["meeting"]["meeting_id"], "admin", "race_lock_override", {"race_id": race_id, "locked": race["locked"]})
        save_session(session)
        self.refresh_all()

    def _export_json(self) -> None:
        if not self.app.session:
            return
        path = export_session(self.app.session)
        messagebox.showinfo("Exported", str(path))

    def _open_sessions_folder(self) -> None:
        folder = SESSIONS.resolve()
        folder.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(str(folder))
            elif os.name == "posix":
                subprocess.Popen(["xdg-open", str(folder)])
        except Exception:
            messagebox.showinfo("Sessions folder", str(folder))

    def _selected_race(self) -> dict[str, Any] | None:
        session = self.app.session
        if not session or not self.app.selected_race_id:
            return None
        return next((r for r in session["meeting"]["races"] if r["race_id"] == self.app.selected_race_id), None)

    def _next_race(self) -> dict[str, Any] | None:
        session = self.app.session
        if not session:
            return None
        now = datetime.now(ZoneInfo("UTC"))
        upcoming = [r for r in session["meeting"]["races"] if datetime.fromisoformat(r["scheduled_off_dt_utc"]) >= now]
        if not upcoming:
            return None
        return sorted(upcoming, key=lambda r: r["scheduled_off_dt_utc"])[0]

    def _picked_horse_text(self, race: dict[str, Any]) -> str:
        session = self.app.session
        player_id = self._selected_player_id()
        if not session or not player_id:
            return "No pick"
        pick = next((p for p in session["picks"] if p["race_id"] == race["race_id"] and p["player_id"] == player_id), None)
        if not pick:
            return "No pick"
        runner = next((r for r in race["runners"] if r["runner_id"] == pick["runner_id"]), None)
        return f"Picked: {runner['horse_name']}" if runner else "Picked"
