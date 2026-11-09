# Evaluation

Walk-forward: every race is predicted by a model trained only on earlier races.
Configs were chosen on 2023–2024 (log-loss of the winner), then evaluated once on the 2025–26 holdout.

Metrics: `winner_acc` = top pick wins; `podium_hit` = share of the actual podium in the predicted top 3; `logloss_win` = −log P(actual winner), lower is better; `brier_win` = squared error of win probabilities per race.

## T1 — before qualifying

Chosen: `{"kind": "logreg", "params": {"C": 0.03}, "same_era_weight": 1.0}`

### holdout 2025–26

| model                  |   same_era_weight |   winner_acc |   podium_hit |   logloss_win |   brier_win |   logloss_podium |   races |
|:-----------------------|------------------:|-------------:|-------------:|--------------:|------------:|-----------------:|--------:|
| logreg                 |             1.000 |        0.273 |        0.614 |         1.769 |       0.837 |            0.233 |  44.000 |
| lgbm                   |             3.000 |        0.318 |        0.614 |         1.775 |       0.824 |            0.230 |  44.000 |
| B2 leader wins         |           nan     |        0.273 |        0.523 |         5.024 |       1.454 |            0.942 |  44.000 |
| B2p P(win | standings) |           nan     |        0.273 |        0.576 |         1.891 |       0.830 |            0.261 |  44.000 |

### 2026 only

| model                  |   same_era_weight |   winner_acc |   podium_hit |   logloss_win |   brier_win |   logloss_podium |   races |
|:-----------------------|------------------:|-------------:|-------------:|--------------:|------------:|-----------------:|--------:|
| logreg                 |             1.000 |        0.300 |        0.567 |         1.882 |       0.858 |            0.235 |  20.000 |
| lgbm                   |             3.000 |        0.300 |        0.583 |         1.887 |       0.847 |            0.225 |  20.000 |
| B2 leader wins         |           nan     |        0.350 |        0.433 |         4.490 |       1.300 |            1.068 |  20.000 |
| B2p P(win | standings) |           nan     |        0.350 |        0.467 |         1.965 |       0.827 |            0.267 |  20.000 |

<details><summary>Tuning grid (2023–24)</summary>

| kind                   | params                                                                                  |   same_era_weight |   winner_acc |   podium_hit |   logloss_win |   brier_win |   logloss_podium |   races |
|:-----------------------|:----------------------------------------------------------------------------------------|------------------:|-------------:|-------------:|--------------:|------------:|-----------------:|--------:|
| logreg                 | {'C': 0.03}                                                                             |             1.000 |        0.587 |        0.507 |         1.296 |       0.538 |            0.281 |  46.000 |
| logreg                 | {'C': 0.03}                                                                             |             3.000 |        0.609 |        0.514 |         1.308 |       0.539 |            0.289 |  46.000 |
| logreg                 | {'C': 0.3}                                                                              |             1.000 |        0.587 |        0.507 |         1.309 |       0.545 |            0.297 |  46.000 |
| logreg                 | {'C': 0.03}                                                                             |             8.000 |        0.609 |        0.514 |         1.332 |       0.545 |            0.297 |  46.000 |
| logreg                 | {'C': 0.3}                                                                              |             3.000 |        0.609 |        0.514 |         1.342 |       0.556 |            0.301 |  46.000 |
| lgbm                   | {'n_estimators': 200, 'num_leaves': 7, 'min_child_samples': 60}                         |             3.000 |        0.565 |        0.464 |         1.372 |       0.584 |            0.294 |  46.000 |
| lgbm                   | {'n_estimators': 200, 'num_leaves': 7, 'min_child_samples': 60}                         |             1.000 |        0.565 |        0.493 |         1.383 |       0.581 |            0.286 |  46.000 |
| lgbm                   | {'n_estimators': 200, 'num_leaves': 7, 'min_child_samples': 60}                         |             8.000 |        0.522 |        0.471 |         1.384 |       0.590 |            0.302 |  46.000 |
| logreg                 | {'C': 0.3}                                                                              |             8.000 |        0.587 |        0.514 |         1.384 |       0.567 |            0.307 |  46.000 |
| lgbm                   | {'n_estimators': 400, 'num_leaves': 15, 'min_child_samples': 30, 'learning_rate': 0.02} |             1.000 |        0.609 |        0.485 |         1.405 |       0.568 |            0.296 |  46.000 |
| lgbm                   | {'n_estimators': 400, 'num_leaves': 15, 'min_child_samples': 30, 'learning_rate': 0.02} |             3.000 |        0.565 |        0.478 |         1.446 |       0.598 |            0.326 |  46.000 |
| lgbm                   | {'n_estimators': 400, 'num_leaves': 15, 'min_child_samples': 30, 'learning_rate': 0.02} |             8.000 |        0.543 |        0.464 |         1.536 |       0.620 |            0.343 |  46.000 |
| B2p P(win | standings) | nan                                                                                     |           nan     |        0.609 |        0.551 |         1.565 |       0.664 |            0.294 |  46.000 |
| B2 leader wins         | nan                                                                                     |           nan     |        0.565 |        0.493 |         3.003 |       0.870 |            1.054 |  46.000 |

</details>

## T2 — after qualifying

Chosen: `{"kind": "lgbm", "params": {"n_estimators": 200, "num_leaves": 7, "min_child_samples": 60}, "same_era_weight": 3.0}`

### holdout 2025–26

