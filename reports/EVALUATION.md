# Evaluation

Walk-forward: every race is predicted by a model trained only on earlier races.
Configs were chosen on 2023–2024 (log-loss of the winner), then evaluated once on the 2025–26 holdout.

- `winner_acc`: the favourite won. `winner_top3`: the winner was among our 3 most likely. `podium_hit`: share of the podium in our predicted top 3. `logloss_win`: −log P(actual winner), lower is better.
- Feature sets: `base` = Phase 2; `plus` = + weather forecast, rain/street records, racecraft, Elo ratings.

## Before qualifying (T1)

Chosen: `{"kind": "logreg", "feature_set": "plus", "params": {"C": 0.03}, "same_era_weight": 1.0}`

### holdout 2025–26

| role      | model                  | feature_set   |   same_era_weight |   winner_acc |   winner_top3 |   podium_hit |   logloss_win |   brier_win |   logloss_podium |   races |
|:----------|:-----------------------|:--------------|------------------:|-------------:|--------------:|-------------:|--------------:|------------:|-----------------:|--------:|
| chosen    | logreg                 | plus          |             1.000 |        0.250 |         0.773 |        0.614 |         1.763 |       0.838 |            0.234 |  44.000 |
| best base | logreg                 | base          |             1.000 |        0.273 |         0.773 |        0.614 |         1.768 |       0.836 |            0.233 |  44.000 |
| baseline  | B2 leader wins         | nan           |           nan     |        0.273 |         0.318 |        0.523 |         5.024 |       1.454 |            0.942 |  44.000 |
| baseline  | B2p P(win | standings) | nan           |           nan     |        0.273 |         0.750 |        0.576 |         1.891 |       0.830 |            0.261 |  44.000 |

### 2026 only

| role      | model                  | feature_set   |   same_era_weight |   winner_acc |   winner_top3 |   podium_hit |   logloss_win |   brier_win |   logloss_podium |   races |
|:----------|:-----------------------|:--------------|------------------:|-------------:|--------------:|-------------:|--------------:|------------:|-----------------:|--------:|
| chosen    | logreg                 | plus          |             1.000 |        0.300 |         0.700 |        0.567 |         1.909 |       0.864 |            0.240 |  20.000 |
| best base | logreg                 | base          |             1.000 |        0.300 |         0.700 |        0.567 |         1.882 |       0.858 |            0.235 |  20.000 |
| baseline  | B2 leader wins         | nan           |           nan     |        0.350 |         0.450 |        0.433 |         4.490 |       1.300 |            1.068 |  20.000 |
| baseline  | B2p P(win | standings) | nan           |           nan     |        0.350 |         0.600 |        0.467 |         1.965 |       0.827 |            0.267 |  20.000 |

<details><summary>Tuning grid (2023–24)</summary>

