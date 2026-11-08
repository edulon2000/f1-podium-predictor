import json

import httpx
import pytest

from f1pred.http import ApiError, CachedClient, DiskCache, RateLimiter


class FakeClock:
    def __init__(self, start: float = 1_000_000.0):
        self.now = start
        self.slept: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


# --- RateLimiter -----------------------------------------------------------------------------


def test_limiter_allows_burst_up_to_per_second_limit():
    clock = FakeClock()
    lim = RateLimiter(per_second=4, per_hour=500, clock=clock.time, sleep=clock.sleep)
    for _ in range(4):
        lim.acquire()
    assert clock.slept == []


def test_limiter_waits_when_per_second_limit_hit():
    clock = FakeClock()
    lim = RateLimiter(per_second=4, per_hour=500, clock=clock.time, sleep=clock.sleep)
    for _ in range(5):
        lim.acquire()
    assert sum(clock.slept) == pytest.approx(1.0, abs=0.01)


def test_limiter_waits_for_hourly_window():
    clock = FakeClock()
    lim = RateLimiter(per_second=1000, per_hour=3, clock=clock.time, sleep=clock.sleep)
    for _ in range(3):
        lim.acquire()
    lim.acquire()
    assert sum(clock.slept) == pytest.approx(3600.0, abs=0.01)


def test_limiter_persists_hourly_window(tmp_path):
    state = tmp_path / "limiter.json"
    clock = FakeClock()
    lim = RateLimiter(per_second=1000, per_hour=2, state_path=state, clock=clock.time,
                      sleep=clock.sleep)
    lim.acquire()
    lim.acquire()
    # A new process (new limiter) must still honour the two requests already made.
    lim2 = RateLimiter(per_second=1000, per_hour=2, state_path=state, clock=clock.time,
                       sleep=clock.sleep)
    lim2.acquire()
    assert sum(clock.slept) == pytest.approx(3600.0, abs=0.01)


# --- DiskCache -------------------------------------------------------------------------------


def test_cache_roundtrip_and_human_readable_path(tmp_path):
    cache = DiskCache(tmp_path, base_url="https://api.example/ergast/f1")
    url = "https://api.example/ergast/f1/2014/results.json"
    params = {"offset": 100, "limit": 100}
    assert cache.get(url, params) is None
    cache.put(url, params, {"hello": "world"}, fetched_at=123.0)
    entry = cache.get(url, params)
    assert entry.body == {"hello": "world"}
    assert entry.fetched_at == 123.0
    path = cache.path_for(url, params)
    assert path.relative_to(tmp_path).as_posix() == "2014/results__limit=100_offset=100.json"


# --- CachedClient ----------------------------------------------------------------------------


def make_client(tmp_path, handler, clock=None):
    clock = clock or FakeClock()
    transport = httpx.MockTransport(handler)
    return CachedClient(
        cache=DiskCache(tmp_path / "raw", base_url="https://api.example/f1"),
        limiter=RateLimiter(per_second=1000, per_hour=1000, clock=clock.time, sleep=clock.sleep),
        http=httpx.Client(transport=transport),
        clock=clock.time,
        sleep=clock.sleep,
    ), clock


def test_client_serves_from_cache_on_second_call(tmp_path):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, json={"n": len(calls)})

    client, _ = make_client(tmp_path, handler)
    url = "https://api.example/f1/2020.json"
    assert client.get_json(url) == {"n": 1}
    assert client.get_json(url) == {"n": 1}
    assert len(calls) == 1
    assert client.network_requests == 1


def test_client_refetches_when_cache_is_stale(tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json={"n": len(calls)})

    client, clock = make_client(tmp_path, handler)
    url = "https://api.example/f1/2026.json"
    client.get_json(url, max_age=60)
    clock.now += 61
    assert client.get_json(url, max_age=60) == {"n": 2}


def test_client_retries_on_429_respecting_retry_after(tmp_path):
    responses = [httpx.Response(429, headers={"Retry-After": "7"}), httpx.Response(200, json={})]

    def handler(request):
        return responses.pop(0)

    client, clock = make_client(tmp_path, handler)
    client.get_json("https://api.example/f1/x.json")
    assert 7 in clock.slept


def test_client_raises_after_persistent_errors_and_does_not_cache(tmp_path):
    def handler(request):
        return httpx.Response(503, text="down")

    client, _ = make_client(tmp_path, handler)
    with pytest.raises(ApiError, match="503"):
        client.get_json("https://api.example/f1/y.json")
    assert not list((tmp_path / "raw").rglob("*.json"))


def test_client_raises_on_non_json(tmp_path):
    def handler(request):
        return httpx.Response(200, text="<html>maintenance</html>")

    client, _ = make_client(tmp_path, handler)
    with pytest.raises(ApiError, match="JSON"):
        client.get_json("https://api.example/f1/z.json")


def test_cache_file_is_valid_json_with_metadata(tmp_path):
    def handler(request):
        return httpx.Response(200, json={"ok": True})

    client, _ = make_client(tmp_path, handler)
    client.get_json("https://api.example/f1/2019/results.json", {"limit": 100, "offset": 0})
    files = list((tmp_path / "raw").rglob("*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text(encoding="utf-8"))
    assert payload["url"].endswith("2019/results.json")
    assert payload["body"] == {"ok": True}
