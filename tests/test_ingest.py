import copy
import json
from pathlib import Path

import pandas as pd

from f1pred.ingest import build_tables, write_tables

FIX = Path(__file__).parent / "fixtures"
NOW = pd.Timestamp("2024-05-06", tz="UTC")


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))["MRData"]


class FakeApi:
    """Serves the Miami 2024 fixtures as if they were the whole 2024 season (round 6 only)."""

    def __init__(self, schedule_rounds=(6,)):
        self.calls = []
        sched = load("2024_schedule.json")["RaceTable"]["Races"]
        self._schedule = [r for r in sched if int(r["round"]) in schedule_rounds]

    def schedule(self, season, max_age=None):
        self.calls.append(("schedule", season, max_age))
        return copy.deepcopy(self._schedule)

    def season_races(self, season, endpoint, max_age=None):
        self.calls.append((endpoint, season, max_age))
        return copy.deepcopy(load(f"2024_6_{endpoint}.json")["RaceTable"]["Races"])

    def standings(self, season, rnd, kind, max_age=None):
        self.calls.append((kind, season, rnd, max_age))
        return copy.deepcopy(load(f"2024_6_{kind}.json"))


def test_build_tables_produces_all_tables_with_join_keys():
    tables, report = build_tables(FakeApi(), [2024], None, 3600, NOW)
    assert set(tables) == {
        "races", "results", "qualifying", "sprint_results", "driver_standings",
        "constructor_standings", "drivers", "constructors", "circuits",
    }
    assert len(tables["results"]) == 20 and len(tables["sprint_results"]) == 20
    assert tables["results"]["grid"].dtype == "Int64"
    for name in ("results", "qualifying", "driver_standings"):
        assert {"season", "round", "driver_id"} <= set(tables[name].columns)
    assert report.gaps == []


def test_historical_season_is_cached_forever_current_uses_ttl():
    api = FakeApi()
    build_tables(api, [2024], None, 3600, NOW)
    assert all(c[-1] is None for c in api.calls)
    api = FakeApi()
    build_tables(api, [2024], 2024, 3600, NOW)
    assert all(c[-1] == 3600 for c in api.calls)


def test_missing_past_race_is_reported_as_gap():
    # Schedule includes round 1 (already run on NOW) but the API has no results for it.
    _, report = build_tables(FakeApi(schedule_rounds=(1, 6)), [2024], None, 3600, NOW)
    kinds = {(g["kind"], g["round"]) for g in report.gaps}
    assert ("results_missing_for_past_race", 1) in kinds


def test_ingestion_is_idempotent(tmp_path):
    snapshots = []
    for _ in range(2):
        tables, report = build_tables(FakeApi(), [2024], None, 3600, NOW)
        write_tables(tables, report, tmp_path)
        snapshots.append({p.name: pd.read_parquet(p) for p in tmp_path.glob("*.parquet")})
    first, snapshot = snapshots
    assert first.keys() == snapshot.keys()
    for name in first:
        pd.testing.assert_frame_equal(first[name], snapshot[name])
