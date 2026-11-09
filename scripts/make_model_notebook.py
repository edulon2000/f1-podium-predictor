"""Generate notebooks/02_baselines_and_model.ipynb.

    uv run python scripts/make_model_notebook.py
    uv run jupyter nbconvert --to notebook --execute --inplace notebooks/02_baselines_and_model.ipynb
"""

from pathlib import Path

import nbformat as nbf

cells = [
    nbf.v4.new_markdown_cell(
        "# 02 — Baselines vs model\n\n"
        "Results of `scripts/run_evaluation.py`: configs chosen on 2023–24 by walk-forward "
        "log-loss, then evaluated once on the 2025–26 holdout (and on 2026 alone, the new "
        "regulation era). Every prediction comes from a model trained only on earlier races."
    ),
    nbf.v4.new_code_cell(
        "import json, os\n"
        "from pathlib import Path\n\n"
        "import matplotlib.pyplot as plt\n"
        "import numpy as np\n"
        "import pandas as pd\n\n"
        "os.chdir(Path('..'))  # project root, so f1pred finds data/ and configs/\n"
        "from f1pred.data import load_tables\n"
        "from f1pred.evaluate import races_between, walk_forward, metrics\n"
        "from f1pred.features import T1_FEATURES, T2_FEATURES, build_features\n"
        "from f1pred.predict import load_spec\n\n"
        "rep = json.loads(Path('reports/evaluation.json').read_text(encoding='utf-8'))\n"
        "hold = pd.DataFrame(rep['holdout'])\n"
        "rep['chosen']"
    ),
    nbf.v4.new_markdown_cell("## Holdout results"),
    nbf.v4.new_code_cell(
        "cols = ['stage', 'window', 'model', 'winner_acc', 'podium_hit', 'logloss_win', "
        "'brier_win', 'races']\n"
        "hold[cols].round(3)"
    ),
    nbf.v4.new_code_cell(
        "fig, axes = plt.subplots(1, 2, figsize=(12, 4))\n"
        "for ax, metric, title in [(axes[0], 'winner_acc', 'Winner accuracy (higher = better)'),\n"
        "                          (axes[1], 'logloss_win', 'Log-loss of the winner (lower = better)')]:\n"
        "    sub = hold[hold.window == 'holdout 2025–26'].copy()\n"
        "    sub['label'] = sub['stage'].str.upper() + ' · ' + sub['model']\n"
        "    sub = sub[~(sub['model'].str.startswith('B') & ~sub['model'].str.contains('p '))\n"
        "              | (metric == 'winner_acc')]\n"
        "    colors = ['#9aa5b1' if m.startswith('B') else '#3b7dd8' for m in sub['model']]\n"
        "    ax.barh(sub['label'], sub[metric], color=colors)\n"
        "    ax.set_title(title)\n"
        "    ax.invert_yaxis()\n"
        "plt.suptitle('Holdout 2025–26 (grey = baselines, blue = models)')\n"
        "plt.tight_layout()"
    ),
    nbf.v4.new_markdown_cell(
        "Deterministic baselines (0/1 predictions) have a huge log-loss by construction, so the "
        "log-loss panel compares the models against the *calibrated* baselines "
        "(`B1p`, `B2p`: empirical P(win | grid) and P(win | standings))."
    ),
    nbf.v4.new_markdown_cell("## Calibration of P(win) — chosen T2 model, 2025–26"),
    nbf.v4.new_code_cell(
        "t = load_tables()\n"
        "frame = build_features(t)\n"
        "spec2 = load_spec('t2', Path('configs'))\n"
        "preds = walk_forward(frame, spec2.as_predictor(), races_between(frame, 2025, 2026))\n"
        "bins = [0, 0.05, 0.15, 0.3, 0.5, 0.7, 1.0]\n"
        "preds['bin'] = pd.cut(preds['p_win'], bins)\n"
        "cal = preds.groupby('bin', observed=True).agg(predicted=('p_win', 'mean'),\n"
        "                                              observed=('win', 'mean'), n=('win', 'size'))\n"
        "ax = cal.plot(x='predicted', y='observed', marker='o', legend=False, figsize=(4.5, 4.5))\n"
        "ax.plot([0, 1], [0, 1], ls='--', c='grey')\n"
        "ax.set_xlabel('predicted P(win)'); ax.set_ylabel('observed win rate')\n"
        "cal.round(3)"
    ),
    nbf.v4.new_markdown_cell("## 2026 race by race — chosen T2 model"),
    nbf.v4.new_code_cell(
        "p26 = preds[preds.season == 2026]\n"
        "top = p26.sort_values('p_win').groupby('round').tail(1).set_index('round')\n"
        "act = p26[p26.win == 1].set_index('round')\n"
        "pd.DataFrame({'predicted': top['driver_id'], 'p_top': top['p_win'].round(2),\n"
        "              'actual': act['driver_id'], 'p_actual': act['p_win'].round(2),\n"
        "              'actual_grid': act['grid_f']}).sort_index()"
    ),
    nbf.v4.new_markdown_cell("## What the models rely on"),
    nbf.v4.new_code_cell(
        "def importance(stage):\n"
        "    spec = load_spec(stage, Path('configs'))\n"
        "    train = frame[frame['win'].notna()]\n"
        "    fitted = spec.fit(train, 2026)['win']\n"
        "    if spec.kind in ('lgbm', 'rank'):\n"
        "        imp = pd.Series(fitted.booster_.feature_importance('gain'), index=spec.features)\n"
        "        return (imp / imp.sum()).sort_values(ascending=False).head(12).rename('gain share')\n"
        "    coefs = fitted.named_steps['logisticregression'].coef_[0][:len(spec.features)]\n"
        "    return pd.Series(coefs, index=spec.features).sort_values(key=abs, ascending=False)\\\n"
        "        .head(12).rename('std. coefficient')\n\n"
        "pd.concat({'T1': importance('t1').reset_index(), 'T2': importance('t2').reset_index()},\n"
        "          axis=1)"
    ),
]

nb = nbf.v4.new_notebook(cells=cells, metadata={"kernelspec": {
    "name": "python3", "display_name": "Python 3", "language": "python"}})
out = Path("notebooks/02_baselines_and_model.ipynb")
nbf.write(nb, out)
print("wrote", out)
