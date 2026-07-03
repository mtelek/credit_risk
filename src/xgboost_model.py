from xgboost import XGBClassifier
from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold
from log_regression import evaluate_model
import numpy as np
import pandas as pd

def train_xgboost(x_train, y_train, x_test, y_test, n_iter=30, cv_folds=3, search_sample=200000):
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

	print(f"Best CV AUC: {search.best_score_:.4f}")
	print(f"Best params: {search.best_params_}")

	# Refit best params on FULL training data
	model = XGBClassifier(**search.best_params_, random_state=42,
		eval_metric="auc", tree_method="hist")
	model.fit(x_train, y_train, eval_set=[(x_test, y_test)], verbose=50)

	train_metrics = evaluate_model(model, x_train, y_train, label="Train")
	test_metrics = evaluate_model(model, x_test, y_test, label="Test")

	return model, train_metrics, test_metrics
