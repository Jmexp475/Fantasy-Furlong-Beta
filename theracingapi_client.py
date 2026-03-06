"""HTTP client for TheRacingAPI Standard plan with shared throttling/cache."""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import requests
from requests.auth import HTTPBasicAuth


DEBUG_API = os.getenv("DEBUG_API", "0") == "1"
FESTIVAL_MODE = os.getenv("FF_FESTIVAL_MODE", "1") == "1"
FESTIVAL_LENGTH_HOURS = int(os.getenv("FF_FESTIVAL_LENGTH_HOURS", "96"))
COURSES_TTL_SECONDS = int(os.getenv("FF_COURSES_TTL_SECONDS", str(96 * 60 * 60)))
RACECARDS_TTL_SECONDS = int(os.getenv("FF_RACECARDS_TTL_SECONDS", "120"))
RESULTS_TTL_SECONDS = int(os.getenv("FF_RESULTS_TTL_SECONDS", "60"))
MIN_REQUEST_INTERVAL_SECONDS = 1.1
MAX_RETRIES = 3


class TheRacingApiError(RuntimeError):
    """Raised when API requests fail."""


class TheRacingApiRequestError(TheRacingApiError):
    """Rich API request failure used by callers for status handling."""

    def __init__(
        self,
        *,
        method: str,
        path: str,
        status_code: int | None,
        body_snippet: str,
        exc_type: str,
        message: str,
    ) -> None:
        self.method = method
        self.path = path
        self.status_code = status_code
        self.body_snippet = body_snippet
        self.exc_type = exc_type
        super().__init__(message)


@dataclass
class _CacheEntry:
    payload: Any
    fetched_at: float
    expires_at: float


_CACHE_LOCK = threading.Lock()
_CACHE: dict[str, _CacheEntry] = {}
_CACHE_HITS = 0
_CACHE_MISSES = 0

_VENDOR_LOCK = threading.Lock()
_VENDOR_TOTAL_CALLS = 0
_VENDOR_CALLS_BY_ENDPOINT: dict[str, int] = {}
_VENDOR_LAST_CALL_AT: str | None = None

_THROTTLE_LOCK = threading.Lock()
_LAST_REQUEST_TS = 0.0


def set_runtime_endpoint_ttls(*, racecards_ttl: int | None = None, results_ttl: int | None = None) -> None:
    global RACECARDS_TTL_SECONDS, RESULTS_TTL_SECONDS
    if racecards_ttl is not None:
        RACECARDS_TTL_SECONDS = int(racecards_ttl)
    if results_ttl is not None:
        RESULTS_TTL_SECONDS = int(results_ttl)


def _ttl_by_endpoint(endpoint: str) -> int:
    path = endpoint.lstrip("/")
    if path.startswith("courses"):
        return COURSES_TTL_SECONDS
    if path.startswith("racecards"):
        return RACECARDS_TTL_SECONDS
    if path.startswith("results"):
        return RESULTS_TTL_SECONDS
    return COURSES_TTL_SECONDS if FESTIVAL_MODE else RACECARDS_TTL_SECONDS


def _cache_key(method: str, path: str, params: dict[str, Any] | None) -> str:
    pairs: list[tuple[str, str]] = []
    for k in sorted((params or {}).keys()):
        val = (params or {})[k]
        if isinstance(val, (list, tuple)):
            for item in val:
                pairs.append((str(k), str(item)))
        else:
            pairs.append((str(k), str(val)))
    query = urlencode(pairs, doseq=True)
    return f"{method.upper()}:{path}?{query}"


def cache_purge_expired() -> int:
    now = time.time()
    purged = 0
    with _CACHE_LOCK:
        dead = [k for k, v in _CACHE.items() if v.expires_at <= now]
        for k in dead:
            del _CACHE[k]
            purged += 1
    return purged


def cache_get(key: str, *, allow_stale: bool = False) -> Any | None:
    global _CACHE_HITS, _CACHE_MISSES
    now = time.time()
    with _CACHE_LOCK:
        entry = _CACHE.get(key)
        if not entry:
            _CACHE_MISSES += 1
            return None
        if entry.expires_at <= now and not allow_stale:
            del _CACHE[key]
            _CACHE_MISSES += 1
            return None
        _CACHE_HITS += 1
        return entry.payload


def cache_set(key: str, value: Any, ttl_seconds: int) -> None:
    now = time.time()
    with _CACHE_LOCK:
        _CACHE[key] = _CacheEntry(payload=value, fetched_at=now, expires_at=now + ttl_seconds)


def cache_clear() -> int:
    with _CACHE_LOCK:
        count = len(_CACHE)
        _CACHE.clear()
        return count


def cache_stats() -> dict[str, Any]:
    with _CACHE_LOCK:
        return {
            "hits": _CACHE_HITS,
            "misses": _CACHE_MISSES,
            "size": len(_CACHE),
            "ttl_by_endpoint": {
                "courses": COURSES_TTL_SECONDS,
                "racecards": RACECARDS_TTL_SECONDS,
                "results": RESULTS_TTL_SECONDS,
            },
        }


