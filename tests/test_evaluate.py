import numpy as np
import pandas as pd
import pytest

from f1pred.evaluate import empirical_by, metrics, pole_wins, walk_forward
from f1pred.features import T1_FEATURES, build_features
from f1pred.model import ModelSpec
from tests.test_features import synthetic


def frame():
    return build_features(synthetic(seasons=(2024, 2025, 2026), rounds=6))


def test_metrics_perfect_and_wrong():
    df = pd.DataFrame({
        "season": [1] * 3, "round": [1] * 3, "driver_id": ["a", "b", "c"],
        "win": [1, 0, 0], "podium": [1, 1, 1],
        "p_win": [0.9, 0.05, 0.05], "p_podium": [1.0, 1.0, 1.0],
    })
    m = metrics(df)
    assert m["winner_acc"] == 1 and m["podium_hit"] == 1
    assert m["logloss_win"] == pytest.approx(-np.log(0.9))
    df["p_win"] = [0.05, 0.9, 0.05]
    assert metrics(df)["winner_acc"] == 0


def test_walk_forward_never_trains_on_the_race_it_predicts():
    f = frame()
    seen = []

    def spy(train, test):
        seen.append((train["race_idx"].max(), test["race_idx"].iloc[0]))
        return pd.DataFrame({"p_win": np.ones(len(test)), "p_podium": np.ones(len(test))})

    preds = walk_forward(f, spy, [(2026, 2), (2026, 3)])
    assert all(tr < te for tr, te in seen)
    sums = preds.groupby(["season", "round"])["p_win"].sum()
    assert np.allclose(sums, 1.0)
    assert np.allclose(preds.groupby(["season", "round"])["p_podium"].sum(), 3.0)


def test_baselines_and_models_run():
    f = frame()
    races = [(2026, r) for r in range(2, 7)]
    assert metrics(walk_forward(f, pole_wins, races))["races"] == 5
    emp = metrics(walk_forward(f, empirical_by("grid_f"), races))
    assert np.isfinite(emp["logloss_win"])
    for kind in ("logreg", "lgbm"):
        spec = ModelSpec(kind, T1_FEATURES, same_era_weight=2.0,
                         params={"n_estimators": 20} if kind == "lgbm" else {})
        m = metrics(walk_forward(f, spec.as_predictor(), races))
        assert 0 <= m["winner_acc"] <= 1 and np.isfinite(m["logloss_win"])
