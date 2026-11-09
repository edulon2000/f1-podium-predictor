"""Feature builder: one row per (season, round, driver_id).

Two feature sets (see docs/FEATURES.md):
- T1_FEATURES: known before qualifying.
- T2_FEATURES: T1 + qualifying / grid information.

Leakage rule: everything derived from a race's *outcome* (finish position, points, status,
standings after the race) only enters later rows, via `shift(1)` inside each group after sorting
chronologically, or via the "standings after the previous race" join. tests/test_features.py
checks this by perturbing a race's outcome and asserting its own features don't move.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from f1pred.cleaning import add_quali_pace, status_category, team_lineage

KEYS = ["season", "round", "driver_id"]
TARGETS = ["win", "podium", "finish_pos"]

T1_FEATURES = [
    # championship after the previous race
    "ds_pos", "ds_pts_share", "ds_gap_to_leader", "ds_wins", "cs_pos", "cs_pts_share",
    "standings_from_prev_season",
    # driver form (lagged)
    "drv_finish_ewm3", "drv_finish_ewm8", "drv_points_ewm5", "drv_podium_rate10",
    "drv_win_rate10", "drv_dnf_rate20", "drv_mech_dnf_rate20", "drv_season_finish_mean",
    "drv_quali_gap_ewm5", "drv_grid_ewm5", "drv_teammate_h2h_season",
    # team form (lagged, by lineage)
    "team_best_finish_ewm5", "team_points_ewm5", "team_quali_gap_ewm5", "team_mech_dnf_rate20",
    # circuit
    "circuit_pole_win_rate", "drv_circuit_finish_mean", "drv_circuit_starts",
    # context
    "era", "rounds_into_era", "round_frac", "is_sprint_weekend", "field_size",
    "drv_starts", "drv_age",
    # weekend info available before GP qualifying
    "sprint_norm_pre_quali",
    "fp_best_gap_pct", "fp_longrun_gap_pct", "has_practice",
]
T2_ONLY = [
    "grid_norm", "pole", "front_row", "pit_lane_start", "quali_gap_pct", "quali_rank_norm",
    "reached_q3", "grid_penalty", "teammate_quali_gap_pct", "pole_x_circuit", "sprint_norm",
]
T2_FEATURES = T1_FEATURES + T2_ONLY


def era_of(season: pd.Series | int):
    s = pd.Series(season) if not isinstance(season, pd.Series) else season
    return np.select([s <= 2021, s <= 2025], [0, 1], 2)


def _lag(df: pd.DataFrame, by, col: str, how: str, n: float) -> pd.Series:
    """Grouped, strictly-lagged statistic (row's own value never included)."""
    def f(s: pd.Series) -> pd.Series:
        s = s.shift(1)
        if how == "ewm":
            return s.ewm(halflife=n, min_periods=1).mean()
        if how == "roll":
            return s.rolling(int(n), min_periods=1).mean()
        if how == "expanding":
            return s.expanding().mean()
        raise ValueError(how)
    return df.groupby(by, sort=False)[col].transform(f)


def build_features(
    t: dict[str, pd.DataFrame],
    target: tuple[int, int] | None = None,
    entries: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Feature frame for every completed race, plus `target` race if it has no results yet.

    entries: optional DataFrame(driver_id, constructor_id) for the target race; defaults to the
    line-up of the most recent completed race.
    """
    races = t["races"].sort_values(["season", "round"]).reset_index(drop=True)
    races["race_idx"] = np.arange(len(races))
    res = t["results"].copy()

    base = res[["season", "round", "driver_id", "constructor_id", "grid", "position", "points",
                "status"]].copy()
    if target is not None and not ((res.season == target[0]) & (res["round"] == target[1])).any():
        if entries is None:
            last = res.merge(races[["season", "round", "race_idx"]], on=["season", "round"])
            last = last[last.race_idx == last.race_idx.max()]
            entries = last[["driver_id", "constructor_id"]]
        tgt = entries[["driver_id", "constructor_id"]].copy()
        tgt["season"], tgt["round"] = target
        base = pd.concat([base, tgt], ignore_index=True)

    base = base.merge(races[["season", "round", "race_idx", "circuit_id", "race_date",
                             "is_sprint_weekend", "sprint_utc", "quali_utc"]],
                      on=["season", "round"], how="left")
    base = base.sort_values(["race_idx", "driver_id"]).reset_index(drop=True)
    base["lineage"] = base["constructor_id"].map(team_lineage)
    base["field_size"] = base.groupby("race_idx")["driver_id"].transform("size")
    fs1 = (base["field_size"] - 1).clip(lower=1)

    # ---- outcomes (only ever used lagged) ----
    base["finish_pos"] = base["position"].astype("float")
    base["finish_norm"] = (base["finish_pos"] - 1) / fs1
    cat = base["status"].map(lambda s: status_category(s) if isinstance(s, str) else None)
    has_outcome = base["position"].notna()
    base["dnf"] = cat.str.startswith("dnf").astype(float).where(has_outcome)
    base["mech_dnf"] = (cat == "dnf_mechanical").astype(float).where(has_outcome)
    base["win"] = (base["finish_pos"] == 1).astype(float).where(has_outcome)
    base["podium"] = (base["finish_pos"] <= 3).astype(float).where(has_outcome)
    base["pts"] = base["points"].astype(float)

    # ---- qualifying (T2 info for its own race; lagged form for T1) ----
    q = add_quali_pace(t["qualifying"])[["season", "round", "driver_id", "position", "best_q_s",
                                          "quali_gap_pct", "reached_q3"]]
    q = q.rename(columns={"position": "quali_pos_published"})
    base = base.merge(q, on=KEYS, how="left")
    # Jolpica sometimes publishes qualifying positions before the lap times (e.g. right after
    # the session). Fill the best lap from OpenF1's starting grid, which carries it.
    if "of1_grid" in t and len(t["of1_grid"]):
        ql = t["of1_grid"][["season", "round", "driver_id", "quali_lap_s"]]
        ql = base[KEYS].merge(ql, on=KEYS, how="left")["quali_lap_s"].astype(float)
        base["best_q_s"] = base["best_q_s"].fillna(ql)
        fastest = base.groupby("race_idx")["best_q_s"].transform("min")
        gap = ((base["best_q_s"] / fastest - 1) * 100).clip(upper=7.0)
        base["quali_gap_pct"] = base["quali_gap_pct"].fillna(gap)
    base["quali_rank"] = base.groupby("race_idx")["best_q_s"].rank(method="min")
    # no time at all: use the published position, else the back of the grid
    base["quali_rank"] = base["quali_rank"].fillna(base["quali_pos_published"].astype(float))
    base["quali_rank"] = base["quali_rank"].fillna(base["field_size"])
    base["quali_rank_norm"] = (base["quali_rank"] - 1) / fs1
    base["reached_q3"] = base["reached_q3"].astype(float)

    # grid: Jolpica, then OpenF1 starting grid, then qualifying rank
    grid = base["grid"].astype(float)
    if "of1_grid" in t and len(t["of1_grid"]):
        og = t["of1_grid"][["season", "round", "driver_id", "grid_position"]]
        og = base[KEYS].merge(og, on=KEYS, how="left")["grid_position"].astype(float)
        grid = grid.fillna(og)
    grid = grid.fillna(base["quali_rank"])
    base["pit_lane_start"] = (grid == 0).astype(float)
    grid = grid.where(grid != 0, base["field_size"])
    base["grid_f"] = grid
    base["grid_norm"] = (grid - 1) / fs1
    base["pole"] = (grid == 1).astype(float)
    base["front_row"] = (grid <= 2).astype(float)
    base["grid_penalty"] = grid - base["quali_rank"]

    # teammate comparisons (same race, same constructor)
    team_best = base.groupby(["race_idx", "constructor_id"])["best_q_s"]
    mate_q = (team_best.transform("sum") - base["best_q_s"]) / (team_best.transform("count") - 1)
    base["teammate_quali_gap_pct"] = (base["best_q_s"] / mate_q - 1) * 100
    comparable = mate_q.notna() & base["best_q_s"].notna()
    base["beat_mate_q"] = (base["best_q_s"] < mate_q).astype(float).where(comparable)

    # ---- driver form (lagged) ----
    d = "driver_id"
    base["drv_finish_ewm3"] = _lag(base, d, "finish_norm", "ewm", 3)
    base["drv_finish_ewm8"] = _lag(base, d, "finish_norm", "ewm", 8)
    base["drv_points_ewm5"] = _lag(base, d, "pts", "ewm", 5)
    base["drv_podium_rate10"] = _lag(base, d, "podium", "roll", 10)
    base["drv_win_rate10"] = _lag(base, d, "win", "roll", 10)
    base["drv_dnf_rate20"] = _lag(base, d, "dnf", "roll", 20)
    base["drv_mech_dnf_rate20"] = _lag(base, d, "mech_dnf", "roll", 20)
    base["drv_season_finish_mean"] = _lag(base, [d, "season"], "finish_norm", "expanding", 0)
    base["drv_quali_gap_ewm5"] = _lag(base, d, "quali_gap_pct", "ewm", 5)
    base["grid_norm_hist"] = base["grid_norm"].where(has_outcome)
    base["drv_grid_ewm5"] = _lag(base, d, "grid_norm_hist", "ewm", 5)
    base["drv_teammate_h2h_season"] = _lag(base, [d, "season"], "beat_mate_q", "expanding", 0)
    base["drv_starts"] = base.groupby(d).cumcount()

    # ---- team form (lagged, per lineage) ----
    tr = base.groupby(["race_idx", "lineage"]).agg(
        t_best=("finish_norm", "min"), t_pts=("pts", "sum"), t_q=("quali_gap_pct", "min"),
        t_mech=("mech_dnf", "mean"), t_has=("position", "count"),
    ).reset_index().sort_values("race_idx")
    tr.loc[tr.t_has == 0, ["t_best", "t_pts", "t_mech"]] = np.nan  # target race: no outcome
    tr["team_best_finish_ewm5"] = _lag(tr, "lineage", "t_best", "ewm", 5)
    tr["team_points_ewm5"] = _lag(tr, "lineage", "t_pts", "ewm", 5)
    tr["team_quali_gap_ewm5"] = _lag(tr, "lineage", "t_q", "ewm", 5)
    tr["team_mech_dnf_rate20"] = _lag(tr, "lineage", "t_mech", "roll", 20)
    base = base.merge(tr[["race_idx", "lineage", "team_best_finish_ewm5", "team_points_ewm5",
                          "team_quali_gap_ewm5", "team_mech_dnf_rate20"]],
                      on=["race_idx", "lineage"], how="left")

    # ---- circuit ----
    rr = base[base.win == 1][["race_idx", "grid_f"]].rename(columns={"grid_f": "w_grid"})
    rl = races[["race_idx", "circuit_id"]].merge(rr, on="race_idx", how="left")
    rl["won_from_pole"] = (rl["w_grid"] == 1).astype(float).where(rl["w_grid"].notna())
    prior_n = rl.groupby("circuit_id")["won_from_pole"].transform(
        lambda s: s.shift(1).expanding().count()).fillna(0)
    prior_sum = rl.groupby("circuit_id")["won_from_pole"].transform(
        lambda s: s.shift(1).fillna(0).cumsum()).fillna(0)
    glob = rl["won_from_pole"].shift(1).expanding().mean().fillna(0.5)
    k = 3.0  # shrink small circuit samples toward the global rate so far
    rl["circuit_pole_win_rate"] = (prior_sum + k * glob) / (prior_n + k)
    base = base.merge(rl[["race_idx", "circuit_pole_win_rate"]], on="race_idx", how="left")
    base["pole_x_circuit"] = base["pole"] * base["circuit_pole_win_rate"]
    base["drv_circuit_finish_mean"] = _lag(base, [d, "circuit_id"], "finish_norm", "expanding", 0)
    base["drv_circuit_starts"] = base.groupby([d, "circuit_id"]).cumcount()

    # ---- context ----
    base["era"] = era_of(base["season"])
    era_start = base.groupby("era")["race_idx"].transform("min")
    base["rounds_into_era"] = base["race_idx"] - era_start
    n_rounds = races.groupby("season")["round"].max()
    base["round_frac"] = base["round"] / base["season"].map(n_rounds)
    base["is_sprint_weekend"] = base["is_sprint_weekend"].astype(float)
    if "drivers" in t:
        dob = pd.to_datetime(base[d].map(t["drivers"].set_index(d)["date_of_birth"]))
        base["drv_age"] = (pd.to_datetime(base["race_date"]) - dob).dt.days / 365.25

    # ---- sprint ----
    spr = t.get("sprint_results")
    if spr is not None and len(spr):
        sp = spr[KEYS + ["position"]].rename(columns={"position": "sprint_pos"})
        base = base.merge(sp, on=KEYS, how="left")
        base["sprint_norm"] = (base["sprint_pos"] - 1) / fs1
    else:
        base["sprint_norm"] = np.nan
    sprint_t = pd.to_datetime(base["sprint_utc"], utc=True)
    before_q = sprint_t.notna() & (sprint_t < pd.to_datetime(base["quali_utc"], utc=True))
    base["sprint_norm_pre_quali"] = base["sprint_norm"].where(before_q)

    # ---- standings after the previous race ----
    nxt = races[["season", "round"]].copy()
    nxt["next_season"] = nxt["season"].shift(-1)
    nxt["next_round"] = nxt["round"].shift(-1)
    nxt = nxt.dropna()
    base = _join_prev_standings(base, t, nxt)

    # ---- practice pace (OpenF1, 2023+) ----
    base = _practice_features(base, t)

    return base


def _join_prev_standings(base, t, nxt) -> pd.DataFrame:
    def shift_to_next(df):
        out = df.merge(nxt, on=["season", "round"], how="inner")
        out["from_prev_season"] = (out["next_season"] != out["season"]).astype(float)
        out = out.drop(columns=["season", "round"]).rename(
            columns={"next_season": "season", "next_round": "round"})
        out[["season", "round"]] = out[["season", "round"]].astype(int)
        return out

    ds = t["driver_standings"].copy()
    lead = ds.groupby(["season", "round"])["points"].transform("max").replace(0, np.nan)
    ds["ds_pts_share"] = ds["points"] / lead
    ds["ds_gap_to_leader"] = lead - ds["points"]
    ds = ds.rename(columns={"position": "ds_pos", "wins": "ds_wins"})
    ds = shift_to_next(ds[["season", "round", "driver_id", "ds_pos", "ds_pts_share",
                           "ds_gap_to_leader", "ds_wins"]])
    flag = ds.groupby(["season", "round"])["from_prev_season"].first().rename(
        "standings_from_prev_season").reset_index()
    base = base.merge(ds.drop(columns="from_prev_season"), on=KEYS, how="left")
    base = base.merge(flag, on=["season", "round"], how="left")

    cs = t["constructor_standings"].copy()
    lead = cs.groupby(["season", "round"])["points"].transform("max").replace(0, np.nan)
    cs["cs_pts_share"] = cs["points"] / lead
    cs["lineage"] = cs["constructor_id"].map(team_lineage)
    cs = cs.rename(columns={"position": "cs_pos"})
    cs = shift_to_next(cs[["season", "round", "lineage", "cs_pos", "cs_pts_share"]])
    cs = cs.drop(columns="from_prev_season").drop_duplicates(["season", "round", "lineage"])
    return base.merge(cs, on=["season", "round", "lineage"], how="left")


def _practice_features(base: pd.DataFrame, t: dict) -> pd.DataFrame:
    laps = t.get("of1_laps")
    if laps is None or not len(laps):
        base["fp_best_gap_pct"] = np.nan
        base["fp_longrun_gap_pct"] = np.nan
        base["has_practice"] = 0.0
        return base
    lp = laps.dropna(subset=["lap_duration", "driver_id"])
    lp = lp[lp["is_pit_out_lap"] != True]  # noqa: E712 (column may hold None)
    sk = ["season", "round", "session_name"]

    best = lp.groupby(sk + ["driver_id"])["lap_duration"].min().rename("best").reset_index()
    best["gap"] = (best["best"] / best.groupby(sk)["best"].transform("min") - 1) * 100
    fp_best = best.groupby(KEYS)["gap"].min().clip(upper=7).rename("fp_best_gap_pct")

    # long runs: laps inside stints of >= 5 laps, within 107% of the driver's session best
    st = t.get("of1_stints")
    fp_long = pd.Series(dtype=float, name="fp_longrun_gap_pct")
    if st is not None and len(st):
        s = st.dropna(subset=["lap_start", "lap_end", "driver_id"]).copy()
        s = s[(s["lap_end"] - s["lap_start"]) >= 4]
        m = lp.merge(s[sk + ["driver_id", "stint_number", "lap_start", "lap_end"]],
                     on=sk + ["driver_id"])
        m = m[(m["lap_number"] > m["lap_start"]) & (m["lap_number"] <= m["lap_end"])]
        m = m.merge(best[sk + ["driver_id", "best"]], on=sk + ["driver_id"])
        m = m[m["lap_duration"] <= m["best"] * 1.07]
        stint_med = m.groupby(sk + ["driver_id", "stint_number"])["lap_duration"].median()
        drv = stint_med.groupby(sk + ["driver_id"]).min().rename("lr").reset_index()
        drv["gap"] = (drv["lr"] / drv.groupby(sk)["lr"].transform("min") - 1) * 100
        fp_long = drv.groupby(KEYS)["gap"].mean().clip(upper=7).rename("fp_longrun_gap_pct")

    base = base.merge(fp_best.reset_index(), on=KEYS, how="left")
    base = base.merge(fp_long.reset_index(), on=KEYS, how="left") if len(fp_long) else \
        base.assign(fp_longrun_gap_pct=np.nan)
    base["has_practice"] = base["fp_best_gap_pct"].notna().astype(float)
    return base
