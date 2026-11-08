"""Tune on 2023–24 (walk-forward), evaluate the chosen configs on the 2025–26 holdout.

    uv run python scripts/run_evaluation.py

Writes reports/evaluation.json, reports/EVALUATION.md and configs/model_t1.json / model_t2.json.
The holdout is only looked at *after* the configs are picked on the tuning window.
"""

from __future__ import annotations

import itertools
import json
import time
from pathlib import Path

import pandas as pd

from f1pred.data import load_tables
from f1pred.evaluate import (
    empirical_by,
    leader_wins,
    metrics,
    pole_wins,
    races_between,
    walk_forward,
)
from f1pred.features import T1_FEATURES, T2_FEATURES, build_features
from f1pred.model import ModelSpec

TUNE = (2023, 2024)
HOLDOUT = {"holdout 2025–26": (2025, 2026), "2026 only": (2026, 2026)}
WEIGHTS = [1.0, 3.0, 8.0]
PARAMS = {
    "logreg": [{"C": 0.03}, {"C": 0.3}],
    "lgbm": [
        {"n_estimators": 200, "num_leaves": 7, "min_child_samples": 60},
        {"n_estimators": 400, "num_leaves": 15, "min_child_samples": 30, "learning_rate": 0.02},
    ],
}
STAGES = {"t1": T1_FEATURES, "t2": T2_FEATURES}
BASELINES = {
    "t1": {"B2 leader wins": leader_wins, "B2p P(win | standings)": empirical_by("ds_pos")},
    "t2": {"B1 pole wins": pole_wins, "B1p P(win | grid)": empirical_by("grid_f")},
}
KEEP = ["winner_acc", "podium_hit", "logloss_win", "brier_win", "logloss_podium", "races"]


def run(frame, predictor, window, every=1):
    return {k: round(float(v), 4) for k, v in
            metrics(walk_forward(frame, predictor, races_between(frame, *window),
                                 retrain_every=every)).items() if k in KEEP}


def main() -> None:
    t0 = time.time()
    frame = build_features(load_tables())
    report: dict = {"tuning": [], "holdout": [], "chosen": {}}

    for stage, feats in STAGES.items():
        best: dict[str, tuple[float, ModelSpec]] = {}
        for kind, plist in PARAMS.items():
            for params, w in itertools.product(plist, WEIGHTS):
                spec = ModelSpec(kind, feats, same_era_weight=w, params=params)
                m = run(frame, spec.as_predictor(), TUNE, every=2)
                report["tuning"].append({"stage": stage, "kind": kind, "params": params,
                                         "same_era_weight": w, **m})
                print(f"[{time.time() - t0:5.0f}s] tune {stage} {kind} {params} w={w}: "
                      f"acc={m['winner_acc']:.3f} ll={m['logloss_win']:.3f}")
                if kind not in best or m["logloss_win"] < best[kind][0]:
                    best[kind] = (m["logloss_win"], spec)
        for name, pred in BASELINES[stage].items():
            report["tuning"].append({"stage": stage, "kind": name, **run(frame, pred, TUNE)})

        overall = min(best.values(), key=lambda x: x[0])[1]
        report["chosen"][stage] = {"kind": overall.kind, "params": overall.params,
                                   "same_era_weight": overall.same_era_weight}
        Path("configs").mkdir(exist_ok=True)
        Path(f"configs/model_{stage}.json").write_text(
            json.dumps(report["chosen"][stage], indent=2), encoding="utf-8")

        # Holdout: chosen config per model family + baselines, retrained every race.
        for label, window in HOLDOUT.items():
            for kind, (_, spec) in best.items():
                report["holdout"].append({"stage": stage, "window": label, "model": kind,
                                          "params": spec.params,
                                          "same_era_weight": spec.same_era_weight,
                                          **run(frame, spec.as_predictor(), window)})
            for name, pred in BASELINES[stage].items():
                report["holdout"].append({"stage": stage, "window": label, "model": name,
                                          **run(frame, pred, window)})
            print(f"[{time.time() - t0:5.0f}s] holdout {stage} {label} done")

    Path("reports").mkdir(exist_ok=True)
    Path("reports/evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(report)
    print(f"done in {time.time() - t0:.0f}s")


def write_markdown(report: dict) -> None:
    h = pd.DataFrame(report["holdout"])
    tu = pd.DataFrame(report["tuning"])
    lines = ["# Evaluation", "",
             "Walk-forward: every race is predicted by a model trained only on earlier races.",
             f"Configs were chosen on {TUNE[0]}–{TUNE[1]} (log-loss of the winner), then "
             "evaluated once on the 2025–26 holdout.", "",
             "Metrics: `winner_acc` = top pick wins; `podium_hit` = share of the actual podium "
             "in the predicted top 3; `logloss_win` = −log P(actual winner), lower is better; "
             "`brier_win` = squared error of win probabilities per race.", ""]
    for stage, title in (("t1", "T1 — before qualifying"), ("t2", "T2 — after qualifying")):
        lines += [f"## {title}", "", f"Chosen: `{json.dumps(report['chosen'][stage])}`", ""]
        for window in HOLDOUT:
            sub = h[(h.stage == stage) & (h.window == window)]
            cols = ["model", "same_era_weight"] + KEEP
            lines += [f"### {window}", "", sub[[c for c in cols if c in sub]].to_markdown(
                index=False, floatfmt=".3f"), ""]
        sub = tu[tu.stage == stage].sort_values("logloss_win")
        cols = ["kind", "params", "same_era_weight"] + KEEP
        lines += ["<details><summary>Tuning grid (2023–24)</summary>", "",
                  sub[[c for c in cols if c in sub]].to_markdown(index=False, floatfmt=".3f"),
                  "", "</details>", ""]
    Path("reports/EVALUATION.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
