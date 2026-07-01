from xgboost import XGBClassifier
from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold
from log_regression import evaluate_model
import numpy as np

def train_xgboost(x_train, y_train, x_test, y_test, n_iter=30, cv_folds=5):
	param_dist = {
		"n_estimators": [100, 200, 300],
		"max_depth": [3, 4, 5, 6],
		"learning_rate": [0.01, 0.03, 0.05, 0.1],
		"subsample": [0.7, 0.8, 0.9, 1.0],
		"colsample_bytree": [0.6, 0.7, 0.8, 1.0],
		"min_child_weight": [1, 3, 5],
		"gamma": [0, 0.1, 0.3],
	}

	base_model = XGBClassifier(random_state=42, eval_metric="auc")

	cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=42)

	search = RandomizedSearchCV(estimator=base_model, param_distributions=param_dist, n_iter=n_iter,
		scoring="roc_auc", cv=cv, n_jobs=-1, verbose=1, random_state=42,
	)
	search.fit(x_train, y_train)

	print(f"Best CV AUC: {search.best_score_:.4f}")
	print(f"Best params: {search.best_params_}")

	model = search.best_estimator_

	train_metrics = evaluate_model(model, x_train, y_train, label="Train")
	test_metrics = evaluate_model(model, x_test, y_test, label="Test")

	return model, train_metrics, test_metrics
