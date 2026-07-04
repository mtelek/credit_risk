from xgboost import XGBClassifier
from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold
from log_regression import evaluate_model
import numpy as np
import pandas as pd
from pathlib import Path
import pickle
from dataset_init import _cache_key

XGB_MODEL_PATH = "/app/data/cache/xgboost_model.pkl"
XGB_KEY_PATH = "/app/data/key/xgboost_model.key"
OUTPUTS_DIR = Path("/app/outputs")

def train_xgboost(x_train, y_train, x_test, y_test, cfg, n_iter=30, cv_folds=3, search_sample=200000):
	model_key = _cache_key(sorted(x_train.columns.tolist()), f"xgboost_{n_iter}_{cv_folds}")
    
	if (not cfg['force_recompute'] and Path(XGB_MODEL_PATH).exists() and Path(XGB_KEY_PATH).exists() and Path(XGB_KEY_PATH).read_text() == model_key):
		with open(XGB_MODEL_PATH, "rb") as f:
			model = pickle.load(f)
		print("[INFO] Loaded cached XGBoost model.")
	else:
		print("[INFO] Training XGBoost model...")
	
		# Sample for hyperparameter search only
		sample_idx = pd.Series(x_train.index).sample(n=min(search_sample, len(x_train)), random_state=42)
		x_search = x_train.loc[sample_idx]
		y_search = y_train.loc[sample_idx]	

		param_dist = {
			"n_estimators": [200, 300, 500],
			"max_depth": [3, 4, 5],
			"learning_rate": [0.01, 0.05, 0.1],
			"subsample": [0.7, 0.85, 1.0],
			"colsample_bytree": [0.7, 0.85, 1.0],
			"min_child_weight": [1, 5],
			"gamma": [0, 0.1],
		}

		base_model = XGBClassifier(random_state=42, eval_metric="auc", tree_method="hist")

		cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=42)

		search = RandomizedSearchCV(estimator=base_model, param_distributions=param_dist, n_iter=n_iter,
			scoring="roc_auc", cv=cv, n_jobs=-1, verbose=1, random_state=42,
		)
		search.fit(x_search, y_search)
		best_params_df = pd.DataFrame([search.best_params_])
		best_params_df.to_csv(OUTPUTS_DIR / "xgboost_best_params.csv", index=False)

		if cfg['debug_eda'] == True:
			print(f"Best CV AUC: {search.best_score_:.4f}")
			print(f"Best params: {search.best_params_}")

		# Refit best params on FULL training data
		model = XGBClassifier(**search.best_params_, random_state=42,
			eval_metric="auc", tree_method="hist")

		verbose = 50 if cfg['debug_eda'] else False
		model.fit(x_train, y_train, eval_set=[(x_test, y_test)], verbose=verbose)

		with open(XGB_MODEL_PATH, "wb") as f:
			pickle.dump(model, f)

		Path(XGB_KEY_PATH).write_text(model_key)
		print("[INFO] Saved XGBoost model.")

	train_metrics = evaluate_model(model, x_train, y_train, label="Train")
	test_metrics = evaluate_model(model, x_test, y_test, label="Test")

	return model, train_metrics, test_metrics
