"""Tune on 2023–24 (walk-forward), evaluate the chosen configs once on the 2025–26 holdout.

    uv run python scripts/run_evaluation.py

Compares, for each stage (before / after qualifying):
- feature sets: "base" (Phase 2) vs "plus" (+ weather forecast, rain/street records, Elo);
- models: logistic regression, LightGBM classifiers, LightGBM learning-to-rank;
- era weight for the current rules era (1 vs 3).

Selection uses only 2023–24 (log-loss of the winner). The holdout is looked at afterwards.
Writes reports/evaluation.json, reports/EVALUATION.md, configs/model_t1.json / model_t2.json.
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
from f1pred.features import (
    T1_FEATURES,
    T1_FEATURES_PLUS,
    T2_FEATURES,
    T2_FEATURES_PLUS,
    build_features,
)
from f1pred.model import ModelSpec

TUNE = (2023, 2024)
HOLDOUT = {"holdout 2025–26": (2025, 2026), "2026 only": (2026, 2026)}
WEIGHTS = [1.0, 3.0]
PARAMS = {
    "logreg": [{"C": 0.03}],
    "lgbm": [{"n_estimators": 200, "num_leaves": 7, "min_child_samples": 60}],
    "rank": [
        {"n_estimators": 200, "num_leaves": 7, "min_child_samples": 40},
        {"n_estimators": 400, "num_leaves": 15, "min_child_samples": 30, "learning_rate": 0.02},
    ],
}
FEATURES = {
    "t1": {"base": T1_FEATURES, "plus": T1_FEATURES_PLUS},
    "t2": {"base": T2_FEATURES, "plus": T2_FEATURES_PLUS},
}
BASELINES = {
    "t1": {"B2 leader wins": leader_wins, "B2p P(win | standings)": empirical_by("ds_pos")},
    "t2": {"B1 pole wins": pole_wins, "B1p P(win | grid)": empirical_by("grid_f")},
}
KEEP = [
    "winner_acc",
    "winner_top3",
    "podium_hit",
    "logloss_win",
    "brier_win",
    "logloss_podium",
    "races",
]


def run(frame, predictor, window, every=1):
    m = metrics(walk_forward(frame, predictor, races_between(frame, *window), retrain_every=every))
    return {k: round(float(v), 4) for k, v in m.items() if k in KEEP}


def describe(spec: ModelSpec) -> dict:
    return {
        "kind": spec.kind,
        "feature_set": spec.feature_set,
        "params": spec.params,
        "same_era_weight": spec.same_era_weight,
    }


def main() -> None:
    t0 = time.time()
    frame = build_features(load_tables())
    report: dict = {"tuning": [], "holdout": [], "chosen": {}}

    for stage, sets in FEATURES.items():
        results: list[tuple[float, ModelSpec, dict]] = []
        for (fset, feats), (kind, plist) in itertools.product(sets.items(), PARAMS.items()):
            for params, w in itertools.product(plist, WEIGHTS):
                spec = ModelSpec(kind, feats, same_era_weight=w, params=params, feature_set=fset)
                m = run(frame, spec.as_predictor(), TUNE, every=2)
                report["tuning"].append({"stage": stage, **describe(spec), **m})
                results.append((m["logloss_win"], spec, m))
                print(
                    f"[{time.time() - t0:5.0f}s] tune {stage} {fset:4s} {kind:6s} w={w} {params}: "
                    f"top1={m['winner_acc']:.3f} top3={m['winner_top3']:.3f} "
                    f"ll={m['logloss_win']:.3f}",
                    flush=True,
                )
        for name, pred in BASELINES[stage].items():
            report["tuning"].append({"stage": stage, "kind": name, **run(frame, pred, TUNE)})

        results.sort(key=lambda x: x[0])
        chosen = results[0][1]
        report["chosen"][stage] = describe(chosen)
        Path("configs").mkdir(exist_ok=True)
        Path(f"configs/model_{stage}.json").write_text(
            json.dumps(describe(chosen), indent=2), encoding="utf-8"
        )
        # Holdout: the chosen config, the best "base" config (Phase 2 equivalent) and baselines.
        best_base = next(s for _, s, _ in results if s.feature_set == "base")
        contenders = {"chosen": chosen, "best base": best_base}
        for label, window in HOLDOUT.items():
            for role, spec in contenders.items():
                if role == "best base" and spec is chosen:
                    continue
                report["holdout"].append(
                    {
                        "stage": stage,
                        "window": label,
                        "role": role,
                        "model": spec.kind,
                        **describe(spec),
                        **run(frame, spec.as_predictor(), window),
                    }
                )
            for name, pred in BASELINES[stage].items():
                report["holdout"].append(
                    {
                        "stage": stage,
                        "window": label,
                        "role": "baseline",
                        "model": name,
                        **run(frame, pred, window),
                    }
                )
            print(f"[{time.time() - t0:5.0f}s] holdout {stage} {label} done", flush=True)

    Path("reports").mkdir(exist_ok=True)
    Path("reports/evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown(report)
    print(f"done in {time.time() - t0:.0f}s")


def write_markdown(report: dict) -> None:
    h = pd.DataFrame(report["holdout"])
    tu = pd.DataFrame(report["tuning"])
    lines = [
        "# Evaluation",
        "",
        "Walk-forward: every race is predicted by a model trained only on earlier races.",
        f"Configs were chosen on {TUNE[0]}–{TUNE[1]} (log-loss of the winner), then evaluated "
        "once on the 2025–26 holdout.",
        "",
        "- `winner_acc`: the favourite won. `winner_top3`: the winner was among our 3 most "
        "likely. `podium_hit`: share of the podium in our predicted top 3. `logloss_win`: "
        "−log P(actual winner), lower is better.",
        "- Feature sets: `base` = Phase 2; `plus` = + weather forecast, rain/street records, "
        "racecraft, Elo ratings.",
        "",
    ]
    for stage, title in (("t1", "Before qualifying (T1)"), ("t2", "After qualifying (T2)")):
        lines += [f"## {title}", "", f"Chosen: `{json.dumps(report['chosen'][stage])}`", ""]
        for window in HOLDOUT:
            sub = h[(h.stage == stage) & (h.window == window)]
            cols = ["role", "model", "feature_set", "same_era_weight"] + KEEP
            lines += [
                f"### {window}",
                "",
                sub[[c for c in cols if c in sub]].to_markdown(index=False, floatfmt=".3f"),
                "",
            ]
        sub = tu[tu.stage == stage].sort_values("logloss_win")
        cols = ["kind", "feature_set", "params", "same_era_weight"] + KEEP
        lines += [
            "<details><summary>Tuning grid (2023–24)</summary>",
            "",
            sub[[c for c in cols if c in sub]].to_markdown(index=False, floatfmt=".3f"),
            "",
            "</details>",
            "",
        ]
    old = Path("reports/EVALUATION.md")
    notes = ""
    if old.exists() and "## Reading the results" in old.read_text(encoding="utf-8"):
        notes = old.read_text(encoding="utf-8").split("## Reading the results", 1)[1]
        notes = "## Reading the results" + notes
    Path("reports/EVALUATION.md").write_text("\n".join(lines) + "\n" + notes, encoding="utf-8")


if __name__ == "__main__":
    main()