| kind                   | feature_set   | params                                                                                  |   same_era_weight |   winner_acc |   winner_top3 |   podium_hit |   logloss_win |   brier_win |   logloss_podium |   races |
|:-----------------------|:--------------|:----------------------------------------------------------------------------------------|------------------:|-------------:|--------------:|-------------:|--------------:|------------:|-----------------:|--------:|
| logreg                 | plus          | {'C': 0.03}                                                                             |             1.000 |        0.587 |         0.761 |        0.522 |         1.285 |       0.540 |            0.281 |  46.000 |
| logreg                 | base          | {'C': 0.03}                                                                             |             1.000 |        0.587 |         0.739 |        0.507 |         1.296 |       0.538 |            0.281 |  46.000 |
| logreg                 | plus          | {'C': 0.03}                                                                             |             3.000 |        0.609 |         0.739 |        0.522 |         1.301 |       0.542 |            0.289 |  46.000 |
| logreg                 | base          | {'C': 0.03}                                                                             |             3.000 |        0.609 |         0.717 |        0.514 |         1.308 |       0.539 |            0.289 |  46.000 |
| lgbm                   | plus          | {'n_estimators': 200, 'num_leaves': 7, 'min_child_samples': 60}                         |             3.000 |        0.522 |         0.761 |        0.464 |         1.361 |       0.580 |            0.292 |  46.000 |
| lgbm                   | base          | {'n_estimators': 200, 'num_leaves': 7, 'min_child_samples': 60}                         |             3.000 |        0.565 |         0.761 |        0.464 |         1.372 |       0.584 |            0.294 |  46.000 |
| rank                   | base          | {'n_estimators': 200, 'num_leaves': 7, 'min_child_samples': 40}                         |             1.000 |        0.609 |         0.761 |        0.493 |         1.381 |       0.580 |            0.345 |  46.000 |
| lgbm                   | base          | {'n_estimators': 200, 'num_leaves': 7, 'min_child_samples': 60}                         |             1.000 |        0.565 |         0.739 |        0.493 |         1.383 |       0.581 |            0.286 |  46.000 |
| rank                   | base          | {'n_estimators': 200, 'num_leaves': 7, 'min_child_samples': 40}                         |             3.000 |        0.543 |         0.783 |        0.464 |         1.385 |       0.586 |            0.349 |  46.000 |
| lgbm                   | plus          | {'n_estimators': 200, 'num_leaves': 7, 'min_child_samples': 60}                         |             1.000 |        0.609 |         0.761 |        0.485 |         1.393 |       0.586 |            0.281 |  46.000 |
| rank                   | plus          | {'n_estimators': 200, 'num_leaves': 7, 'min_child_samples': 40}                         |             3.000 |        0.565 |         0.783 |        0.478 |         1.408 |       0.595 |            0.354 |  46.000 |
| rank                   | plus          | {'n_estimators': 200, 'num_leaves': 7, 'min_child_samples': 40}                         |             1.000 |        0.565 |         0.761 |        0.514 |         1.459 |       0.610 |            0.355 |  46.000 |
| B2p P(win | standings) | nan           | nan                                                                                     |           nan     |        0.609 |         0.783 |        0.551 |         1.565 |       0.664 |            0.294 |  46.000 |
| rank                   | base          | {'n_estimators': 400, 'num_leaves': 15, 'min_child_samples': 30, 'learning_rate': 0.02} |             3.000 |        0.587 |         0.804 |        0.485 |         1.699 |       0.627 |            0.504 |  46.000 |
| rank                   | plus          | {'n_estimators': 400, 'num_leaves': 15, 'min_child_samples': 30, 'learning_rate': 0.02} |             1.000 |        0.609 |         0.804 |        0.514 |         1.774 |       0.649 |            0.508 |  46.000 |
| rank                   | base          | {'n_estimators': 400, 'num_leaves': 15, 'min_child_samples': 30, 'learning_rate': 0.02} |             1.000 |        0.587 |         0.739 |        0.493 |         1.780 |       0.634 |            0.506 |  46.000 |
| rank                   | plus          | {'n_estimators': 400, 'num_leaves': 15, 'min_child_samples': 30, 'learning_rate': 0.02} |             3.000 |        0.565 |         0.804 |        0.478 |         1.824 |       0.704 |            0.490 |  46.000 |
| B2 leader wins         | nan           | nan                                                                                     |           nan     |        0.565 |         0.565 |        0.493 |         3.003 |       0.870 |            1.054 |  46.000 |

</details>

## After qualifying (T2)

Chosen: `{"kind": "rank", "feature_set": "plus", "params": {"n_estimators": 200, "num_leaves": 7, "min_child_samples": 40}, "same_era_weight": 1.0}`

### holdout 2025–26

| role      | model             | feature_set   |   same_era_weight |   winner_acc |   winner_top3 |   podium_hit |   logloss_win |   brier_win |   logloss_podium |   races |
|:----------|:------------------|:--------------|------------------:|-------------:|--------------:|-------------:|--------------:|------------:|-----------------:|--------:|
| chosen    | rank              | plus          |             1.000 |        0.614 |         0.909 |        0.682 |         0.976 |       0.511 |            0.216 |  44.000 |
| best base | lgbm              | base          |             3.000 |        0.614 |         0.932 |        0.705 |         1.055 |       0.549 |            0.195 |  44.000 |
| baseline  | B1 pole wins      | nan           |           nan     |        0.682 |         0.750 |        0.682 |         2.198 |       0.636 |            0.627 |  44.000 |
| baseline  | B1p P(win | grid) | nan           |           nan     |        0.682 |         0.932 |        0.682 |         1.176 |       0.526 |            0.209 |  44.000 |

