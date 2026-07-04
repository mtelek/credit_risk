# Credit Risk Modeling Project

- This repository implements a credit risk modeling pipeline that builds, evaluates and compares a logistic regression scorecard and an XGBoost model using Lending Club historical data. It includes data ingestion, preprocessing, caching, model training, evaluation (ROC/AUC, KS deciles, calibration) and scorecard generation with per-individual scores.

## Quickstart — run the full pipeline

Prerequisites
- Docker & Docker Compose (or the `docker-compose` compatibility shim). The project is containerized so you don't need to install the Python deps locally. See [docker-compose.yml](docker-compose.yml).
- Make (recommended) to use the convenience targets in the `Makefile`.

Run the pipeline (cold run)
- Build and run all services (Postgres + app) and execute the full pipeline (data init, modeling, evaluation, plots, scorecard):

```bash
make start
```

- Alternatively you can start only services without rebuilding with:

```bash
make up
```

Download raw dataset from Kaggle (if needed)

```bash
make download-data
# or
docker compose run --rm --build app python src/download_kaggle.py
```

Stop and cleanup

```bash
make down               # stop containers
make clean              # stop and remove volumes
make clean-data         # additionally remove raw data folder
make clean-cache        # remove cached computation results and keys
make prune              # prune docker system resources
make prune-all          # remove images and orphan containers too
```

Why Docker and the Makefile
- Docker ensures a reproducible environment (Python deps, system libs, identical runtime). The `app` service in [docker-compose.yml](docker-compose.yml) runs `python src/project.py` by default; this orchestrates the full pipeline end-to-end. The `Makefile` provides short aliases that call `docker compose`/`docker-compose` depending on environment, making common actions (build, run, download data, clean) one-liners.

## What the pipeline does (high-level steps)
- Ensure database schema exists and populate `accepted_loans` table from either a CSV dump or by creating a staging table and bulk-loading the raw CSV. (See `src/dataset_init.py`.)
- Run SQL transforms that normalize/clean the staging data and persist a transformed table. The transformed table is dumped to CSV for fast restores.
- Compute a cutoff date to split the dataset into train (first 80% by `issue_d`) and test (remaining 20%).
- Load train/test into pandas, apply dtype optimizations, and save pickled copies in the cache for fast subsequent runs.
- Train a logistic regression model based on Weight-of-Evidence (WOE) transformed features and a scorecard derived from it.
- Train an XGBoost model (hyperparameter search + refit) and compute feature importance.
- Produce evaluation artifacts: ROC plot, KS decile charts, calibration plot, AUC/Gini/KS tables, and CSVs for IV, coefficients, scorecard table and individual scores.

## Data initialization — detailed (what `dataset_init()` does)
- Paths and directories (inside container):
  - Raw files: `/app/data/raw` (mounted from the repo `./data` directory).
  - Cache dir: `/app/data/cache` (pickles for quick reuse).
  - Key dir: `/app/data/key` (small files used as cache version keys).
  - Database dumps: `/app/data/db_dumps` (CSV dump of `accepted_loans`).

- Schema & staging
  - `ensure_schema()` executes `sql/schema_accepted_loans.sql` to create the final normalized schema if needed.
  - If the `accepted_loans` table is empty, the pipeline will look for a pre-made dump `/app/data/db_dumps/accepted_loans.csv` and restore it directly (fast path).
  - Otherwise it creates a `stg_accepted_loans` staging table (all TEXT columns) and bulk loads the raw CSV into that staging table using Postgres `COPY` for performance.
  - The repo contains [sql/transform_accepted_loans.sql](sql/transform_accepted_loans.sql) which performs the SQL transforms to produce the canonical `accepted_loans` table from the staging data. After transform the final table is dumped to `/app/data/db_dumps/accepted_loans.csv` so subsequent runs can restore quickly.

- Cutoff calculation and train/test split
  - `calc_cutoff_data()` selects the issue date at the 80th percentile (by row order) and returns that date as `cutoff_date`.
  - `load_train_and_test_data_in_pd()` queries `accepted_loans` with a fixed feature column list and splits rows by `issue_d <= cutoff` (train) and `> cutoff` (test).
  - A `DTYPE_MAP` is applied to reduce memory (e.g. `category` for string categories, `int8` for small ints).

