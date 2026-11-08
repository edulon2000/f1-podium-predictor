"""HTTP layer: rate limiting + on-disk JSON cache.

Jolpica-F1 allows 4 requests/second burst and 500 requests/hour sustained. Both windows are
enforced. The hourly window is persisted to disk so that restarting the ingestion does not reset
the budget and get us throttled.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger(__name__)

Params = Mapping[str, Any] | None


class ApiError(RuntimeError):
    """The upstream API failed or returned something we cannot trust."""


class RateLimiter:
    """Sliding-window limiter over two windows (1 s and 1 h)."""

    def __init__(
        self,
        per_second: int = 4,
        per_hour: int = 500,
        state_path: Path | None = None,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.per_second = per_second
        self.per_hour = per_hour
        self.state_path = state_path
        self._clock = clock
        self._sleep = sleep
        self._second: deque[float] = deque()
        self._hour: deque[float] = deque(self._load_state())

    def _load_state(self) -> list[float]:
        if not self.state_path or not self.state_path.exists():
            return []
        try:
            stamps = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        cutoff = self._clock() - 3600
        return sorted(t for t in stamps if t > cutoff)

    def _save_state(self) -> None:
        if not self.state_path:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(list(self._hour)), encoding="utf-8")
        os.replace(tmp, self.state_path)

    @staticmethod
    def _wait_needed(window: deque[float], limit: int, span: float, now: float) -> float:
        while window and window[0] <= now - span:
            window.popleft()
        if len(window) < limit:
            return 0.0
        return window[0] + span - now

    def acquire(self) -> None:
        while True:
            now = self._clock()
            wait = max(
                self._wait_needed(self._second, self.per_second, 1.0, now),
                self._wait_needed(self._hour, self.per_hour, 3600.0, now),
            )
            if wait <= 0:
                break
            if wait > 5:
                log.warning("Rate limit reached: waiting %.0f s for the hourly window", wait)
            self._sleep(wait)
        now = self._clock()
        self._second.append(now)
        self._hour.append(now)
        self._save_state()

    @property
    def used_last_hour(self) -> int:
        self._wait_needed(self._hour, self.per_hour, 3600.0, self._clock())
        return len(self._hour)


@dataclass(frozen=True)
class CacheEntry:
    body: Any
    fetched_at: float


class DiskCache:
    """One JSON file per request, laid out to mirror the API path (easy to inspect by hand)."""

    def __init__(self, root: Path, base_url: str) -> None:
        self.root = Path(root)
        self.base_url = base_url.rstrip("/")

    def path_for(self, url: str, params: Params = None) -> Path:
        rel = url[len(self.base_url):] if url.startswith(self.base_url) else url
        rel = rel.lstrip("/")
        stem = rel[:-5] if rel.endswith(".json") else rel
        if params:
            query = "_".join(f"{k}={params[k]}" for k in sorted(params))
            stem = f"{stem}__{query}"
        stem = re.sub(r"[^A-Za-z0-9_./=-]", "_", stem)
        return self.root / f"{stem}.json"

    def get(self, url: str, params: Params = None) -> CacheEntry | None:
        path = self.path_for(url, params)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return CacheEntry(body=payload["body"], fetched_at=payload["fetched_at"])

    def put(self, url: str, params: Params, body: Any, fetched_at: float) -> None:
        path = self.path_for(url, params)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"url": url, "params": dict(params or {}), "fetched_at": fetched_at, "body": body}
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)


class CachedClient:
    """GET JSON with cache-first semantics, rate limiting and bounded retries."""

    RETRY_STATUSES = {429, 500, 502, 503, 504}

    def __init__(
        self,
        cache: DiskCache,
        limiter: RateLimiter,
        http: httpx.Client | None = None,
        max_retries: int = 4,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.cache = cache
        self.limiter = limiter
        self.http = http or httpx.Client(timeout=30.0, headers={"User-Agent": "f1pred/0.1"})
        self.max_retries = max_retries
        self._clock = clock
        self._sleep = sleep
        self.network_requests = 0
        self.cache_hits = 0

    def get_json(self, url: str, params: Params = None, max_age: float | None = None) -> Any:
        """Return the JSON body for url+params.

        max_age=None means a cached copy never expires (finished seasons); otherwise a cached
        copy older than max_age seconds is re-fetched.
        """
        entry = self.cache.get(url, params)
        if entry is not None and (max_age is None or self._clock() - entry.fetched_at <= max_age):
            self.cache_hits += 1
            return entry.body
        body = self._fetch(url, params)
        self.cache.put(url, params, body, fetched_at=self._clock())
        return body

    def _fetch(self, url: str, params: Params) -> Any:
        last_error = ""
        for attempt in range(self.max_retries + 1):
            self.limiter.acquire()
            self.network_requests += 1
            try:
                resp = self.http.get(url, params=dict(params or {}))
            except httpx.HTTPError as exc:
                last_error = f"network error: {exc!r}"
                self._sleep(min(2**attempt, 60))
                continue
            if resp.status_code == 200:
                try:
                    return resp.json()
                except ValueError as exc:
                    raise ApiError(f"{url}: response is not JSON ({resp.text[:120]!r})") from exc
            last_error = f"HTTP {resp.status_code}: {resp.text[:200]!r}"
            if resp.status_code not in self.RETRY_STATUSES:
                break
            retry_after = resp.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                delay = float(retry_after)
            elif resp.status_code == 429:
                delay = 10.0 * (attempt + 1)  # back off hard: retries also burn the hourly budget
            else:
                delay = 2.0**attempt
            log.warning("%s -> %s, retrying in %.0f s", url, resp.status_code, delay)
            self._sleep(min(delay, 900))
        raise ApiError(f"{url} params={dict(params or {})}: {last_error}")
