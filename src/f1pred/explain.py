"""Explain a prediction in plain language: which features pushed a driver's win chance up/down.

For LightGBM we use its native per-row contributions (SHAP values in log-odds); for logistic
regression, coefficient x standardised value. Contributions are reported *relative to the race
average*, so they answer "what set this driver apart from the rest of the field today".
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from f1pred.model import ModelSpec

# Plain-English names shown on the website. Keep them short and free of jargon.
FEATURE_LABELS: dict[str, str] = {
    "ds_pos": "Championship position",
    "ds_pts_share": "Points compared with the championship leader",
    "ds_gap_to_leader": "Points behind the leader",
    "ds_wins": "Wins this season",
    "cs_pos": "Team's championship position",
    "cs_pts_share": "Team points compared with the leading team",
    "standings_from_prev_season": "Season opener (using last year's standings)",
    "drv_finish_ewm3": "Recent finishing positions (last few races)",
    "drv_finish_ewm8": "Finishing positions over a longer stretch",
    "drv_points_ewm5": "Points scored recently",
    "drv_podium_rate10": "Podiums in the last 10 races",
    "drv_win_rate10": "Wins in the last 10 races",
    "drv_dnf_rate20": "How often the driver failed to finish lately",
    "drv_mech_dnf_rate20": "Recent mechanical failures",
    "drv_season_finish_mean": "Average finish this season",
    "drv_quali_gap_ewm5": "Recent qualifying pace",
    "drv_grid_ewm5": "Recent starting positions",
    "drv_teammate_h2h_season": "Beating the teammate in qualifying",
    "team_best_finish_ewm5": "Team's best recent results",
    "team_points_ewm5": "Team's recent points",
    "team_quali_gap_ewm5": "Team's recent qualifying pace",
    "team_mech_dnf_rate20": "Team's recent mechanical failures",
    "circuit_pole_win_rate": "How often pole wins at this track",
    "drv_circuit_finish_mean": "Driver's past results at this track",
    "drv_circuit_starts": "Experience at this track",
    "era": "Rules era",
    "rounds_into_era": "Races since the rules changed",
    "round_frac": "Point of the season",
    "is_sprint_weekend": "Sprint weekend",
    "field_size": "Number of cars",
    "drv_starts": "Career experience",
    "drv_age": "Age",
    "sprint_norm_pre_quali": "Sprint result (before qualifying)",
    "fp_best_gap_pct": "Fastest lap in practice",
    "fp_longrun_gap_pct": "Race pace in practice (long runs)",
    "has_practice": "Practice data available",
    "grid_norm": "Starting position",
    "pole": "Starting from pole",
    "front_row": "Starting on the front row",
    "pit_lane_start": "Starting from the pit lane",
    "quali_gap_pct": "Gap to pole in qualifying",
    "quali_rank_norm": "Qualifying position",
    "reached_q3": "Reached the final part of qualifying",
    "grid_penalty": "Grid penalty",
    "teammate_quali_gap_pct": "Qualifying gap to the teammate",
    "pole_x_circuit": "Pole at a track where pole usually wins",
    "sprint_norm": "Sprint result",
}


def label(feature: str) -> str:
    return FEATURE_LABELS.get(feature, feature.replace("_", " ").capitalize())


def contributions(spec: ModelSpec, fitted: dict, test: pd.DataFrame) -> pd.DataFrame:
    """Per-driver, per-feature contribution to the *win* model (log-odds), centred on the race."""
    X = test[spec.features].astype(float)
    model = fitted["win"]
    if spec.kind == "lgbm":
        raw = model.booster_.predict(X, pred_contrib=True)[:, : len(spec.features)]
    else:
        pre, lr = model[:-1], model[-1]
        z = pre.transform(X)
        parts = z * lr.coef_[0]
        raw = parts[:, : len(spec.features)].copy()
        imputer = model[0]
        if getattr(imputer, "indicator_", None) is not None:
            for j, src in enumerate(imputer.indicator_.features_):
                raw[:, src] += parts[:, len(spec.features) + j]
    df = pd.DataFrame(raw, columns=spec.features, index=test.index)
    return df - df.mean(axis=0)


def top_reasons(contrib_row: pd.Series, n: int = 5) -> list[dict]:
    s = contrib_row[contrib_row.abs() > 1e-6]
    s = s.reindex(s.abs().sort_values(ascending=False).index).head(n)
    return [{"feature": f, "label": label(f), "effect": round(float(v), 3)} for f, v in s.items()]


def _np_float(v):
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else float(v)
