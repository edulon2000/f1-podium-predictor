"""Cleaning maps: result status categories, team lineage, qualifying pace from lap times."""

from __future__ import annotations

import re

import pandas as pd

# --- status ----------------------------------------------------------------------------------

DNS = {"Did not start", "Withdrew", "Illness"}
DSQ = {"Disqualified", "Excluded"}
ACCIDENT = {"Collision", "Accident", "Collision damage", "Spun off", "Damage", "Debris",
            "Puncture", "Front wing", "Rear wing"}
# 2024+ data often reports a generic "Retired" with no cause, so it can't be split further.
UNKNOWN_DNF = {"Retired"}


def status_category(status: str | None) -> str:
    """finished | lapped | dnf_mechanical | dnf_accident | dnf_unknown | dns | dsq."""
    if status is None or status == "":
        return "dnf_unknown"
    if status == "Finished":
        return "finished"
    if status == "Lapped" or re.fullmatch(r"\+\d+ Laps?", status):
        return "lapped"
    if status in DNS:
        return "dns"
    if status in DSQ:
        return "dsq"
    if status in ACCIDENT:
        return "dnf_accident"
    if status in UNKNOWN_DNF:
        return "dnf_unknown"
    return "dnf_mechanical"  # Engine, Gearbox, Hydraulics, Power Unit, ... (long tail)


# --- team lineage ----------------------------------------------------------------------------

# Same factory / organisation across rebrands, so team history carries over.
LINEAGE = {
    "toro_rosso": "faenza", "alphatauri": "faenza", "rb": "faenza",
    "force_india": "silverstone", "racing_point": "silverstone", "aston_martin": "silverstone",
    "lotus_f1": "enstone", "renault": "enstone", "alpine": "enstone",
    "sauber": "hinwil", "alfa": "hinwil", "audi": "hinwil",
    "marussia": "banbury", "manor": "banbury",
}


def team_lineage(constructor_id: str) -> str:
    return LINEAGE.get(constructor_id, constructor_id)


# --- qualifying pace -------------------------------------------------------------------------


def add_quali_pace(quali: pd.DataFrame) -> pd.DataFrame:
    """Best lap of Q1/Q2/Q3 per driver and its gap to the session's fastest, in %.

    Derived from times, because the published `position` has known inconsistencies (DATA_MAP
    gap #5). Times above 107% of the fastest (rain, mistakes) are kept but capped at 107%.
    """
    q = quali.copy()
    q["best_q_s"] = q[["q1_s", "q2_s", "q3_s"]].min(axis=1)
    fastest = q.groupby(["season", "round"])["best_q_s"].transform("min")
    q["quali_gap_pct"] = ((q["best_q_s"] / fastest - 1) * 100).clip(upper=7.0)
    q["reached_q3"] = q["q3_s"].notna()
    return q
