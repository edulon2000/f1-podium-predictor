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

import numpy as np
import pandas as pd

from f1pred.cleaning import status_category
from f1pred.data import load_tables
from f1pred.evaluate import normalize
from f1pred.explain import contributions, top_reasons
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


STATUS_TEXT = {
    "finished": "Finished", "lapped": "Finished, lapped", "dnf_mechanical": "Retired (car problem)",
    "dnf_accident": "Retired (crash or damage)", "dnf_unknown": "Retired", "dns": "Did not start",
    "dsq": "Disqualified",
}


def _num(v: Any, digits: int = 4) -> float | None:
    return None if v is None or pd.isna(v) else round(float(v), digits)


def _int(v: Any) -> int | None:
    return None if v is None or pd.isna(v) else int(v)


def export_details(t: dict, frame: pd.DataFrame, season: int, pred_dir: Path
                   ) -> tuple[dict[int, dict], dict[str, list]]:
    """Per-race detail pages + the backtest summary.

    Every completed race of the season is re-predicted from earlier races only (walk-forward),
    for both stages, keeping the fitted model so we can also explain each prediction.
    """
    drivers = driver_index(t)
    teams = t["constructors"].set_index("constructor_id")["name"].to_dict()
    races = t["races"][t["races"].season == season].set_index("round")
    circuits = t["circuits"].set_index("circuit_id")
    res = t["results"][t["results"].season == season]
    weather = t.get("weather", t.get("of1_weather"))
    specs = {s: load_spec(s, Path("configs")) for s in ("t1", "t2")}
    hist = frame[frame["win"].notna()]
    details: dict[int, dict] = {}
    summary: dict[str, list] = {"t1": [], "t2": []}

    def live_block(rnd: int) -> dict:
        out = {}
        for path in sorted(pred_dir.glob(f"{season}_R{rnd:02d}_t*.json")):
            pj = json.loads(path.read_text(encoding="utf-8"))
            out[pj["stage"]] = {"generated_at": pj["generated_at"], "model": pj["model"],
                                "predictions": pj["predictions"]}
        return out

    def header(rnd: int) -> dict:
        r = races.loc[rnd]
        c = circuits.loc[r.circuit_id] if r.circuit_id in circuits.index else None
        w = None
        if weather is not None and len(weather):
            ww = weather[(weather.season == season) & (weather["round"] == rnd)]
            if len(ww):
                x = ww.iloc[0]
                w = {}
                for k, v in x.drop(labels=["season", "round"]).items():
                    if v is None or (not isinstance(v, str) and pd.isna(v)):
                        w[k] = None
                    elif isinstance(v, (bool, np.bool_)):
                        w[k] = bool(v)
                    elif isinstance(v, (int, float, np.integer, np.floating)):
                        w[k] = round(float(v), 2)
                    else:
                        w[k] = v
        return {"season": season, "round": int(rnd), "race_name": r.race_name,
                "circuit_name": None if c is None else c["circuit_name"],
                "locality": None if c is None else c["locality"],
                "country": None if c is None else c["country"],
                "race_start_utc": _ts(r.race_start_utc),
                "is_sprint_weekend": bool(r.is_sprint_weekend),
                "weather": w}

    done_rounds = sorted(set(res["round"].astype(int)))
    for rnd in done_rounds:
        test = frame[(frame.season == season) & (frame["round"] == rnd)].reset_index(drop=True)
        idx = test["race_idx"].iloc[0]
        train = hist[hist["race_idx"] < idx]
        rr = res[res["round"] == rnd].set_index("driver_id")
        rows = []
        for _, x in test.iterrows():
            d = drivers.get(x.driver_id, {})
            st = rr.loc[x.driver_id, "status"] if x.driver_id in rr.index else None
            cat = status_category(st) if isinstance(st, str) else ""
            rows.append({
                "driver_id": x.driver_id, "name": d.get("name", x.driver_id), "code": d.get("code"),
                "constructor_id": x.constructor_id,
                "team": teams.get(x.constructor_id, x.constructor_id),
                "grid": _int(x.grid_f), "finish": _int(x.finish_pos),
                "status": STATUS_TEXT.get(cat, st),
                "points": _num(x.pts, 1), "quali_position": _int(x.quali_rank),
                "quali_gap_pct": _num(x.quali_gap_pct, 3),
                "practice_best_gap_pct": _num(x.fp_best_gap_pct, 3),
                "practice_longrun_gap_pct": _num(x.fp_longrun_gap_pct, 3),
            })
        stages = {}
        for stage, spec in specs.items():
            fitted = spec.fit(train, season)
            pred = spec.predict(fitted, test)
            pp = pd.concat([test[["season", "round", "driver_id", "win", "podium", "finish_pos",
                                  "grid_f"]], pred], axis=1)
            pp["p_win"] = normalize(pp, "p_win", 1.0)
            pp["p_podium"] = normalize(pp, "p_podium", 3.0)
            contrib = contributions(spec, fitted, test)
            fav = int(pp["p_win"].idxmax())
            win_idx = pp.index[pp["win"] == 1]
            wi = int(win_idx[0]) if len(win_idx) else None
            order = pp["p_win"].rank(ascending=False, method="first").astype(int)
            for i, row in enumerate(rows):
                row[f"{stage}_p_win"] = _num(pp.loc[i, "p_win"])
                row[f"{stage}_p_podium"] = _num(pp.loc[i, "p_podium"])
                row[f"{stage}_rank"] = int(order[i])
            stages[stage] = {
                "model": {"kind": spec.kind, "params": spec.params,
                          "same_era_weight": spec.same_era_weight},
                "train_races": int(train["race_idx"].nunique()),
                "favourite": pp.loc[fav, "driver_id"],
                "favourite_reasons": top_reasons(contrib.loc[fav]),
                "winner_reasons": None if wi is None or wi == fav else top_reasons(contrib.loc[wi]),
            }
            winner = pp[pp.win == 1]
            summary[stage].append({
                "season": season, "round": int(rnd),
                "predicted": pp.loc[fav, "driver_id"], "p_predicted": _num(pp.loc[fav, "p_win"]),
                "actual": None if winner.empty else winner.driver_id.iloc[0],
                "p_actual": None if winner.empty else _num(winner.p_win.iloc[0]),
                "predicted_podium": list(pp.sort_values("p_podium", ascending=False)
                                         .driver_id.head(3)),
                "actual_podium": list(pp[pp.podium == 1].sort_values("finish_pos").driver_id),
                "pole_won": bool((winner.grid_f == 1).any()),
            })
        details[rnd] = {**header(rnd), "status": "done", "kind": "backtest",
                        "drivers": sorted(rows, key=lambda r: r["finish"] or 99),
                        "stages": stages, "live": live_block(rnd)}
        log.info("details %s R%s", season, rnd)

    # upcoming races that already have a live prediction
    for path in sorted(pred_dir.glob(f"{season}_R*_t*.json")):
        rnd = int(path.stem.split("_")[1][1:])
        if rnd in details or rnd not in races.index:
            continue
        details[rnd] = {**header(rnd), "status": "upcoming", "kind": "live", "drivers": [],
                        "stages": {}, "live": live_block(rnd)}
    return details, summary


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
        details, summary = export_details(t, build_features(t), args.season, args.predictions)
        _write(args.out / f"backtest_{args.season}.json", summary)
        for rnd, d in details.items():
            _write(args.out / "races" / f"{args.season}_R{rnd:02d}.json", d)

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
