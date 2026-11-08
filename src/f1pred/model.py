"""Models: logistic regression and LightGBM, each fitting one classifier per target.

Era weighting: rows from the same regulation era as the race being predicted get weight
`same_era_weight`; older eras get 1. On 2023–24 this means "2022+ rows count more", the closest
analogue to "2026 rows count more" that can actually be validated before 2026.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from f1pred.features import era_of


def era_weights(train: pd.DataFrame, target_season: int, same_era_weight: float) -> np.ndarray:
    target_era = int(era_of(target_season)[0])
    return np.where(train["era"].to_numpy() == target_era, same_era_weight, 1.0)


@dataclass
class ModelSpec:
    kind: str  # "logreg" | "lgbm"
    features: list[str]
    same_era_weight: float = 1.0
    params: dict = field(default_factory=dict)

    def make(self):
        if self.kind == "logreg":
            return make_pipeline(
                SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
                StandardScaler(),
                LogisticRegression(C=self.params.get("C", 0.1), max_iter=2000),
            )
        if self.kind == "lgbm":
            defaults = dict(n_estimators=300, learning_rate=0.03, num_leaves=15,
                            min_child_samples=40, subsample=0.8, subsample_freq=1,
                            colsample_bytree=0.8, reg_lambda=1.0, verbose=-1, n_jobs=4)
            return LGBMClassifier(**{**defaults, **self.params})
        raise ValueError(self.kind)

    def fit(self, train: pd.DataFrame, target_season: int) -> dict:
        w = era_weights(train, target_season, self.same_era_weight)
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
        return pd.DataFrame({"p_win": fitted["win"].predict_proba(X)[:, 1],
                             "p_podium": fitted["podium"].predict_proba(X)[:, 1]})

    def as_predictor(self):
        def predict(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
            return self.predict(self.fit(train, int(test["season"].iloc[0])), test)
        return predict
