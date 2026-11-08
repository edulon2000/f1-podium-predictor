import json
from pathlib import Path

import httpx
import pytest

from f1pred.http import CachedClient, DiskCache, RateLimiter
from f1pred.jolpica import Jolpica
from f1pred.schema import (
    SchemaError,
    collect_dimensions,
    laptime_to_seconds,
    parse_constructor_standings,
    parse_driver_standings,
    parse_qualifying,
    parse_results,
    parse_schedule,
)

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))["MRData"]


def races(name):
    return load(name)["RaceTable"]["Races"]


# --- parsers on real payloads ----------------------------------------------------------------


def test_laptime_parsing():
    assert laptime_to_seconds("1:27.689") == pytest.approx(87.689)
    assert laptime_to_seconds("27.5") == pytest.approx(27.5)
    assert laptime_to_seconds("1:30:49.876") == pytest.approx(5449.876)
    assert laptime_to_seconds("") is None
    assert laptime_to_seconds(None) is None


def test_parse_results_miami_2024():
    rows = parse_results(races("2024_6_results.json"))
    assert len(rows) == 20
    winner = rows[0]
    assert (winner["season"], winner["round"]) == (2024, 6)
    assert winner["driver_id"] == "norris" and winner["constructor_id"] == "mclaren"
    assert winner["grid"] == 5 and winner["position"] == 1 and winner["points"] == 25.0
    dnf = rows[-1]
    assert dnf["position_text"] == "R" and dnf["time_millis"] is None


def test_parse_results_handles_unpublished_grid():
    rows = parse_results(races("2026_20_results.json"))
    assert len(rows) == 22
    assert all(r["grid"] is None for r in rows)
    assert all(r["fastest_lap_rank"] is None for r in rows)


def test_parse_sprint_and_qualifying():
    sprint = parse_results(races("2024_6_sprint.json"), list_key="SprintResults")
    assert sprint[0]["driver_id"] == "max_verstappen" and sprint[0]["points"] == 8.0
    quali = parse_qualifying(races("2024_6_qualifying.json"))
    assert len(quali) == 20
    pole = quali[0]
    assert pole["position"] == 1 and pole["q3_s"] == pytest.approx(87.241)
    assert quali[-1]["q3_s"] is None  # eliminated in Q1


def test_parse_standings():
    ds = parse_driver_standings(load("2024_6_driverStandings.json"))
    assert ds[0] == {
        "season": 2024, "round": 6, "driver_id": "max_verstappen", "constructor_id": "red_bull",
        "position": 1, "position_text": "1", "points": 136.0, "wins": 4,
    }
    cs = parse_constructor_standings(load("2024_6_constructorStandings.json"))
    assert len(cs) == 10 and cs[0]["constructor_id"] == "red_bull"


def test_parse_schedule_sessions_and_sprint_flag():
    rows = {r["round"]: r for r in parse_schedule(races("2024_schedule.json"))}
    miami, bahrain = rows[6], rows[1]
    assert miami["is_sprint_weekend"] and miami["sprint_quali_utc"] is not None
    assert miami["fp2_utc"] is None
    assert not bahrain["is_sprint_weekend"] and bahrain["fp3_utc"] is not None
    assert str(miami["race_start_utc"]) == "2024-05-05 20:00:00+00:00"


def test_missing_field_raises_schema_error():
    broken = races("2024_6_results.json")
    del broken[0]["Results"][0]["Driver"]
    with pytest.raises(SchemaError, match="Driver"):
        parse_results(broken)


def test_collect_dimensions():
    dims = collect_dimensions(races("2024_6_results.json"), [load("2024_6_driverStandings.json")])
    assert {"norris", "max_verstappen"} <= {d["driver_id"] for d in dims["drivers"]}
    assert dims["circuits"][0]["circuit_id"] == "miami"


# --- pagination ------------------------------------------------------------------------------


def make_api(tmp_path, handler):
    client = CachedClient(
        cache=DiskCache(tmp_path, base_url="https://x/f1"),
        limiter=RateLimiter(per_second=10**6, per_hour=10**6),
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    return Jolpica(client, base_url="https://x/f1")


def page(offset, total, races):
    return {"MRData": {"limit": "100", "offset": str(offset), "total": str(total),
                       "RaceTable": {"Races": races}}}


def race(rnd, n_results, start=0):
    return {"season": "2014", "round": str(rnd),
            "Results": [{"i": start + i} for i in range(n_results)]}


def test_pagination_merges_race_split_across_pages(tmp_path):
    pages = {
        0: page(0, 130, [race(1, 60), race(2, 40)]),
        100: page(100, 130, [race(2, 20, start=40), race(3, 10)]),
    }

    def handler(request):
        return httpx.Response(200, json=pages[int(request.url.params["offset"])])

    out = make_api(tmp_path, handler).season_races(2014, "results")
    assert [r["round"] for r in out] == ["1", "2", "3"]
    assert [len(r["Results"]) for r in out] == [60, 60, 10]


def test_pagination_row_count_mismatch_raises(tmp_path):
    def handler(request):
        return httpx.Response(200, json=page(0, 50, [race(1, 20)]))

    with pytest.raises(SchemaError, match="expected 50 rows"):
        make_api(tmp_path, handler).season_races(2014, "results")