### 2026 only

| role      | model             | feature_set   |   same_era_weight |   winner_acc |   winner_top3 |   podium_hit |   logloss_win |   brier_win |   logloss_podium |   races |
|:----------|:------------------|:--------------|------------------:|-------------:|--------------:|-------------:|--------------:|------------:|-----------------:|--------:|
| chosen    | rank              | plus          |             1.000 |        0.650 |         0.850 |        0.650 |         1.036 |       0.500 |            0.220 |  20.000 |
| best base | lgbm              | base          |             3.000 |        0.700 |         0.900 |        0.667 |         1.069 |       0.507 |            0.190 |  20.000 |
| baseline  | B1 pole wins      | nan           |           nan     |        0.700 |         0.850 |        0.600 |         2.072 |       0.600 |            0.754 |  20.000 |
| baseline  | B1p P(win | grid) | nan           |           nan     |        0.700 |         0.900 |        0.600 |         1.280 |       0.510 |            0.215 |  20.000 |

<details><summary>Tuning grid (2023–24)</summary>

| kind              | feature_set   | params                                                                                  |   same_era_weight |   winner_acc |   winner_top3 |   podium_hit |   logloss_win |   brier_win |   logloss_podium |   races |
|:------------------|:--------------|:----------------------------------------------------------------------------------------|------------------:|-------------:|--------------:|-------------:|--------------:|------------:|-----------------:|--------:|
| rank              | plus          | {'n_estimators': 200, 'num_leaves': 7, 'min_child_samples': 40}                         |             1.000 |        0.696 |         0.957 |        0.652 |         1.042 |       0.470 |            0.263 |  46.000 |
| rank              | plus          | {'n_estimators': 200, 'num_leaves': 7, 'min_child_samples': 40}                         |             3.000 |        0.696 |         0.913 |        0.638 |         1.065 |       0.474 |            0.257 |  46.000 |
| lgbm              | base          | {'n_estimators': 200, 'num_leaves': 7, 'min_child_samples': 60}                         |             3.000 |        0.652 |         0.913 |        0.667 |         1.071 |       0.469 |            0.234 |  46.000 |
| rank              | base          | {'n_estimators': 200, 'num_leaves': 7, 'min_child_samples': 40}                         |             3.000 |        0.717 |         0.913 |        0.645 |         1.086 |       0.479 |            0.258 |  46.000 |
| lgbm              | base          | {'n_estimators': 200, 'num_leaves': 7, 'min_child_samples': 60}                         |             1.000 |        0.652 |         0.848 |        0.638 |         1.090 |       0.492 |            0.227 |  46.000 |
| lgbm              | plus          | {'n_estimators': 200, 'num_leaves': 7, 'min_child_samples': 60}                         |             3.000 |        0.674 |         0.913 |        0.630 |         1.097 |       0.491 |            0.235 |  46.000 |
| logreg            | plus          | {'C': 0.03}                                                                             |             1.000 |        0.674 |         0.870 |        0.594 |         1.098 |       0.461 |            0.242 |  46.000 |
| lgbm              | plus          | {'n_estimators': 200, 'num_leaves': 7, 'min_child_samples': 60}                         |             1.000 |        0.630 |         0.870 |        0.652 |         1.099 |       0.508 |            0.225 |  46.000 |
| logreg            | base          | {'C': 0.03}                                                                             |             1.000 |        0.717 |         0.848 |        0.601 |         1.101 |       0.454 |            0.242 |  46.000 |
| rank              | base          | {'n_estimators': 200, 'num_leaves': 7, 'min_child_samples': 40}                         |             1.000 |        0.674 |         0.891 |        0.645 |         1.119 |       0.502 |            0.267 |  46.000 |
| logreg            | plus          | {'C': 0.03}                                                                             |             3.000 |        0.696 |         0.826 |        0.594 |         1.137 |       0.460 |            0.250 |  46.000 |
| logreg            | base          | {'C': 0.03}                                                                             |             3.000 |        0.717 |         0.826 |        0.594 |         1.143 |       0.454 |            0.247 |  46.000 |
| rank              | base          | {'n_estimators': 400, 'num_leaves': 15, 'min_child_samples': 30, 'learning_rate': 0.02} |             3.000 |        0.674 |         0.891 |        0.623 |         1.452 |       0.547 |            0.368 |  46.000 |
| rank              | plus          | {'n_estimators': 400, 'num_leaves': 15, 'min_child_samples': 30, 'learning_rate': 0.02} |             3.000 |        0.674 |         0.913 |        0.638 |         1.494 |       0.577 |            0.380 |  46.000 |
| B1p P(win | grid) | nan           | nan                                                                                     |           nan     |        0.543 |         0.848 |        0.652 |         1.558 |       0.651 |            0.251 |  46.000 |
| rank              | base          | {'n_estimators': 400, 'num_leaves': 15, 'min_child_samples': 30, 'learning_rate': 0.02} |             1.000 |        0.652 |         0.870 |        0.609 |         1.577 |       0.574 |            0.408 |  46.000 |
| rank              | plus          | {'n_estimators': 400, 'num_leaves': 15, 'min_child_samples': 30, 'learning_rate': 0.02} |             1.000 |        0.674 |         0.935 |        0.659 |         1.583 |       0.573 |            0.409 |  46.000 |
| B1 pole wins      | nan           | nan                                                                                     |           nan     |        0.543 |         0.543 |        0.652 |         3.154 |       0.913 |            0.723 |  46.000 |

