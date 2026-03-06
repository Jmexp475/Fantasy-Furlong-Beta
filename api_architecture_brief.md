# Fantasy Furlong API Architecture Brief (GPT Thread Format)

## 1) What the architecture is doing today

### Core principle
- **Only the backend calls TheRacingAPI**.
- Players (PWA clients) call **our backend endpoints** (`/api/meeting`, `/api/races`, `/api/picks`, `/api/leaderboard`) and never call TheRacingAPI directly.

### Runtime components
- `backend_api.py` runs a FastAPI service plus a background refresh thread.
- `theracingapi_client.py` performs outbound HTTP calls to TheRacingAPI.
- `theracingapi_adapter.py` converts vendor payloads into one canonical app session model.
- `engine.py` computes fair odds + scoring from canonical session data.
- `storage.py` persists snapshots and web-facing data files.

### Data flow (high level)
1. Backend refresh thread triggers on interval (configured by `FF_REFRESH_SECONDS`).
2. Backend fetches racecards/results from TheRacingAPI using a shared client.
3. Adapter normalizes payload into canonical session structure.
4. Engine recomputes fair odds and scoring-ready fields.
5. Backend stores this in memory cache (`AppState._cache`) and disk snapshots.
6. All players read this same latest backend snapshot via `/api/*` routes.

---

## 2) How API calling currently works

### Outbound calling to TheRacingAPI
- A single shared server-side client is used.
- Calls are throttled (`MIN_REQUEST_INTERVAL_SECONDS`) to avoid rate-limit spikes.
- Calls have retries (`MAX_RETRIES`) for transient errors.
- Calls are cached in-process with TTL (`CACHE_TTL_SECONDS`) keyed by request path + params.

### Inbound calling from players
- Every player device requests backend endpoints only.
- Backend returns current server snapshot in memory (`meeting`, `races`, etc.).
- This already creates a **standard most recent pull** model:
  - one backend refresh,
  - many player reads,
  - no fan-out of vendor API calls per player.

---

## 3) Desired cache model (player-safe, low-call architecture)

### Goal
> “Don’t let each player trigger new vendor API calls. Keep a standard most recent pull everyone can reuse for a period.”

### Recommended model

#### A) Source API cache (server -> TheRacingAPI)
- Keep server-side request cache per endpoint (`courses`, `racecards`, `results`).
- Use endpoint-aware TTLs:
  - `courses`: long TTL (e.g., 24h)
  - `racecards`: short TTL (e.g., 30–120s during active windows)
  - `results`: short TTL (e.g., 30–60s near race completion)
- Keep retries + throttling in place.

#### B) Canonical snapshot cache (server -> players)
- Maintain one authoritative `latest_snapshot` in backend memory and disk.
- Include metadata on every read response:
  - `generated_at_utc`
  - `source_age_seconds`
  - `stale` (bool)
- All players read this same snapshot until next scheduled refresh.

#### C) Optional per-route response cache
- Cache rendered route payloads (`/api/races`, `/api/leaderboard`) for a short period (e.g., 5–15s).
- Invalidate route cache when new canonical snapshot is written.

---

## 4) Why this prevents “one call per player”

- Players never hit TheRacingAPI.
- Backend does controlled periodic pulls.
- The newest backend snapshot is shared by all players.
- Even at high concurrent load, player requests read cached backend state, not source API.

---

## 5) Operational notes for GPT/engineering thread

- Treat backend refresh loop as the **single source-of-truth fetcher**.
- Use cache TTL tuning by endpoint, not one blanket TTL for everything.
- Keep cache observability via stats endpoint (hits/misses/size/last_refresh/last_error).
- Preserve graceful degradation:
  - if vendor fails temporarily, continue serving last good snapshot with `stale=true`.

---

## 6) Implementation-ready acceptance criteria

1. Multiple players refreshing the app do **not** increase outbound TheRacingAPI calls linearly.
2. Backend exposes latest shared snapshot timestamp and staleness.
3. Cache hit ratio remains high under normal player load.
4. If TheRacingAPI is unavailable, players still receive last successful snapshot.
5. Refresh interval + TTLs are configurable via environment/config.
