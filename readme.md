# Fantasy Furlong

Fantasy Furlong has **three parts**:

1. **Backend API (FastAPI)** — the only service that talks to TheRacingAPI.
2. **Web app (React + Vite PWA)** — player/admin browser UI.
3. **Desktop app (Tkinter)** — local operator/admin UI.

> ✅ Rule of thumb: **start backend first, then frontend**.

---

## Quick Start (copy/paste)

### 0) Prerequisites

- Python **3.10+**
- Node.js **18+**
- npm

### 1) Add Racing API credentials

Create `secrets/racingapi.env`:

```env
RACING_API_USERNAME=your_username
RACING_API_PASSWORD=your_password
```

### 2) Install backend deps

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell equivalent:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3) Run backend (keep this terminal open)

```bash
python -m uvicorn backend_api:app --host 0.0.0.0 --port 8000
```

Check backend health:

- <http://localhost:8000/health>

### 4) Install frontend deps

Open a **second terminal** in project root:

```bash
npm install
```

### 5) Run frontend (keep this second terminal open)

```bash
npm run dev
```

Open the URL shown as **Local** by Vite (expected: <http://localhost:5173>).

You should see a terminal line like `Local: http://localhost:5173/` before opening the browser.
If you do **not** see that line, the frontend is not running yet.

---

## Start commands (at a glance)

### Backend

```bash
python -m uvicorn backend_api:app --host 0.0.0.0 --port 8000
```

### Web app

```bash
npm run dev
```

### Desktop app

```bash
python furlong_desktop_app.py
```

---

## What runs where

### Backend (`backend_api.py`)

Main endpoints:

- `/health`
- `/api/meeting`
- `/api/races`
- `/api/picks`
- `/api/users`
- `/api/leaderboard`
- `/api/admin/*`

Responsibilities:

- pulls racecards/results from TheRacingAPI
- normalizes vendor payloads into canonical app session data
- computes odds/scoring projections
- caches shared snapshot for all clients

### Web app (`src/`)

- Router: `src/app/routes.tsx`
- Layout shell: `src/app/components/Layout.tsx`
- API client: `src/app/api/client.tsx`

Dev proxy forwards `/api` and `/health` to `http://127.0.0.1:8000`.

### Desktop app

- Entry point: `furlong_desktop_app.py`

---

## Most-used commands

### Run tests

```bash
pytest tests/test_sqrt_scoring.py
```

### Build + preview frontend

```bash
npm run build
npm run preview
```

### Session ID migration help

```bash
python migrate_session_ids.py --help
```

---

## Environment variables

Core:

- `FF_TARGET_COURSE` (default: `Exeter`)
- `FF_REFRESH_SECONDS` (default: `60`)
- `FF_RACECARD_DAY` (default: `tomorrow`)
- `FF_ADMIN_PASSWORD` (admin login password)
- `FF_ADMIN_SECRET` (cookie signing secret)

Optional tuning:

- `FF_FESTIVAL_MODE`
- `FF_FESTIVAL_LENGTH_HOURS`
- `FF_COURSES_TTL_SECONDS`
- `FF_RACECARDS_TTL_SECONDS`
- `FF_RESULTS_TTL_SECONDS`

---


## Railway deployment (single service)

This project is wired for a **single Railway public service**:
- FastAPI serves `/api/*` + `/health`
- FastAPI also serves the built Vite app from `dist/`

### Config
- `railway.toml` defines:
  - build: `pip install -r requirements.txt && npm install && npm run build`
  - start: `python -m uvicorn backend_api:app --host 0.0.0.0 --port $PORT`
  - healthcheck: `/health`

### Required env vars
- `RACING_API_USERNAME`
- `RACING_API_PASSWORD`
- `FF_ADMIN_PASSWORD`
- `FF_ADMIN_SECRET`

### Persistent volume
Mount a Railway volume to:
- `/app/data`

This preserves app state files such as:
- `data/racedays.json`
- `data/invites.json`
- `data/web/users.json`
- `data/admin_state.json`

### Post-deploy smoke checks
- `https://<your-app>.up.railway.app/health`
- `https://<your-app>.up.railway.app/api/meeting`
- `https://<your-app>.up.railway.app/api/races`
- `https://<your-app>.up.railway.app/`
- `https://<your-app>.up.railway.app/join?token=...`

## Troubleshooting

### `http://localhost:5173` shows 404

This means something is responding on port 5173, but it is **not** your Vite app.

- Keep backend terminal and frontend terminal separate.
- In frontend terminal, run `npm run dev` and confirm it prints `Local: http://localhost:5173/`.
- If Vite reports `Port 5173 is already in use`, stop the other process on 5173 and run again.
- If you only started backend, use <http://localhost:8000/health> (backend), not 5173 (frontend).

### Frontend shows API errors

- Make sure backend is running on port 8000.
- Check <http://localhost:8000/health>.

### Backend says credentials are missing

- Ensure `secrets/racingapi.env` exists.
- Ensure both username and password keys are present and non-empty.

### Vendor/rate-limit issues

- Backend serves cached/stale snapshot when possible.
- Check `/health` response for cache/vendor stats.

---

## Reference files

> Note: This README was intentionally touched in a follow-up pass to force visible file-sync for downstream tooling.

- `Master_config_V1.txt`
- `rules_config_vNext.json`
- `API_ARCHITECTURE_BRIEF.md`
- `ARCHITECTURE_LOCK_v1.0.md`
- `data/`

> Sync note: this README line exists so downstream tools that only surface modified files can refresh project visibility.

> Sync heartbeat: README touched intentionally to trigger downstream file visibility refresh.

> Sync heartbeat 2: additional no-op README touch for file replacement workflows.