- Caching and keys (why warm run is fast)
  - After the first full (cold) run the pipeline writes pickled `train_raw.pkl` and `test_raw.pkl` to `/app/data/cache` and writes a small key (`/app/data/key/raw_cache.key`) containing an MD5 derived from the feature list and cutoff date.
  - On subsequent runs (warm runs) if the key matches and `force_recompute` is not enabled, the pipeline loads these pickles instead of re-querying and re-processing the entire SQL stage. This reduces runtime dramatically.
  - Similar cache+key patterns are used for:
    - WOE bins and WOE-transformed train/test (`/app/data/cache/bins_cache.pkl`, `/app/data/cache/train_woe.pkl`, `/app/data/cache/test_woe.pkl` with `/app/data/key/woe_cache.key`).
    - XGBoost fitted model (`/app/data/cache/xgboost_model.pkl` with `/app/data/key/xgboost_model.key`).
    - Scorecard and per-individual scores (`/app/data/cache/scorecard.pkl`, `/app/data/cache/scores.pkl` with `/app/data/key/scorecard.key`).
  - To ignore caches and force recomputation set the environment variable `FORCE_RECOMPUTE=true` (see `src/environment.py`).

- Typical timings (observed on the development machine)
  - Cold run (no caches present): ~500 seconds (this includes CSV load / transforms + model fitting + search). This is dominated by the SQL load/transform and hyperparameter search when run for the first time.
  - Warm run (all caches present): ~30 seconds (loading pickles and re-using artifacts is much faster).

## Creating the training and test datasets — small implementation details
- Feature selection: `load_train_and_test_data_in_pd()` selects an explicit list of features (loan amount, term, rates, grade, income, dti, fico fields, and more). These are listed in the function source so you can add or remove columns safely.
- The split is deterministic and based on `issue_d` determined by `calc_cutoff_data()` (80/20 temporal split). This avoids leakage across train/test.
- The code stores the selected train/test dataframes as pickles in the cache so repeated runs avoid the SQL roundtrip.
- `check_class_balance()` writes `outputs/train_class_balance.csv` and `outputs/test_class_balance.csv` so you can inspect the proportion of defaults vs non-defaults in each split.

## Logistic Regression pipeline and WOE details
- WOE (Weight of Evidence) binning:
  - The project uses `scorecardpy.woebin()` to compute bins and WOE values for each variable. The WOE transform helps convert categorical or binned numeric variables into monotonic numeric predictors that are interpretable for scorecards.
  - `apply_woe()` caches the bins (`bins_cache.pkl`) and WOE-transformed data frames (`train_woe.pkl`, `test_woe.pkl`) and uses `/app/data/key/woe_cache.key` to skip recomputation.

- Information Value (IV) and variable selection:
  - `get_iv_table()` extracts IV per variable and the pipeline writes `outputs/iv_table.csv`.
  - `variable_check()` removes variables with IV below a threshold (default 0.02). This filters out weak predictors.
  - It then computes correlations on the WOE features and removes one feature from each highly-correlated pair (corr threshold default 0.8) using the IV values to decide which to keep (the higher IV wins).

- Model fitting and interpretation:
  - A scikit-learn `LogisticRegression(class_weight='balanced', max_iter=1000)` is trained on the selected WOE features.
  - A `statsmodels.Logit` model is also fit on the same features to produce coefficient p-values and a statistical summary that is saved to `outputs/logit_stats.csv`.
  - Coefficients of the scikit-learn model are saved to `outputs/logreg_coefficients.csv` for inspection and business-sign checks.

- Scorecard creation and per-individual scores:
  - The repository uses `scorecardpy.scorecard()` to produce a scorecard mapping WOE bins + coefficients to integer score points.
  - The scorecard table is saved as `outputs/scorecard_table.csv` and individual scores for the test set are saved to `outputs/individual_scores.csv`.

