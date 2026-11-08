import pandas as pd

from f1pred.openf1 import driver_map, ingest, map_meetings

NOW = pd.Timestamp("2026-11-09", tz="UTC")

RACES = pd.DataFrame({
    "season": [2026, 2026], "round": [20, 21],
    "race_start_utc": pd.to_datetime(["2026-11-08T17:00Z", "2026-11-22T04:00Z"], utc=True),
})
RESULTS = pd.DataFrame({"season": [2026, 2026], "round": [20, 20],
                        "driver_id": ["norris", "max_verstappen"], "number": [1, 3]})
DRIVERS = pd.DataFrame({"driver_id": ["norris", "max_verstappen"], "code": ["NOR", "VER"]})


def sess(mk, sk, name, start, end):
    return {"meeting_key": mk, "session_key": sk, "session_name": name,
            "session_type": "Race" if name == "Race" else "Practice",
            "date_start": start, "date_end": end}


SESSIONS = [
    sess(1, 10, "Practice 1", "2026-11-06T15:30Z", "2026-11-06T16:30Z"),
    sess(1, 11, "Qualifying", "2026-11-07T18:00Z", "2026-11-07T19:00Z"),
    sess(1, 12, "Race", "2026-11-08T17:00Z", "2026-11-08T19:00Z"),
    sess(2, 20, "Practice 1", "2026-11-20T00:30Z", "2026-11-20T01:30Z"),  # future: not fetched
    sess(99, 990, "Day 1", "2026-02-11T07:00Z", "2026-02-11T16:00Z"),     # testing: dropped
]


class FakeOpenF1:
    def __init__(self):
        self.calls = []

    def get(self, endpoint, max_age=None, **params):
        self.calls.append((endpoint, params, max_age))
        if endpoint == "sessions":
            return SESSIONS
        if endpoint == "drivers":
            return [{"driver_number": 1, "name_acronym": "NOR"},
                    {"driver_number": 3, "name_acronym": "VER"},
                    {"driver_number": 3, "name_acronym": "VER"}]
        if endpoint == "laps":
            return [{"driver_number": 1, "lap_number": 1, "lap_duration": 72.1},
                    {"driver_number": 44, "lap_number": 1, "lap_duration": 75.0}]
        if endpoint == "stints":
            return [{"driver_number": 3, "stint_number": 1, "compound": "SOFT"}]
        if endpoint == "starting_grid":
            return [{"driver_number": 1, "position": 1, "lap_duration": 70.0}]
        if endpoint == "weather":
            return [{"air_temperature": 20, "track_temperature": 30, "humidity": 50,
                     "wind_speed": 1, "rainfall": 0}]
        return []


def test_map_meetings_drops_testing_and_matches_rounds():
    m = map_meetings(pd.DataFrame(SESSIONS), RACES)
    assert set(m.meeting_key) == {1, 2}
    assert set(m[m.meeting_key == 2]["round"]) == {21}


def test_driver_map_code_wins_and_number_only_without_code():
    dmap = driver_map([{"driver_number": 1, "name_acronym": "NOR"},
                       {"driver_number": 3, "name_acronym": None}], 2026, RESULTS, DRIVERS)
    assert dmap == {1: "norris", 3: "max_verstappen"}


def test_driver_map_ignores_support_series_driver_reusing_a_number():
    # An F2 driver ("ARO") with car number 1 must not be mapped to the F1 #1 (Norris here),
    # whatever the order of the rows.
    rows = [{"driver_number": 1, "name_acronym": "ARO"},
            {"driver_number": 1, "name_acronym": "NOR"},
            {"driver_number": 1, "name_acronym": "ARO"}]
    assert driver_map(rows, 2026, RESULTS, DRIVERS) == {1: "norris"}
    assert driver_map(rows[:1], 2026, RESULTS, DRIVERS) == {}


def test_ingest_only_fetches_finished_sessions_and_reports_unmapped():
    api = FakeOpenF1()
    tables, gaps = ingest(api, [2026], RACES, RESULTS, DRIVERS, NOW, ttl=3600)
    fetched = {(e, p.get("session_key")) for e, p, _ in api.calls}
    assert ("laps", 10) in fetched and ("laps", 20) not in fetched
    assert ("starting_grid", 11) in fetched  # grid via the qualifying key
    assert list(tables["of1_laps"].driver_id) == ["norris"]
    assert tables["of1_grid"].iloc[0].to_dict()["grid_position"] == 1
    assert tables["of1_weather"].iloc[0]["rainfall_any"] is False or not \
        tables["of1_weather"].iloc[0]["rainfall_any"]
    assert any(g["kind"] == "openf1_unmapped_driver" and g["driver_number"] == 44 for g in gaps)


def test_recent_sessions_use_ttl_old_ones_cached_forever():
    api = FakeOpenF1()
    ingest(api, [2026], RACES, RESULTS, DRIVERS, NOW, ttl=3600)
    assert all(a == 3600 for e, _, a in api.calls if e != "sessions")
    api = FakeOpenF1()
    ingest(api, [2026], RACES, RESULTS, DRIVERS, NOW + pd.Timedelta(days=30), ttl=3600)
    assert all(a is None for e, p, a in api.calls if p.get("session_key") == 10)


def test_clean_stints_drops_support_series_and_ambiguous_cars():
    from f1pred.openf1 import clean_stints
    laps = [{"driver_number": 1}, {"driver_number": 4}]
    stints = [
        {"driver_number": 1, "stint_number": 1}, {"driver_number": 1, "stint_number": 2},
        {"driver_number": 4, "stint_number": 1}, {"driver_number": 4, "stint_number": 1},  # clash
        {"driver_number": 24, "stint_number": 1},                                        # F2 car
    ]
    gaps = []
    out = clean_stints(stints, laps, 2025, 11, "Practice 3", gaps)
    assert [(s["driver_number"], s["stint_number"]) for s in out] == [(1, 1), (1, 2)]
    assert gaps[0]["dropped_rows"] == 1 and gaps[0]["ambiguous_cars"] == [4]