| model             |   same_era_weight |   winner_acc |   podium_hit |   logloss_win |   brier_win |   logloss_podium |   races |
|:------------------|------------------:|-------------:|-------------:|--------------:|------------:|-----------------:|--------:|
| logreg            |             1.000 |        0.545 |        0.697 |         1.140 |       0.579 |            0.202 |  44.000 |
| lgbm              |             3.000 |        0.568 |        0.712 |         1.059 |       0.544 |            0.194 |  44.000 |
| B1 pole wins      |           nan     |        0.682 |        0.682 |         2.198 |       0.636 |            0.627 |  44.000 |
| B1p P(win | grid) |           nan     |        0.682 |        0.682 |         1.176 |       0.526 |            0.209 |  44.000 |

### 2026 only

| model             |   same_era_weight |   winner_acc |   podium_hit |   logloss_win |   brier_win |   logloss_podium |   races |
|:------------------|------------------:|-------------:|-------------:|--------------:|------------:|-----------------:|--------:|
| logreg            |             1.000 |        0.600 |        0.617 |         1.097 |       0.539 |            0.199 |  20.000 |
| lgbm              |             3.000 |        0.650 |        0.667 |         1.079 |       0.512 |            0.191 |  20.000 |
| B1 pole wins      |           nan     |        0.700 |        0.600 |         2.072 |       0.600 |            0.754 |  20.000 |
| B1p P(win | grid) |           nan     |        0.700 |        0.600 |         1.280 |       0.510 |            0.215 |  20.000 |

<details><summary>Tuning grid (2023–24)</summary>

| kind              | params                                                                                  |   same_era_weight |   winner_acc |   podium_hit |   logloss_win |   brier_win |   logloss_podium |   races |
|:------------------|:----------------------------------------------------------------------------------------|------------------:|-------------:|-------------:|--------------:|------------:|-----------------:|--------:|
| lgbm              | {'n_estimators': 200, 'num_leaves': 7, 'min_child_samples': 60}                         |             3.000 |        0.674 |        0.659 |         1.066 |       0.467 |            0.233 |  46.000 |
| lgbm              | {'n_estimators': 200, 'num_leaves': 7, 'min_child_samples': 60}                         |             1.000 |        0.652 |        0.638 |         1.090 |       0.492 |            0.227 |  46.000 |
| logreg            | {'C': 0.03}                                                                             |             1.000 |        0.717 |        0.601 |         1.101 |       0.454 |            0.242 |  46.000 |
| lgbm              | {'n_estimators': 400, 'num_leaves': 15, 'min_child_samples': 30, 'learning_rate': 0.02} |             1.000 |        0.652 |        0.645 |         1.131 |       0.503 |            0.242 |  46.000 |
| lgbm              | {'n_estimators': 200, 'num_leaves': 7, 'min_child_samples': 60}                         |             8.000 |        0.674 |        0.638 |         1.135 |       0.488 |            0.235 |  46.000 |
| logreg            | {'C': 0.3}                                                                              |             1.000 |        0.696 |        0.587 |         1.140 |       0.451 |            0.258 |  46.000 |
| logreg            | {'C': 0.03}                                                                             |             3.000 |        0.717 |        0.594 |         1.143 |       0.454 |            0.247 |  46.000 |
| logreg            | {'C': 0.3}                                                                              |             3.000 |        0.696 |        0.587 |         1.150 |       0.455 |            0.258 |  46.000 |
| logreg            | {'C': 0.03}                                                                             |             8.000 |        0.717 |        0.601 |         1.169 |       0.462 |            0.253 |  46.000 |
| lgbm              | {'n_estimators': 400, 'num_leaves': 15, 'min_child_samples': 30, 'learning_rate': 0.02} |             3.000 |        0.652 |        0.630 |         1.169 |       0.510 |            0.248 |  46.000 |
| logreg            | {'C': 0.3}                                                                              |             8.000 |        0.696 |        0.609 |         1.174 |       0.463 |            0.264 |  46.000 |
| lgbm              | {'n_estimators': 400, 'num_leaves': 15, 'min_child_samples': 30, 'learning_rate': 0.02} |             8.000 |        0.652 |        0.616 |         1.227 |       0.511 |            0.251 |  46.000 |
| B1p P(win | grid) | nan                                                                                     |           nan     |        0.543 |        0.652 |         1.558 |       0.651 |            0.251 |  46.000 |
| B1 pole wins      | nan                                                                                     |           nan     |        0.543 |        0.652 |         3.154 |       0.913 |            0.723 |  46.000 |

</details>

## Reading the results (written by hand, 2026-11-08)

- **After qualifying**, LightGBM beats the calibrated grid baseline on log-loss (1.06 vs 1.18 on
  2025–26) and on podium hit rate (71% vs 68%), but **names the winner less often than "the
  pole-sitter wins"** (57% vs 68%). It spreads probability over the front row instead of always
  backing P1, which pays off in log-loss and podiums but loses on top-1 accuracy in seasons where
  pole converts this often (2025: 67%, 2026: 70%).
- **Before qualifying**, both the model and the standings baseline name the winner ~27–30% of
  the time; the model is slightly better on log-loss and clearly better on podiums.
- **Era weight**: weighting rows from the current regulation era ×3 helped T2 on 2023–24 and is
  used for 2026; for T1 it did not help (×1 chosen).

### Next ideas (Phase 4)

1. A ranking objective (LambdaRank) or a conditional-logit (softmax per race) instead of
   independent binary classifiers + normalisation.
2. Pole conversion features by team/era (how often this car converts P1 this season).
3. Choose the T2 model on a mix of log-loss and top-1 accuracy, or report a hybrid
   ("pole-sitter unless the model is >X% confident in someone else").
4. Compare against bookmaker odds — the real benchmark for any betting-style claim.
