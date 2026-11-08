"""Generate notebooks/01_sanity.ipynb (kept as code so the notebook diff stays reviewable).

    uv run python scripts/make_sanity_notebook.py
    uv run jupyter nbconvert --to notebook --execute --inplace notebooks/01_sanity.ipynb
"""

from pathlib import Path

import nbformat as nbf

cells = [
    nbf.v4.new_markdown_cell(
        "# 01 — Sanity checks on the ingested data\n\n"
        "Quick checks on `data/processed/*.parquet` (produced by `f1pred-ingest`):\n"
        "coverage, pole → win conversion by regulation era, and 2026 winners so far.\n\n"
        "Two definitions of *pole*: **grid = 1** (actual starting position, after penalties) and "
        "**qualifying P1**. Races with an unpublished grid are excluded from the grid-based rate."
    ),
    nbf.v4.new_code_cell(
        "import json\n"
        "from pathlib import Path\n\n"
        "import matplotlib.pyplot as plt\n"
        "import pandas as pd\n\n"
        "DATA = Path('..') / 'data' / 'processed'\n"
        "t = {p.stem: pd.read_parquet(p) for p in DATA.glob('*.parquet')}\n"
        "report = json.loads((DATA / 'ingest_report.json').read_text(encoding='utf-8'))\n"
        "print('generated_at:', report['generated_at'], '| latest round:', report['latest_round'])\n"
        "pd.Series(report['row_counts'], name='rows').to_frame()"
    ),
    nbf.v4.new_markdown_cell("## Coverage per season"),
    nbf.v4.new_code_cell(
        "races, res, q = t['races'], t['results'], t['qualifying']\n"
        "cov = pd.DataFrame({\n"
        "    'scheduled': races.groupby('season').size(),\n"
        "    'with_results': res.groupby('season')['round'].nunique(),\n"
        "    'with_quali': q.groupby('season')['round'].nunique(),\n"
        "    'sprints': t['sprint_results'].groupby('season')['round'].nunique()\n"
        "    if not t['sprint_results'].empty else 0,\n"
        "    'standings_rounds': t['driver_standings'].groupby('season')['round'].nunique(),\n"
        "}).fillna(0).astype(int)\n"
        "cov"
    ),
    nbf.v4.new_markdown_cell("## Pole → win conversion by era"),
    nbf.v4.new_code_cell(
        "def era(season):\n"
        "    return '2014–2021' if season <= 2021 else ('2022–2025' if season <= 2025 else '2026')\n\n"
        "winners = res[res['position'] == 1][['season', 'round', 'driver_id', 'constructor_id', 'grid']]\n"
        "qpole = q[q['position'] == 1][['season', 'round', 'driver_id']].rename(\n"
        "    columns={'driver_id': 'quali_pole'})\n"
        "w = winners.merge(qpole, on=['season', 'round'], how='left')\n"
        "w['era'] = w['season'].map(era)\n"
        "w['won_from_grid1'] = (w['grid'] == 1).where(w['grid'].notna())\n"
        "w['won_from_quali_pole'] = (w['driver_id'] == w['quali_pole']).where(w['quali_pole'].notna())\n\n"
        "summary = w.groupby('era').agg(\n"
        "    races=('round', 'size'),\n"
        "    races_with_grid=('won_from_grid1', 'count'),\n"
        "    pole_win_pct_grid=('won_from_grid1', 'mean'),\n"
        "    pole_win_pct_quali=('won_from_quali_pole', 'mean'),\n"
        ")\n"
        "summary[['pole_win_pct_grid', 'pole_win_pct_quali']] *= 100\n"
        "summary.round(1)"
    ),
    nbf.v4.new_code_cell(
        "per_season = w.groupby('season')['won_from_grid1'].mean() * 100\n"
        "colors = ['#7a8b99' if s <= 2021 else '#3b7dd8' if s <= 2025 else '#e8590c'\n"
        "          for s in per_season.index]\n"
        "ax = per_season.plot.bar(color=colors, figsize=(10, 3.5))\n"
        "ax.set_ylabel('% of races won from grid P1')\n"
        "ax.set_xlabel('')\n"
        "ax.set_title('Pole-to-win conversion per season (grey 2014–21, blue 2022–25, orange 2026)')\n"
        "ax.set_ylim(0, 100)\n"
        "plt.tight_layout()"
    ),
    nbf.v4.new_markdown_cell("## 2026 winners so far"),
    nbf.v4.new_code_cell(
        "d = t['drivers'].set_index('driver_id')\n"
        "c = t['constructors'].set_index('constructor_id')\n"
        "w26 = (w[w['season'] == 2026]\n"
        "       .merge(races[['season', 'round', 'race_name', 'race_date']], on=['season', 'round'])\n"
        "       .assign(winner=lambda x: x['driver_id'].map(d['family_name']),\n"
        "               team=lambda x: x['constructor_id'].map(c['name']))\n"
        "       [['round', 'race_name', 'race_date', 'winner', 'team', 'grid', 'quali_pole']])\n"
        "w26"
    ),
    nbf.v4.new_code_cell(
        "w26.groupby(['winner', 'team']).size().rename('wins').sort_values(ascending=False)"
        ".reset_index()"
    ),
    nbf.v4.new_code_cell(
        "w26['team'].value_counts().rename('wins').reset_index()"
    ),
    nbf.v4.new_markdown_cell("## Gaps reported by the ingestion"),
    nbf.v4.new_code_cell(
        "gaps = pd.DataFrame(report['gaps'])\n"
        "gaps if not gaps.empty else 'no gaps reported'"
    ),
]

nb = nbf.v4.new_notebook(cells=cells, metadata={"kernelspec": {
    "name": "python3", "display_name": "Python 3", "language": "python"}})
out = Path("notebooks/01_sanity.ipynb")
nbf.write(nb, out)
print("wrote", out)