</details>

## Reading the results (written by hand, Phase 3 — 2026-11-08)

Targets agreed before Phase 3, checked on the 2025–26 test races (44 races, never used for tuning):

| Target | Result | Met? |
|---|---|---|
| Winner among our top 3, **before** qualifying ≥ 90% | 77.3% (standings baseline 75.0%) | ❌ |
| Winner among our top 3, after qualifying ≥ 90% | 90.9% (grid baseline 93.2%) | ✅ but not better than the grid |
| Exact winner after qualifying ≥ 70% (beat pole) | 61.4% (pole 68.2%) | ❌ |
| Confidence score (log-loss) after qualifying < 1.00 | **0.976** (grid baseline 1.176, Phase 2 model 1.055) | ✅ |
| Podium places guessed > 75% | 68.2% | ❌ |

What moved the numbers:

- **The biggest gain was a data fix**, not a new feature: Jolpica sometimes publishes
  qualifying positions without lap times; falling back to OpenF1's laps lifted the Phase 2
  model from 56.8% to 61.4% exact winners and from 1.06 to 1.055 log-loss on the same test.
- The **ranking model** with the new condition features gives the best-calibrated
  probabilities so far (0.976), i.e. it puts more chance on the eventual winner on average,
  but it still names the exact winner less often than “the pole-sitter wins”.
- **Weather, rain/street records and Elo ratings barely helped** on these test races: before
  qualifying the new features change log-loss from 1.768 to 1.763 and leave the top-3 rate at
  77.3%. 2025–26 had few races where rain changed the result, and the ratings largely repeat
  what standings and recent form already say.
- Before qualifying the problem is genuinely hard: about a third of the time the winner is
  someone the form guide does not single out, and nothing measured before qualifying sees it.

Next ideas (Phase 4): use practice long-run pace more aggressively (it is the only
same-weekend signal before qualifying), team upgrade/package timing, a decision rule that backs
the pole-sitter unless the model is clearly more confident in someone else (tuned on 2023–24),
and a comparison against bookmaker odds as the real benchmark.
