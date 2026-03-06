"""Loader for Master_config_V1.txt."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


class MasterConfigError(RuntimeError):
    """Raised when master config cannot be parsed."""


def _parse_json_block(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    if text[0] == "{" and text[-1] == "}":
        return json.loads(text)
    return None


def _parse_env_file(path: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    if not path.exists():
        return parsed
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        parsed[key.strip()] = value.strip().strip('"').strip("'")
    return parsed


def load_racing_api_credentials(base_dir: Path, config: dict[str, Any] | None = None) -> tuple[str | None, str | None, str]:
    """Load RacingAPI credentials from env and secrets files, then export to os.environ."""
    env_user = os.getenv("RACING_API_USERNAME")
    env_pass = os.getenv("RACING_API_PASSWORD")
    if env_user and env_pass:
        return env_user, env_pass, "env"

    candidate_paths: list[Path] = []
    cfg = config or {}
    cfg_secret = cfg.get("racingapi_secrets_path") or cfg.get("api_secrets_path")
    if cfg_secret:
        candidate_paths.append((base_dir / str(cfg_secret)).resolve())

    candidate_paths.extend(
        [
            base_dir / ".env",
            base_dir / ".env.local",
            base_dir / "secrets" / "racingapi.env",
            base_dir / "secrets" / "racingapi.txt",
        ]
    )

    seen: set[Path] = set()
    for path in candidate_paths:
        real = path.resolve()
        if real in seen:
            continue
        seen.add(real)
        vals = _parse_env_file(real)
        user = vals.get("RACING_API_USERNAME") or env_user
        pwd = vals.get("RACING_API_PASSWORD") or env_pass
        # Load optional backend secrets from the same env source when present.
        for opt in ("FF_ADMIN_SECRET", "FF_ADMIN_PASSWORD", "FF_ADMIN_PASSWORD_HASH"):
            if vals.get(opt) and not os.getenv(opt):
                os.environ[opt] = vals[opt]
        if user and pwd:
            os.environ["RACING_API_USERNAME"] = user
            os.environ["RACING_API_PASSWORD"] = pwd
            try:
                source = str(real.relative_to(base_dir.resolve()))
            except Exception:
                source = str(real)
            return user, pwd, source

    return env_user, env_pass, "missing"


def load_master_config(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        raise MasterConfigError(f"Master config not found: {file_path}")

    raw = file_path.read_text(encoding="utf-8")

    as_json = _parse_json_block(raw)
    if as_json is not None:
        return as_json

    # Lightweight key: value parser with a few nested sections.
    config: dict[str, Any] = {
        "id": "master_config_v1",
        "timezone": "Europe/London",
        "internal_dp": 6,
        "display_dp": 2,
        "odds": {"no_default_odds_1_0": True, "place_divisor": 4, "win_multiplier": {"type": "sqrt"}, "place_multiplier": {"type": "sqrt"}},
        "scoring": {
            "base_points": {"win": 10, "place": 6},
            "powers": {"win": 1.0, "place": 1.0},
            "dnf_penalty": {"points": -2, "multiplied": False},
            "rounding": {"mode": "half_up", "dp": 2},
        },
        "paid_places": [{"min": 1, "max": 4, "places": 1}, {"min": 5, "max": 7, "places": 2}, {"min": 8, "max": 99, "places": 3}],
        "settlement": {"allow_one_rescore": True, "max_rescore_count": 1},
        "admin_panels": [
            "missing_odds_queue",
            "manual_odds_entry",
            "race_lock_override",
            "result_override",
            "force_rescore",
            "audit_log",
        ],
    }

    # Extract simple overrides from plain text.
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        kv = re.match(r"^([a-zA-Z0-9_.-]+)\s*[:=]\s*(.+)$", line)
        if not kv:
            continue
        key, value = kv.group(1).lower(), kv.group(2).strip()
        if key in {"timezone", "id", "racingapi_secrets_path", "api_secrets_path"}:
            config[key] = value
        elif key == "internal_dp":
            config["internal_dp"] = int(value)
        elif key == "display_dp":
            config["display_dp"] = int(value)
        elif key in {"place_divisor", "divisor"}:
            config["odds"]["place_divisor"] = float(value)

    required_top = ["timezone", "scoring", "odds", "paid_places", "settlement"]
    missing = [k for k in required_top if k not in config]
    if missing:
        raise MasterConfigError(f"Master config missing required sections: {missing}")
    return config