## Why also train XGBoost? (and how it's used here)
- Motivation
  - Logistic regression + WOE produces an interpretable scorecard useful for regulatory / business contexts where explanations and monotonic behavior are important.
  - XGBoost is a powerful tree-based ensemble that often yields better discrimination (AUC) by capturing nonlinear interactions and complex patterns.

- Implementation notes
  - In this project the XGBoost training function `train_xgboost()` receives the same `x_train`/`x_test` that the logistic regression used (i.e., after variable selection). That said, tree-based methods do not require WOE; they can take raw numeric/categorical encodings directly. Using WOE here is a pragmatic choice to keep feature sets consistent between models, but you could train XGBoost on raw features for potentially different behavior.

- Hyperparameter search & tuning
  - The code runs a `RandomizedSearchCV` (defaults: `n_iter=30`, `cv_folds=3`) using a parameter distribution that includes `n_estimators`, `max_depth`, `learning_rate`, `subsample`, `colsample_bytree`, `min_child_weight` and `gamma`.
  - To keep the search fast it samples up to `search_sample` rows (default 200k or the dataset size) for the hyperparameter search, then refits the best parameters on the full training set.
  - The chosen best parameters are saved to `outputs/xgboost_best_params.csv` and the final fitted model is pickled to `/app/data/cache/xgboost_model.pkl` with a key file `/app/data/key/xgboost_model.key`.

## Evaluation: ROC, AUC, Gini, KS decile, calibration
- ROC & AUC
  - ROC (Receiver Operating Characteristic) plots True Positive Rate vs False Positive Rate across decision thresholds.
  - AUC (Area Under ROC) is the scalar summary of discrimination (higher = better). The project computes AUC with `sklearn.metrics.roc_auc_score` and writes ROC comparisons to `outputs/roc_comparison.png`.
  - Gini is reported as `2*AUC - 1` and saved in the model evaluation tables.

- KS decile chart
  - The KS decile chart bins predicted probabilities into deciles (highest PD = decile 1) and plots cumulative % of bads and goods. KS is the maximum vertical distance between those two curves and is a discrimination measure commonly used in credit scoring.
  - Plots are saved as `outputs/ks_decile_logreg.png` and `outputs/ks_decile_xgboost.png`.

- Calibration plot
  - Calibration plots compare average predicted probability vs observed default rate across quantile bins. A perfectly calibrated model lies on the diagonal `y=x`. The project computes calibration curves (sklearn `calibration_curve`) and outputs `outputs/calibration_plot_.png`.

- What the numbers measure (short)
  - AUC: how well the model ranks positives vs negatives across thresholds (0.5 = random, 1.0 = perfect).
  - Gini: rescaled AUC (Gini = 2*AUC - 1), commonly reported in credit analytics.
  - KS: the maximum separation between cumulative bads and goods across score deciles — higher KS indicates stronger separation.
  - Calibration: whether predicted probabilities correspond to observed frequencies (important if you use raw probabilities for pricing or provisioning).

## Outputs produced by the pipeline
- CSVs in `outputs/` (examples): `iv_table.csv`, `logit_stats.csv`, `logreg_coefficients.csv`, `model_comparison.csv`, `train_class_balance.csv`, `test_class_balance.csv`, `xgboost_best_params.csv`, `scorecard_table.csv`, `individual_scores.csv`.
- Images: `roc_comparison.png`, `ks_decile_logreg.png`, `ks_decile_xgboost.png`, `calibration_plot_.png`, `xgboost_feature_importance.png`.

## Class imbalance checks
- The pipeline saves simple class-balance CSVs (`outputs/train_class_balance.csv`, `outputs/test_class_balance.csv`) computed by `dataset_init.check_class_balance()` so you can confirm the percentage of defaults in each split. Logistic regression training uses `class_weight='balanced'` to compensate for imbalance; XGBoost can be tuned with `scale_pos_weight` if needed (not set by default here).

## Reproducibility and forcing recompute
- To force recomputation of every cached step set the environment variable `FORCE_RECOMPUTE=true` (in `.env`). The project reads `FORCE_RECOMPUTE` in `src/environment.py`.
