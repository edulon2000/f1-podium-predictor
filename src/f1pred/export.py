"""Export everything the website needs into site_data/ (small JSON files, committed to git).

    uv run f1pred-export [--season 2026]

The API only reads these files, so the deployed service needs no pandas, no model and no
Parquet: predictions shown on the site are exactly the files committed before each race.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from f1pred.data import load_tables
from f1pred.evaluate import races_between, walk_forward
from f1pred.features import build_features
from f1pred.predict import load_spec, score

log = logging.getLogger("f1pred.export")


def _ts(v: Any) -> str | None:
    return None if v is None or pd.isna(v) else pd.Timestamp(v).isoformat()


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str),
                    encoding="utf-8")


def driver_index(t: dict) -> dict[str, dict]:
    d = t["drivers"].set_index("driver_id")
    return {i: {"driver_id": i, "name": f"{r.given_name} {r.family_name}",
                "family_name": r.family_name, "code": r.code,
                "number": None if pd.isna(r.permanent_number) else int(r.permanent_number)}
            for i, r in d.iterrows()}


def export_races(t: dict, season: int, pred_dir: Path) -> list[dict]:
    races = t["races"][t["races"].season == season].sort_values("round")
    res = t["results"]
    circuits = t["circuits"].set_index("circuit_id")
    teams = t["constructors"].set_index("constructor_id")["name"]
    drivers = driver_index(t)
    out = []
    for r in races.itertuples():
        rr = res[(res.season == season) & (res["round"] == r.round)]
        winner = rr[rr.position == 1]
        pole = rr[rr.grid == 1]
        c = circuits.loc[r.circuit_id] if r.circuit_id in circuits.index else None
        stages = sorted(p.stem.split("_")[-1]
                        for p in pred_dir.glob(f"{season}_R{r.round:02d}_t*.json"))
        out.append({
            "season": season, "round": int(r.round), "race_name": r.race_name,
            "circuit_id": r.circuit_id,
            "circuit_name": None if c is None else c["circuit_name"],
            "locality": None if c is None else c["locality"],
            "country": None if c is None else c["country"],
            "race_start_utc": _ts(r.race_start_utc), "quali_utc": _ts(r.quali_utc),
            "fp1_utc": _ts(r.fp1_utc), "is_sprint_weekend": bool(r.is_sprint_weekend),
            "status": "done" if len(rr) else "upcoming",
            "winner": None if winner.empty else {
                **drivers.get(winner.driver_id.iloc[0], {"driver_id": winner.driver_id.iloc[0]}),
                "team": teams.get(winner.constructor_id.iloc[0], winner.constructor_id.iloc[0]),
                "grid": None if pd.isna(winner.grid.iloc[0]) else int(winner.grid.iloc[0])},
            "pole_driver_id": None if pole.empty else pole.driver_id.iloc[0],
            "prediction_stages": stages,
        })
    return out


def export_predictions(t: dict, pred_dir: Path, out_dir: Path) -> list[str]:
    drivers = driver_index(t)
    teams = t["constructors"].set_index("constructor_id")["name"].to_dict()
    written = []
    for path in sorted(pred_dir.glob("*_R*_t*.json")):
        p = json.loads(path.read_text(encoding="utf-8"))
        for rec in p["predictions"]:
            d = drivers.get(rec["driver_id"], {})
            rec["name"] = d.get("name", rec["driver_id"])
            rec["code"] = d.get("code")
            rec["team"] = teams.get(rec["constructor_id"], rec["constructor_id"])
        _write(out_dir / "predictions" / path.name, p)
        written.append(path.name)
    return written


def export_scoreboard(t: dict, pred_dir: Path) -> list[dict]:
    res = t["results"]
    rows = []
    done = {(int(s), int(r)) for s, r in zip(res.season, res["round"], strict=True)}
    keys = sorted({tuple(int(x) for x in p.stem.replace("R", "").split("_")[:2])
                   for p in pred_dir.glob("*_R*_t*.json")})
    for season, rnd in keys:
        if (season, rnd) not in done:
            continue
        board = score(t, season, rnd, pred_dir)
        win = res[(res.season == season) & (res["round"] == rnd) & (res.position == 1)]
        pole_won = bool((win.grid == 1).any())
        for rec in board.to_dict("records"):
            rows.append({**rec, "season": season, "round": rnd, "pole_won": pole_won})
    return rows


def export_backtest(frame: pd.DataFrame, season: int) -> dict:
    """Retroactive walk-forward predictions for the season (clearly labelled as backtest)."""
    out: dict[str, list] = {}
    races = races_between(frame, season, season)
    if not races:
        return out
    for stage in ("t1", "t2"):
        spec = load_spec(stage, Path("configs"))
        preds = walk_forward(frame, spec.as_predictor(), races)
        rows = []
        for (s, r), g in preds.groupby(["season", "round"]):
            top = g.sort_values("p_win", ascending=False)
            winner = g[g.win == 1]
            rows.append({
                "season": int(s), "round": int(r),
                "predicted": top.driver_id.iloc[0], "p_predicted": round(top.p_win.iloc[0], 4),
                "actual": None if winner.empty else winner.driver_id.iloc[0],
                "p_actual": None if winner.empty else round(winner.p_win.iloc[0], 4),
                "predicted_podium": list(g.sort_values("p_podium", ascending=False)
                                         .driver_id.head(3)),
                "actual_podium": list(g[g.podium == 1].sort_values("finish_pos").driver_id),
                "pole_won": bool((winner.grid_f == 1).any()),
            })
        out[stage] = rows
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--season", type=int, default=2026)
    p.add_argument("--data-dir", type=Path, default=Path("data"))
    p.add_argument("--predictions", type=Path, default=Path("predictions"))
    p.add_argument("--out", type=Path, default=Path("site_data"))
    p.add_argument("--no-backtest", action="store_true")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    t = load_tables(args.data_dir)
    args.predictions.mkdir(exist_ok=True)
    if args.out.exists():
        shutil.rmtree(args.out)
    args.out.mkdir(parents=True)

    races = export_races(t, args.season, args.predictions)
    _write(args.out / f"races_{args.season}.json", races)
    preds = export_predictions(t, args.predictions, args.out)
    _write(args.out / "scoreboard.json", export_scoreboard(t, args.predictions))
    _write(args.out / "drivers.json", driver_index(t))
    teams = t["constructors"].set_index("constructor_id")["name"].to_dict()
    _write(args.out / "teams.json", teams)

    eval_path = Path("reports/evaluation.json")
    if eval_path.exists():
        shutil.copy(eval_path, args.out / "evaluation.json")
    else:
        log.warning("reports/evaluation.json missing — run scripts/run_evaluation.py")

    if not args.no_backtest:
        _write(args.out / f"backtest_{args.season}.json",
               export_backtest(build_features(t), args.season))

    done = [r for r in races if r["status"] == "done"]
    _write(args.out / "meta.json", {
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "season": args.season,
        "latest_round": done[-1]["round"] if done else None,
        "latest_race": done[-1]["race_name"] if done else None,
        "prediction_files": preds,
    })
    log.info("site_data written: %s races, %s prediction files", len(races), len(preds))
    return 0


if __name__ == "__main__":
    sys.exit(main())
