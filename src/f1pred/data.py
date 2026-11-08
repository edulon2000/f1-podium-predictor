"""Load the processed Parquet tables (Jolpica + OpenF1) into a dict."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

REQUIRED = ["races", "results", "qualifying", "driver_standings", "constructor_standings",
            "drivers", "constructors"]


def load_tables(data_dir: Path = Path("data")) -> dict[str, pd.DataFrame]:
    proc = Path(data_dir) / "processed"
    tables = {p.stem: pd.read_parquet(p) for p in proc.glob("*.parquet")}
    missing = [n for n in REQUIRED if n not in tables]
    if missing:
        raise FileNotFoundError(f"missing tables {missing} in {proc} — run f1pred-ingest first")
    return tables
