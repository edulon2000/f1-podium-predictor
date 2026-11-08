import json

import pandas as pd
import pytest

from f1pred.features import T1_FEATURES, T2_FEATURES
from f1pred.model import ModelSpec
from f1pred.predict import predict_race, score, write_prediction
from tests.test_features import DRIVERS, TEAM, synthetic


def tables_before(t, season, rnd):
    out = {}
    for k, v in t.items():
        if k in ("races", "drivers"):
            out[k] = v
        else:
            out[k] = v[(v.season < season) | ((v.season == season) & (v["round"] < rnd))]
    out["drivers"] = pd.DataFrame({"driver_id": DRIVERS, "given_name": DRIVERS,
                                   "family_name": [d.upper() for d in DRIVERS],
                                   "date_of_birth": ["2000-01-01"] * 6})
    out["constructors"] = pd.DataFrame({"constructor_id": sorted(set(TEAM.values())),
                                        "name": ["T1", "T2", "T3"]})
    out["races"] = out["races"].assign(race_name="GP")
    return out


SPEC_T1 = ModelSpec("logreg", T1_FEATURES, 2.0, {"C": 0.1})


def test_t1_prediction_for_future_race_and_files(tmp_path):
    t = tables_before(synthetic(), 2026, 4)
    out, meta = predict_race(t, 2026, 4, "t1", SPEC_T1)
    assert len(out) == 6 and out["p_win"].sum() == pytest.approx(1)
    assert out["p_podium"].sum() == pytest.approx(3)
    assert meta["train_until"] == "2026 R3"
    md = write_prediction(out, meta, tmp_path, t)
    payload = json.loads((tmp_path / "2026_R04_t1.json").read_text(encoding="utf-8"))
    assert len(payload["predictions"]) == 6
    assert "Predicted winner" in md.read_text(encoding="utf-8")


def test_t2_requires_qualifying():
    t = tables_before(synthetic(), 2026, 4)
    with pytest.raises(ValueError, match="No qualifying"):
        predict_race(t, 2026, 4, "t2", ModelSpec("logreg", T2_FEATURES, 1.0, {"C": 0.1}))
    full = synthetic()
    q = full["qualifying"]
    t["qualifying"] = pd.concat([t["qualifying"], q[(q.season == 2026) & (q["round"] == 4)]])
    out, _ = predict_race(t, 2026, 4, "t2", ModelSpec("logreg", T2_FEATURES, 1.0, {"C": 0.1}))
    assert out["grid_f"].notna().all()


def test_score_after_race(tmp_path):
    full = synthetic()
    t = tables_before(full, 2026, 4)
    out, meta = predict_race(t, 2026, 4, "t1", SPEC_T1)
    write_prediction(out, meta, tmp_path, t)
    t_after = tables_before(full, 2026, 5)
    board = score(t_after, 2026, 4, tmp_path)
    assert board.iloc[0]["stage"] == "t1"
    res = full["results"]
    winner = res[(res.season == 2026) & (res["round"] == 4) & (res.position == 1)].driver_id.iloc[0]
    assert board.iloc[0]["actual"] == winner
