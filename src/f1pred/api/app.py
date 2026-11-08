"""FastAPI app: JSON API under /api, plus the built frontend (frontend/dist) at /.

    uv run uvicorn f1pred.api.app:app --reload

Environment:
    SITE_DATA_DIR  directory with the exported JSON (default: site_data)
    FRONTEND_DIST  directory with the built SPA (default: frontend/dist)
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


def site_data_dir() -> Path:
    return Path(os.environ.get("SITE_DATA_DIR", "site_data"))


def frontend_dir() -> Path:
    return Path(os.environ.get("FRONTEND_DIST", "frontend/dist"))


def read_json(name: str) -> Any:
    path = site_data_dir() / name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{name} not found")
    return json.loads(path.read_text(encoding="utf-8"))


# ---- response models (also documented in /docs) ----------------------------------------------


class Winner(BaseModel):
    driver_id: str
    name: str | None = None
    code: str | None = None
    team: str | None = None
    grid: int | None = None


class Race(BaseModel):
    season: int
    round: int
    race_name: str
    circuit_id: str
    circuit_name: str | None = None
    locality: str | None = None
    country: str | None = None
    race_start_utc: str | None = None
    quali_utc: str | None = None
    fp1_utc: str | None = None
    is_sprint_weekend: bool
    status: Literal["done", "upcoming"]
    winner: Winner | None = None
    pole_driver_id: str | None = None
    prediction_stages: list[str] = []


class DriverPrediction(BaseModel):
    driver_id: str
    constructor_id: str
    name: str | None = None
    code: str | None = None
    team: str | None = None
    p_win: float
    p_podium: float
    grid: int | None = None


class Prediction(BaseModel):
    season: int
    round: int
    race_name: str
    stage: Literal["t1", "t2"]
    generated_at: str
    race_start_utc: str
    model: dict[str, Any]
    train_races: int
    train_until: str
    warnings: list[str] = []
    predictions: list[DriverPrediction]


class ScoreRow(BaseModel):
    race: str
    season: int
    round: int
    stage: str
    predicted: str
    actual: str
    p_actual_winner: float
    winner_correct: bool
    podium_hit: float
    pole_won: bool


class Health(BaseModel):
    status: str
    generated_at: str | None
    latest_race: str | None
    server_time: str


# ---- app ------------------------------------------------------------------------------------

app = FastAPI(
    title="F1 Podium Predictor API",
    version="0.1.0",
    description="Pre-race win/podium probabilities for Formula 1 Grands Prix. "
                "Predictions are generated and committed before each race.",
)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"],
                   allow_methods=["GET"], allow_headers=["*"])


@app.get("/api/health", response_model=Health)
def health() -> Health:
    try:
        meta = read_json("meta.json")
    except HTTPException:
        meta = {}
    return Health(status="ok", generated_at=meta.get("generated_at"),
                  latest_race=meta.get("latest_race"),
                  server_time=datetime.now(UTC).isoformat())


@app.get("/api/races", response_model=list[Race])
def races(season: int = Query(2026)) -> list[dict]:
    return read_json(f"races_{season}.json")


@app.get("/api/races/next", response_model=Race)
def next_race(season: int = Query(2026)) -> dict:
    upcoming = [r for r in read_json(f"races_{season}.json") if r["status"] == "upcoming"]
    if not upcoming:
        raise HTTPException(status_code=404, detail="no upcoming race this season")
    return upcoming[0]


@app.get("/api/races/{season}/{rnd}/predictions", response_model=Prediction)
def prediction(season: int, rnd: int, stage: Literal["t1", "t2"] = "t2") -> dict:
    return read_json(f"predictions/{season}_R{rnd:02d}_{stage}.json")


@app.get("/api/scoreboard", response_model=list[ScoreRow])
def scoreboard() -> list[dict]:
    return read_json("scoreboard.json")


@app.get("/api/backtest/{season}")
def backtest(season: int) -> dict:
    """Retroactive walk-forward predictions (each race predicted from earlier races only)."""
    return read_json(f"backtest_{season}.json")


@app.get("/api/evaluation")
def evaluation() -> dict:
    return read_json("evaluation.json")


@app.get("/api/drivers")
def drivers() -> dict:
    return read_json("drivers.json")


# ---- frontend (single-page app) -------------------------------------------------------------

_dist = frontend_dir()
if (_dist / "assets").exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str) -> FileResponse:
    if path.startswith("api/"):
        raise HTTPException(status_code=404, detail="unknown API route")
    dist = frontend_dir()
    target = dist / path
    if path and target.is_file() and dist.resolve() in target.resolve().parents:
        return FileResponse(target)
    index = dist / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="frontend not built (npm run build)")
    return FileResponse(index)
