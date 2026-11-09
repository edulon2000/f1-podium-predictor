"""Models.

- "logreg" / "lgbm": one binary classifier per target (win, podium); probabilities are later
  normalised inside each race.
- "rank": a LightGBM learning-to-rank model (lambdarank) that scores drivers *against each other
  within a race*. Scores become win probabilities with a softmax whose temperature is fitted on
  the training races, and podium probabilities come from the same scores via Plackett–Luce
  sampling — so win and podium chances are always consistent with each other.

Era weighting: rows from the same regulation era as the race being predicted get weight
`same_era_weight`; older eras get 1. On 2023–24 this means "2022+ rows count more", the closest
analogue to "2026 rows count more" that can actually be validated before 2026.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, LGBMRanker
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from f1pred.features import era_of

LGBM_DEFAULTS = dict(n_estimators=300, learning_rate=0.03, num_leaves=15, min_child_samples=40,
                     subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0,
                     verbose=-1, n_jobs=4)
RACE = ["season", "round"]
TEMPERATURES = np.exp(np.linspace(np.log(0.1), np.log(5.0), 40))
PODIUM_DRAWS = 4000


def era_weights(train: pd.DataFrame, target_season: int, same_era_weight: float) -> np.ndarray:
    target_era = int(era_of(target_season)[0])
    return np.where(train["era"].to_numpy() == target_era, same_era_weight, 1.0)


def relevance(finish: pd.Series) -> np.ndarray:
    """Ranking label: winner 3, second 2, third 1, everyone else 0."""
    f = finish.to_numpy(dtype=float)
    return np.select([f == 1, f == 2, f == 3], [3, 2, 1], 0)


def _softmax(x: np.ndarray) -> np.ndarray:
    z = np.exp(x - x.max())
    return z / z.sum()


def fit_temperature(scores: np.ndarray, races: np.ndarray, win: np.ndarray) -> float:
    """Temperature maximising the likelihood of the actual winners on the training races."""
    best_t, best_ll = 1.0, -np.inf
    groups = [np.flatnonzero(races == r) for r in np.unique(races)]
    groups = [g for g in groups if win[g].sum() == 1]
    for t in TEMPERATURES:
        ll = sum(np.log(max(_softmax(scores[g] / t)[win[g] == 1][0], 1e-9)) for g in groups)
        if ll > best_ll:
            best_t, best_ll = float(t), ll
    return best_t


def podium_probabilities(strength: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """P(top 3) under Plackett–Luce with the given log-strengths (Gumbel-max sampling)."""
    n = len(strength)
    if n <= 3:
        return np.ones(n)
    g = rng.gumbel(size=(PODIUM_DRAWS, n)) + strength[None, :]
    top3 = np.argpartition(-g, 3, axis=1)[:, :3]
    counts = np.bincount(top3.ravel(), minlength=n)
    return counts / PODIUM_DRAWS


@dataclass
class ModelSpec:
    kind: str  # "logreg" | "lgbm" | "rank"
    features: list[str]
    same_era_weight: float = 1.0
    params: dict = field(default_factory=dict)
    feature_set: str = "base"

    def make(self):
        if self.kind == "logreg":
            return make_pipeline(
                SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
                StandardScaler(),
                LogisticRegression(C=self.params.get("C", 0.1), max_iter=2000),
            )
        if self.kind == "lgbm":
            return LGBMClassifier(**{**LGBM_DEFAULTS, **self.params})
        if self.kind == "rank":
            return LGBMRanker(objective="lambdarank", **{**LGBM_DEFAULTS, **self.params})
        raise ValueError(self.kind)

    def fit(self, train: pd.DataFrame, target_season: int) -> dict:
        w = era_weights(train, target_season, self.same_era_weight)
        if self.kind == "rank":
            train = train.assign(_w=w).sort_values(["race_idx", "driver_id"])
            X = train[self.features].astype(float)
            groups = train.groupby("race_idx", sort=True).size().to_numpy()
            m = self.make()
            m.fit(X, relevance(train["finish_pos"]), group=groups,
                  sample_weight=train["_w"].to_numpy())
            t = fit_temperature(m.predict(X), train["race_idx"].to_numpy(), train["win"].to_numpy())
            return {"win": m, "podium": m, "temperature": t}
        X = train[self.features].astype(float)
        fitted = {}
        for y in ("win", "podium"):
            m = self.make()
            if self.kind == "logreg":
                m.fit(X, train[y].astype(int), logisticregression__sample_weight=w)
            else:
                m.fit(X, train[y].astype(int), sample_weight=w)
            fitted[y] = m
        return fitted

    def predict(self, fitted: dict, test: pd.DataFrame) -> pd.DataFrame:
        X = test[self.features].astype(float)
        if self.kind == "rank":
            scores = fitted["win"].predict(X) / fitted["temperature"]
            p_win = np.zeros(len(test))
            p_pod = np.zeros(len(test))
            rng = np.random.default_rng(0)
            keys = test[RACE].astype(str).agg("-".join, axis=1).to_numpy()
            for k in np.unique(keys):
                idx = np.flatnonzero(keys == k)
                p_win[idx] = _softmax(scores[idx])
                p_pod[idx] = podium_probabilities(scores[idx], rng)
            return pd.DataFrame({"p_win": p_win, "p_podium": p_pod})
        return pd.DataFrame({"p_win": fitted["win"].predict_proba(X)[:, 1],
                             "p_podium": fitted["podium"].predict_proba(X)[:, 1]})

    def as_predictor(self):
        def predict(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
            return self.predict(self.fit(train, int(test["season"].iloc[0])), test)
        return predict
