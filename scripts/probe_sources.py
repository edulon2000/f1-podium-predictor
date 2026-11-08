"""Probe OpenF1 and FastF1 on one real session and record what each actually returns.

Output: data/raw/samples/source_probe.json (endpoint -> status, row count, columns, sample row).
Used to write docs/SOURCES.md from observed data rather than from memory.

    uv run python scripts/probe_sources.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

OUT = Path("data/raw/samples")
OPENF1 = "https://api.openf1.org/v1"
YEAR, COUNTRY, GP = 2026, "Brazil", "São Paulo"


def openf1(client: httpx.Client, endpoint: str, params: dict) -> dict:
    time.sleep(0.4)  # stay well under OpenF1's public limits
    try:
        r = client.get(f"{OPENF1}/{endpoint}", params=params)
    except httpx.HTTPError as exc:
        return {"status": None, "error": repr(exc)}
    out: dict = {"status": r.status_code, "params": params}
    try:
        data = r.json()
    except ValueError:
        out["error"] = r.text[:200]
        return out
    if isinstance(data, list):
        out["rows"] = len(data)
        out["columns"] = sorted({k for row in data for k in row}) if data else []
        out["sample"] = data[0] if data else None
    else:
        out["error"] = str(data)[:300]
    return out


def probe_openf1() -> dict:
    res: dict = {}
    with httpx.Client(timeout=60) as c:
        params = {"year": YEAR, "country_name": COUNTRY}
        sessions = c.get(f"{OPENF1}/sessions", params=params).json()
        by_name = {s["session_name"]: s for s in sessions}
        race, quali = by_name["Race"], by_name["Qualifying"]
        rk, qk, mk = race["session_key"], quali["session_key"], race["meeting_key"]
        res["_session_keys"] = {"race": rk, "qualifying": qk, "meeting": mk}
        # earliest season covered
        for y in (2022, 2023):
            r = c.get(f"{OPENF1}/sessions", params={"year": y, "session_name": "Race"}).json()
            res[f"_coverage_{y}_races"] = len(r) if isinstance(r, list) else str(r)[:200]
        window = {"date>": race["date_start"], "date<": race["date_start"][:15] + "1:00+00:00"}
        endpoints = {
            "meetings": {"meeting_key": mk},
            "sessions": {"meeting_key": mk},
            "drivers": {"session_key": rk},
            "session_result": {"session_key": rk},
            "session_result__quali": ("session_result", {"session_key": qk}),
            "starting_grid": {"session_key": rk},  # 404: grid lives under the quali key
            "starting_grid__quali": ("starting_grid", {"session_key": qk}),
            "laps": {"session_key": rk, "driver_number": 1},
            "stints": {"session_key": rk},
            "pit": {"session_key": rk},
            "weather": {"session_key": rk},
            "race_control": {"session_key": rk},
            "position": {"session_key": rk, "driver_number": 1},
            "intervals": {"session_key": rk, "driver_number": 1},
            "overtakes": {"session_key": rk},
            "team_radio": {"session_key": rk, "driver_number": 1},
            "championship_drivers": {"session_key": rk},
            "championship_teams": {"session_key": rk},
            "car_data": {"session_key": rk, "driver_number": 1, **window},
            "location": {"session_key": rk, "driver_number": 1, **window},
        }
        for name, spec in endpoints.items():
            endpoint, params = spec if isinstance(spec, tuple) else (name, spec)
            res[name] = openf1(c, endpoint, params)
            print(f"openf1 {name:24s} {res[name].get('status')} rows={res[name].get('rows')}")
    return res


def probe_fastf1() -> dict:
    import fastf1

    cache = Path(".cache/fastf1")
    cache.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(cache))
    res: dict = {"version": fastf1.__version__}
    sched = fastf1.get_event_schedule(YEAR, include_testing=False)
    res["schedule_columns"] = list(sched.columns)
    res["schedule_rows"] = len(sched)
    for code in ("Q", "R"):
        s = fastf1.get_session(YEAR, GP, code)
        s.load(laps=True, telemetry=False, weather=True, messages=True)
        entry = {
            "event": str(s.event["EventName"]),
            "results_columns": list(s.results.columns),
            "results_rows": len(s.results),
            "laps_columns": list(s.laps.columns),
            "laps_rows": len(s.laps),
            "weather_columns": list(s.weather_data.columns) if s.weather_data is not None else None,
            "weather_rows": len(s.weather_data) if s.weather_data is not None else 0,
            "race_control_rows": len(s.race_control_messages)
            if s.race_control_messages is not None else 0,
            "compounds": sorted(s.laps["Compound"].dropna().unique().tolist()),
            "results_sample": s.results.iloc[0].astype(str).to_dict(),
        }
        res[code] = entry
        print(f"fastf1 {code}: results={entry['results_rows']} laps={entry['laps_rows']}")
    # Oldest season with lap timing: FastF1 documents 2018+. Verify one 2018 schedule loads.
    res["schedule_2018_rows"] = len(fastf1.get_event_schedule(2018, include_testing=False))
    return res


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    result = {"openf1": probe_openf1()}
    try:
        result["fastf1"] = probe_fastf1()
    except Exception as exc:  # report, don't hide
        result["fastf1"] = {"error": repr(exc)}
        print("fastf1 FAILED:", repr(exc))
    path = OUT / "source_probe.json"
    path.write_text(json.dumps(result, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    print("wrote", path)


if __name__ == "__main__":
    main()
