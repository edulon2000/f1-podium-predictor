import json

import pytest
from fastapi.testclient import TestClient

from f1pred.api.app import app


def write(base, name, payload):
    path = base / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


RACE = {"season": 2026, "round": 21, "race_name": "Las Vegas Grand Prix", "circuit_id": "vegas",
        "is_sprint_weekend": False, "status": "upcoming", "prediction_stages": ["t1"]}
DONE = {**RACE, "round": 20, "race_name": "Brazilian Grand Prix", "circuit_id": "interlagos",
        "status": "done", "winner": {"driver_id": "norris", "name": "Lando Norris", "grid": 3}}
PRED = {"season": 2026, "round": 21, "race_name": "Las Vegas Grand Prix", "stage": "t1",
        "generated_at": "2026-11-20T23:00:00+00:00", "race_start_utc": "2026-11-22T04:00:00",
        "model": {"kind": "lgbm"}, "train_races": 270, "train_until": "2026 R20",
        "predictions": [{"driver_id": "russell", "constructor_id": "mercedes",
                         "p_win": 0.31, "p_podium": 0.7}]}


@pytest.fixture
def client(tmp_path, monkeypatch):
    data, dist = tmp_path / "site_data", tmp_path / "dist"
    write(data, "races_2026.json", [DONE, RACE])
    write(data, "predictions/2026_R21_t1.json", PRED)
    write(data, "scoreboard.json", [])
    write(data, "meta.json", {"generated_at": "x", "latest_race": "Brazilian Grand Prix"})
    write(data, "evaluation.json", {"chosen": {}})
    write(data, "races/2026_R20.json", {"round": 20, "drivers": [], "stages": {}})
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>spa</html>", encoding="utf-8")
    monkeypatch.setenv("SITE_DATA_DIR", str(data))
    monkeypatch.setenv("FRONTEND_DIST", str(dist))
    return TestClient(app)


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["latest_race"] == "Brazilian Grand Prix"


def test_races_and_next(client):
    assert len(client.get("/api/races?season=2026").json()) == 2
    nxt = client.get("/api/races/next").json()
    assert nxt["round"] == 21 and nxt["status"] == "upcoming"


def test_prediction_found_and_missing(client):
    r = client.get("/api/races/2026/21/predictions?stage=t1")
    assert r.status_code == 200 and r.json()["predictions"][0]["driver_id"] == "russell"
    assert client.get("/api/races/2026/21/predictions?stage=t2").status_code == 404
    assert client.get("/api/races/2026/21/predictions?stage=t9").status_code == 422


def test_unknown_api_route_is_404_not_spa(client):
    assert client.get("/api/nope").status_code == 404


def test_spa_fallback_serves_index(client):
    r = client.get("/history")
    assert r.status_code == 200 and "spa" in r.text


def test_path_traversal_blocked(client):
    r = client.get("/..%2F..%2Fsite_data%2Fmeta.json")
    assert "spa" in r.text or r.status_code == 404


def test_race_detail(client):
    assert client.get("/api/races/2026/20/detail").json()["round"] == 20
    assert client.get("/api/races/2026/5/detail").status_code == 404
