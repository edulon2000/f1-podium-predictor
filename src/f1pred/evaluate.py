"""Walk-forward evaluation, baselines and metrics.

Protocol: for each evaluated race r (in chronological order), fit on every completed race
before r, predict r. Never random splits.

A predictor is a function `(train, test) -> DataFrame[p_win, p_podium]` aligned with `test`.
Probabilities are normalised inside each race (p_win sums to 1, p_podium sums to 3).
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

Predictor = Callable[[pd.DataFrame, pd.DataFrame], pd.DataFrame]
EPS = 1e-3


def normalize(df: pd.DataFrame, col: str, total: float) -> pd.Series:
    p = df[col].clip(lower=1e-6)
    p = p / p.groupby([df["season"], df["round"]]).transform("sum") * total
    return p.clip(upper=1 - 1e-6)


def walk_forward(frame: pd.DataFrame, predictor: Predictor, eval_races: list[tuple[int, int]],
                 retrain_every: int = 1) -> pd.DataFrame:
    """Return per-driver predictions for eval_races, each made from strictly earlier races.

    retrain_every > 1 reuses a fit for the next k-1 races (still trained only on the past).
    """
    hist = frame[frame["win"].notna()]
    out = []
    model_cache = None
    for i, (s, r) in enumerate(eval_races):
        test = frame[(frame.season == s) & (frame["round"] == r)]
        idx = test["race_idx"].iloc[0]
        if i % retrain_every == 0 or model_cache is None:
            train = hist[hist["race_idx"] < idx]
            model_cache = train
        pred = predictor(model_cache, test)
        out.append(pd.concat([test[["season", "round", "driver_id", "win", "podium",
                                    "finish_pos", "grid_f"]].reset_index(drop=True),
                              pred.reset_index(drop=True)], axis=1))
    preds = pd.concat(out, ignore_index=True)
    preds["p_win"] = normalize(preds, "p_win", 1.0)
    preds["p_podium"] = normalize(preds, "p_podium", 3.0)
    return preds


def metrics(preds: pd.DataFrame) -> dict[str, float]:
    rows = []
    for _, g in preds.groupby(["season", "round"]):
        if g["win"].sum() != 1:
            continue
        winner = g.loc[g["win"] == 1].iloc[0]
        top1 = g.sort_values("p_win", ascending=False).iloc[0]
        top3 = set(g.sort_values("p_podium", ascending=False)["driver_id"].head(3))
        actual3 = set(g.loc[g["podium"] == 1, "driver_id"])
        pw = float(np.clip(winner["p_win"], EPS, 1))
        yp = g["podium"].to_numpy()
        pp = np.clip(g["p_podium"].to_numpy(), EPS, 1 - EPS)
        rows.append({
            "winner_acc": float(top1["driver_id"] == winner["driver_id"]),
            "winner_top3": float(winner["driver_id"] in set(g.sort_values("p_win", ascending=False)
                                                            ["driver_id"].head(3))),
            "podium_hit": len(top3 & actual3) / 3,
            "logloss_win": -np.log(pw),
            "brier_win": float(((g["p_win"] - g["win"]) ** 2).sum()),
            "logloss_podium": float(-(yp * np.log(pp) + (1 - yp) * np.log(1 - pp)).mean()),
            "p_winner": pw,
        })
    m = pd.DataFrame(rows)
    out = m.mean().to_dict()
    out["races"] = len(m)
    return out


# ---- baselines ------------------------------------------------------------------------------


def _deterministic(test: pd.DataFrame, rank_col: str) -> pd.DataFrame:
    rank = test[rank_col].rank(method="first", na_option="bottom")
    return pd.DataFrame({"p_win": np.where(rank == 1, 1.0, 1e-6),
                         "p_podium": np.where(rank <= 3, 1.0, 1e-6)})


def pole_wins(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    """B1 (T2): driver starting P1 wins; podium = grid 1-2-3."""
    return _deterministic(test, "grid_f")


def leader_wins(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    """B2 (T1): championship leader after the previous race wins; podium = standings 1-2-3."""
    return _deterministic(test, "ds_pos")


def empirical_by(col: str, cap: int = 20, alpha: float = 1.0) -> Predictor:
    """Calibrated version of a baseline: P(win | col = k) and P(podium | col = k) from history.

    Gives the baselines a meaningful log-loss (a 0/1 prediction has infinite log-loss).
    """
    def predict(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
        k_tr = train[col].clip(upper=cap).fillna(cap).round()
        k_te = test[col].clip(upper=cap).fillna(cap).round()
        n = k_tr.value_counts()
        w = train.groupby(k_tr)["win"].sum()
        p = train.groupby(k_tr)["podium"].sum()
        base_w, base_p = train["win"].mean(), train["podium"].mean()
        rate_w = (w + alpha * base_w) / (n + alpha)
        rate_p = (p + alpha * base_p) / (n + alpha)
        return pd.DataFrame({"p_win": k_te.map(rate_w).fillna(base_w).to_numpy(),
                             "p_podium": k_te.map(rate_p).fillna(base_p).to_numpy()})
    return predict


def races_between(frame: pd.DataFrame, first: int, last: int) -> list[tuple[int, int]]:
    done = frame[frame["win"].notna() & frame.season.between(first, last)]
    return sorted({(int(s), int(r)) for s, r in zip(done.season, done["round"], strict=True)})
