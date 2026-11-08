import pandas as pd
import pytest

from f1pred.cleaning import add_quali_pace, status_category, team_lineage


@pytest.mark.parametrize("status,cat", [
    ("Finished", "finished"), ("+1 Lap", "lapped"), ("+8 Laps", "lapped"), ("Lapped", "lapped"),
    ("Engine", "dnf_mechanical"), ("Power Unit", "dnf_mechanical"),
    ("Collision", "dnf_accident"), ("Retired", "dnf_unknown"),
    ("Did not start", "dns"), ("Disqualified", "dsq"), (None, "dnf_unknown"),
])
def test_status_category(status, cat):
    assert status_category(status) == cat


def test_team_lineage():
    assert team_lineage("toro_rosso") == team_lineage("rb") == "faenza"
    assert team_lineage("audi") == "hinwil"
    assert team_lineage("ferrari") == "ferrari"


def test_quali_pace_uses_best_time_not_position():
    q = pd.DataFrame({
        "season": [2024] * 3, "round": [15] * 3, "driver_id": ["a", "b", "c"],
        "position": [10, 10, 1],  # duplicated position, as in the real data
        "q1_s": [71.3, None, 70.0], "q2_s": [70.9, 70.7, None], "q3_s": [None, 70.6, None],
    })
    out = add_quali_pace(q).set_index("driver_id")
    assert out.loc["c", "quali_gap_pct"] == 0
    assert out.loc["b", "quali_gap_pct"] == pytest.approx((70.6 / 70.0 - 1) * 100)
    assert out.loc["b", "reached_q3"] and not out.loc["a", "reached_q3"]