def vendor_call_stats() -> dict[str, Any]:
    with _VENDOR_LOCK:
        return {
            "total_calls": _VENDOR_TOTAL_CALLS,
            "calls_by_endpoint": dict(_VENDOR_CALLS_BY_ENDPOINT),
            "last_call_at": _VENDOR_LAST_CALL_AT,
        }


def _record_vendor_call(endpoint: str) -> None:
    global _VENDOR_TOTAL_CALLS, _VENDOR_LAST_CALL_AT
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with _VENDOR_LOCK:
        _VENDOR_TOTAL_CALLS += 1
        _VENDOR_CALLS_BY_ENDPOINT[endpoint] = _VENDOR_CALLS_BY_ENDPOINT.get(endpoint, 0) + 1
        _VENDOR_LAST_CALL_AT = now


def _throttle() -> None:
    global _LAST_REQUEST_TS
    with _THROTTLE_LOCK:
        now = time.monotonic()
        wait = MIN_REQUEST_INTERVAL_SECONDS - (now - _LAST_REQUEST_TS)
        if wait > 0:
            time.sleep(wait)
        _LAST_REQUEST_TS = time.monotonic()


class TheRacingApiClient:
    def __init__(self, username: str, password: str, base_url: str = "https://api.theracingapi.com/v1") -> None:
        if not username or not password:
            raise RuntimeError("Missing Racing API credentials. Set env vars or create secrets/racingapi.env")
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(username, password)
        if DEBUG_API:
            print(f"[API DEBUG] base_url={self.base_url}")

    def request_json(self, path: str, params: dict[str, Any] | None = None, *, force_refresh: bool = False) -> dict[str, Any] | list[Any]:
        cache_purge_expired()
        endpoint = f"/{path.lstrip('/')}"
        url = f"{self.base_url}{endpoint}"
        query = f"?{urlencode(params or {}, doseq=True)}" if params else ""
        method = "GET"
        key = _cache_key(method, endpoint, params)
        ttl = _ttl_by_endpoint(endpoint)

        allow_stale = endpoint.lstrip("/").startswith("courses")
        if not force_refresh:
            cached = cache_get(key, allow_stale=allow_stale)
            if cached is not None:
                return cached

        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                _throttle()
                _record_vendor_call(endpoint)
                response = self.session.get(url, params=params, timeout=(5, 20))
                response.raise_for_status()
                payload = response.json()
                cache_set(key, payload, ttl_seconds=ttl)
                return payload
            except Exception as exc:
                last_error = exc
                status = getattr(getattr(exc, "response", None), "status_code", None)
                body = ""
                resp = getattr(exc, "response", None)
                if resp is not None and getattr(resp, "text", None):
                    body = str(resp.text)[:300].replace("\n", " ")
                print(f"[API ERROR] {method} {endpoint}{query} status={status} body=\"{body}\" exc={type(exc).__name__}: {exc}")

                is_429 = status == 429
                retriable = isinstance(exc, requests.exceptions.RequestException) and status in {None, 408, 425, 429, 500, 502, 503, 504}
                if retriable and attempt < MAX_RETRIES - 1:
                    time.sleep(1.5 if is_429 else 1.2 * (attempt + 1))
                    continue

                if allow_stale:
                    stale = cache_get(key, allow_stale=True)
                    if stale is not None:
                        return stale

                err = TheRacingApiRequestError(
                    method=method,
                    path=f"{endpoint}{query}",
                    status_code=status,
                    body_snippet=body,
                    exc_type=type(exc).__name__,
                    message=f"API request failed for {endpoint}: {type(exc).__name__}: {exc}",
                )
                raise err
        assert last_error is not None
        raise TheRacingApiError(f"API request failed: {last_error}")

    def list_courses(self, region_codes: list[str] | None = None, *, force_refresh: bool = False) -> list[dict[str, Any]]:
        payload = self.request_json("courses", params={"region_codes": region_codes or ["gb"]}, force_refresh=force_refresh)
        if isinstance(payload, dict):
            return payload.get("courses", [])
        return payload

    def fetch_racecards_standard(
        self,
        day: str,
        course_ids: list[str | int] | None = None,
        region_codes: list[str] | None = None,
        *,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"day": day}
        if course_ids:
            params["course_ids"] = course_ids
        if region_codes:
            params["region_codes"] = region_codes
        payload = self.request_json("racecards/standard", params=params, force_refresh=force_refresh)
        if isinstance(payload, dict):
            return payload
        return {"racecards": payload}

    def fetch_results(
        self,
        start_date: str,
        end_date: str,
        course: list[str | int] | None = None,
        *,
        force_refresh: bool = False,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"start_date": start_date, "end_date": end_date}
        if course:
            params["course"] = course
        payload = self.request_json("results", params=params, force_refresh=force_refresh)
        if isinstance(payload, dict):
            return payload.get("results", [])
        return payload
