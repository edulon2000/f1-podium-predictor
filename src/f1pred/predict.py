"""Predict a race and score past predictions.

    uv run f1pred-predict --season 2026 --round 21 --stage t1     # after practice
    uv run f1pred-predict --season 2026 --round 21 --stage t2     # after qualifying
    uv run f1pred-score   --season 2026 --round 21                # after the race

Predictions go to predictions/<season>_R<round>_<stage>.json/.md — commit them before the race
so the out-of-sample record is verifiable.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd

from f1pred.data import load_tables
from f1pred.evaluate import metrics, normalize
from f1pred.features import T1_FEATURES, T2_FEATURES, build_features
from f1pred.model import ModelSpec

log = logging.getLogger("f1pred.predict")
STAGE_FEATURES = {"t1": T1_FEATURES, "t2": T2_FEATURES}
DEFAULT_SPEC = {"kind": "logreg", "params": {"C": 0.1}, "same_era_weight": 3.0}


def load_spec(stage: str, config_dir: Path) -> ModelSpec:
    path = config_dir / f"model_{stage}.json"
    cfg = json.loads(path.read_text(encoding="utf-8")) if path.exists() else DEFAULT_SPEC
    if not path.exists():
        log.warning("%s not found — using default spec %s (run scripts/run_evaluation.py)",
                    path, DEFAULT_SPEC)
    return ModelSpec(cfg["kind"], STAGE_FEATURES[stage], cfg["same_era_weight"], cfg["params"])


def predict_race(t: dict, season: int, rnd: int, stage: str, spec: ModelSpec,
                 entries: pd.DataFrame | None = None) -> tuple[pd.DataFrame, dict]:
    frame = build_features(t, target=(season, rnd), entries=entries)
    test = frame[(frame.season == season) & (frame["round"] == rnd)].copy()
    if test.empty:
        raise ValueError(f"{season} R{rnd} is not in the calendar")
    idx = test["race_idx"].iloc[0]
    train = frame[frame["win"].notna() & (frame["race_idx"] < idx)]

    warnings = []
    if stage == "t2":
        q = t["qualifying"]
        has_q = ((q.season == season) & (q["round"] == rnd)).any()
        g = t.get("of1_grid")
        has_g = g is not None and ((g.season == season) & (g["round"] == rnd)).any()
        has_r = test["grid"].notna().any()
        if not (has_q or has_g or has_r):
            raise ValueError(f"No qualifying/grid data for {season} R{rnd} yet — "
                             "re-run the ingestion after qualifying, or use --stage t1")
    if season >= 2023 and test["has_practice"].sum() == 0:
        warnings.append("no practice data for this race (run f1pred-ingest-openf1 after FP)")

    fitted = spec.fit(train, season)
    pred = spec.predict(fitted, test)
    out = pd.concat([test[["season", "round", "driver_id", "constructor_id", "grid_f",
                           "win", "podium", "finish_pos"]].reset_index(drop=True), pred], axis=1)
    out["p_win"] = normalize(out, "p_win", 1.0)
    out["p_podium"] = normalize(out, "p_podium", 3.0)
    out = out.sort_values("p_win", ascending=False).reset_index(drop=True)

    races = t["races"]
    race = races[(races.season == season) & (races["round"] == rnd)].iloc[0]
    meta = {
        "season": season, "round": rnd, "race_name": race["race_name"],
        "race_start_utc": str(race["race_start_utc"]), "stage": stage,
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "model": {"kind": spec.kind, "params": spec.params,
                  "same_era_weight": spec.same_era_weight},
        "train_races": int(train["race_idx"].nunique()),
        "train_until": f"{int(train.season.iloc[-1])} R{int(train['round'].iloc[-1])}",
        "warnings": warnings,
    }
    return out, meta


def write_prediction(out: pd.DataFrame, meta: dict, out_dir: Path, t: dict) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{meta['season']}_R{meta['round']:02d}_{meta['stage']}"
    names = t["drivers"].set_index("driver_id")
    teams = t["constructors"].set_index("constructor_id")["name"]
    table = out.assign(
        driver=out["driver_id"].map(lambda d: f"{names.loc[d, 'given_name']} "
                                              f"{names.loc[d, 'family_name']}"
                                    if d in names.index else d),
        team=out["constructor_id"].map(teams).fillna(out["constructor_id"]),
    )
    payload = {**meta, "predictions": table[["driver_id", "constructor_id", "p_win",
                                             "p_podium"]].round(4).to_dict("records")}
    if meta["stage"] == "t2":
        for rec, g in zip(payload["predictions"], table["grid_f"], strict=True):
            rec["grid"] = None if pd.isna(g) else int(g)
    (out_dir / f"{stem}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    cols = ["driver", "team"] + (["grid_f"] if meta["stage"] == "t2" else []) + \
        ["p_win", "p_podium"]
    md = table[cols].rename(columns={"grid_f": "grid", "p_win": "P(win)",
                                     "p_podium": "P(podium)"}).copy()
    md["P(win)"] = (md["P(win)"] * 100).map("{:.1f}%".format)
    md["P(podium)"] = (md["P(podium)"] * 100).map("{:.1f}%".format)
    md.index = range(1, len(md) + 1)
    top3 = ", ".join(table["driver"].head(3))
    stage_txt = "before qualifying" if meta["stage"] == "t1" else "after qualifying"
    lines = [f"# {meta['season']} {meta['race_name']} — prediction {stage_txt}", "",
             f"- Generated: {meta['generated_at']}",
             f"- Race start (UTC): {meta['race_start_utc']}",
             f"- Model: `{json.dumps(meta['model'])}`, trained on {meta['train_races']} races "
             f"(up to {meta['train_until']})",
             f"- Predicted winner: **{table['driver'].iloc[0]}** "
             f"({table['p_win'].iloc[0] * 100:.1f}%); likely podium: {top3}", ""]
    lines += [f"- ⚠️ {w}" for w in meta["warnings"]]
    lines += ["", md.to_markdown(), ""]
    path = out_dir / f"{stem}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def score(t: dict, season: int, rnd: int, pred_dir: Path) -> pd.DataFrame:
    res = t["results"]
    actual = res[(res.season == season) & (res["round"] == rnd)]
    if actual.empty:
        raise ValueError(f"No results for {season} R{rnd} yet")
    rows = []
    for path in sorted(pred_dir.glob(f"{season}_R{rnd:02d}_t*.json")):
        p = json.loads(path.read_text(encoding="utf-8"))
        df = pd.DataFrame(p["predictions"]).merge(
            actual[["driver_id", "position"]], on="driver_id", how="left")
        df["season"], df["round"] = season, rnd
        df["win"] = (df["position"] == 1).astype(float)
        df["podium"] = (df["position"] <= 3).astype(float)
        m = metrics(df)
        winner = actual.loc[actual.position == 1, "driver_id"].iloc[0]
        rows.append({"race": f"{season} R{rnd}", "stage": p["stage"],
                     "predicted": df.sort_values("p_win").iloc[-1]["driver_id"],
                     "actual": winner, "p_actual_winner": round(m["p_winner"], 3),
                     "winner_correct": bool(m["winner_acc"]),
                     "podium_hit": round(m["podium_hit"], 3)})
    if not rows:
        raise FileNotFoundError(f"no prediction files for {season} R{rnd} in {pred_dir}")
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--season", type=int, required=True)
    p.add_argument("--round", dest="rnd", type=int, required=True)
    p.add_argument("--stage", choices=["t1", "t2"], required=True)
    p.add_argument("--entries", type=Path, help="CSV with driver_id,constructor_id")
    p.add_argument("--data-dir", type=Path, default=Path("data"))
    p.add_argument("--config-dir", type=Path, default=Path("configs"))
    p.add_argument("--out", type=Path, default=Path("predictions"))
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    t = load_tables(args.data_dir)
    entries = pd.read_csv(args.entries) if args.entries else None
    try:
        out, meta = predict_race(t, args.season, args.rnd, args.stage,
                                 load_spec(args.stage, args.config_dir), entries)
    except ValueError as exc:
        log.error("%s", exc)
        return 1
    path = write_prediction(out, meta, args.out, t)
    for w in meta["warnings"]:
        log.warning(w)
    print(path.read_text(encoding="utf-8"))
    return 0


def score_main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Score saved predictions against the result")
    p.add_argument("--season", type=int, required=True)
    p.add_argument("--round", dest="rnd", type=int, required=True)
    p.add_argument("--data-dir", type=Path, default=Path("data"))
    p.add_argument("--out", type=Path, default=Path("predictions"))
    args = p.parse_args(argv)
    try:
        df = score(load_tables(args.data_dir), args.season, args.rnd, args.out)
    except (ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    board = args.out / "scoreboard.csv"
    old = pd.read_csv(board) if board.exists() else pd.DataFrame()
    if len(old):
        old = old[old["race"] != df["race"].iloc[0]]
    pd.concat([old, df], ignore_index=True).to_csv(board, index=False)
    print(df.to_markdown(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
