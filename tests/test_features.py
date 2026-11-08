"""Leakage tests for the feature builder, on a small synthetic championship."""

import numpy as np
import pandas as pd
import pytest

from f1pred.features import T1_FEATURES, T2_FEATURES, build_features

DRIVERS = ["a", "b", "c", "d", "e", "f"]
TEAM = {"a": "t1", "b": "t1", "c": "t2", "d": "t2", "e": "t3", "f": "t3"}
POINTS = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10, 6: 8}


def synthetic(seed=0, seasons=(2025, 2026), rounds=5):
    rng = np.random.default_rng(seed)
    races, res, q, ds, cs = [], [], [], [], []
    for s in seasons:
        cum_d = dict.fromkeys(DRIVERS, 0.0)
        wins = dict.fromkeys(DRIVERS, 0)
        for r in range(1, rounds + 1):
            start = pd.Timestamp(f"{s}-03-01", tz="UTC") + pd.Timedelta(weeks=2 * r)
            races.append({"season": s, "round": r, "circuit_id": f"c{r}",
                          "race_date": start.date().isoformat(), "race_start_utc": start,
                          "quali_utc": start - pd.Timedelta(days=1),
                          "sprint_utc": pd.NaT, "is_sprint_weekend": False})
            qorder = rng.permutation(DRIVERS)
            for i, drv in enumerate(qorder):
                q.append({"season": s, "round": r, "driver_id": drv, "constructor_id": TEAM[drv],
                          "position": i + 1, "q1_s": 80 + i * 0.2 + rng.random() * 0.05,
                          "q2_s": np.nan, "q3_s": np.nan})
            forder = rng.permutation(DRIVERS)
            for i, drv in enumerate(forder):
                pos = i + 1
                res.append({"season": s, "round": r, "driver_id": drv, "constructor_id": TEAM[drv],
                            "grid": int(np.where(qorder == drv)[0][0]) + 1, "position": pos,
                            "points": float(POINTS[pos]),
                            "status": "Finished" if pos < 6 else "Engine"})
                cum_d[drv] += POINTS[pos]
                wins[drv] += pos == 1
            order = sorted(DRIVERS, key=lambda x: -cum_d[x])
            for i, drv in enumerate(order):
                ds.append({"season": s, "round": r, "driver_id": drv, "position": i + 1,
                           "points": cum_d[drv], "wins": wins[drv]})
            team_pts = {}
            for drv in DRIVERS:
                team_pts[TEAM[drv]] = team_pts.get(TEAM[drv], 0) + cum_d[drv]
            for i, (tm, p) in enumerate(sorted(team_pts.items(), key=lambda x: -x[1])):
                cs.append({"season": s, "round": r, "constructor_id": tm, "position": i + 1,
                           "points": p, "wins": 0})
    return {
        "races": pd.DataFrame(races), "results": pd.DataFrame(res),
        "qualifying": pd.DataFrame(q), "driver_standings": pd.DataFrame(ds),
        "constructor_standings": pd.DataFrame(cs),
        "drivers": pd.DataFrame({"driver_id": DRIVERS, "date_of_birth": ["2000-01-01"] * 6}),
    }


def rows(f, s, r):
    return f[(f.season == s) & (f["round"] == r)].set_index("driver_id").sort_index()


def test_outcome_of_race_does_not_leak_into_its_own_features():
    t = synthetic()
    base = build_features(t)
    # Scramble every post-race fact of 2026 R3: results and standings after it.
    t2 = {k: v.copy() for k, v in t.items()}
    m = (t2["results"].season == 2026) & (t2["results"]["round"] == 3)
    t2["results"].loc[m, "position"] = t2["results"].loc[m, "position"].values[::-1]
    t2["results"].loc[m, "points"] = t2["results"].loc[m, "points"].values[::-1]
    t2["results"].loc[m, "status"] = "Collision"
    sm = (t2["driver_standings"].season == 2026) & (t2["driver_standings"]["round"] == 3)
    t2["driver_standings"].loc[sm, "points"] = 999.0
    t2["driver_standings"].loc[sm, "position"] = t2["driver_standings"].loc[sm, "position"] \
        .values[::-1]
    pert = build_features(t2)

    pd.testing.assert_frame_equal(rows(base, 2026, 3)[T2_FEATURES],
                                  rows(pert, 2026, 3)[T2_FEATURES])
    # ...but the next race must see the change (otherwise the features are dead).
    nxt_b, nxt_p = rows(base, 2026, 4)[T1_FEATURES], rows(pert, 2026, 4)[T1_FEATURES]
    assert not nxt_b.equals(nxt_p)


def test_target_race_features_equal_features_from_truncated_history():
    """Features for a race computed *before* it happens == features after it happened."""
    t = synthetic()
    full = build_features(t)
    target = (2026, 4)
    keep = {}
    for k, v in t.items():
        if k in ("races", "drivers"):
            keep[k] = v
        else:
            before = (v.season < target[0]) | ((v.season == target[0]) & (v["round"] < target[1]))
            keep[k] = v[before]
    pre = build_features(keep, target=target)
    pd.testing.assert_frame_equal(rows(full, *target)[T1_FEATURES],
                                  rows(pre, *target)[T1_FEATURES], check_dtype=False)


def test_round_one_uses_previous_season_final_standings():
    f = build_features(synthetic())
    r1 = rows(f, 2026, 1)
    assert (r1["standings_from_prev_season"] == 1).all()
    t = synthetic()
    final = t["driver_standings"]
    final = final[(final.season == 2025) & (final["round"] == 5)].set_index("driver_id")
    assert (r1["ds_pos"] == final["position"].sort_index()).all()


def test_targets_present_for_history_and_absent_for_target():
    t = synthetic()
    keep = {k: (v[v.season == 2025] if k not in ("races", "drivers") else v)
            for k, v in t.items()}
    f = build_features(keep, target=(2026, 1))
    tgt = rows(f, 2026, 1)
    assert len(tgt) == 6 and tgt["win"].isna().all()
    hist = f[f.season == 2025]
    assert hist.groupby("round")["win"].sum().eq(1).all()


@pytest.mark.parametrize("col", ["drv_finish_ewm3", "drv_podium_rate10", "team_points_ewm5"])
def test_first_appearance_has_no_history(col):
    f = build_features(synthetic())
    assert rows(f, 2025, 1)[col].isna().all()
