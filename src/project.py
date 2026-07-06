from time import perf_counter
import warnings
from log_regression import log_regression, OUTPUTS_DIR
from dataset_init import dataset_init, _cache_key
import scorecardpy as sc
from xgboost_model import train_xgboost
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
import pickle
from comparison_and_evaluation import plot_roc_curve, plot_decile_ks, plot_calibration

warnings.filterwarnings("ignore", category=FutureWarning, module="scorecardpy")

SCORECARD_PATH = "/app/data/cache/scorecard.pkl"
SCORES_PATH = "/app/data/cache/scores.pkl"
SCORECARD_KEY_PATH = "/app/data/key/scorecard.key"

def _scorecard_key(bins, logreg, columns):
	return _cache_key(sorted(columns.tolist()),str(logreg.coef_.round(6).tolist()), str(len(bins)))

def creating_scorecard_and_scores(bins, logreg, x_train, test, force_compute):
	key = _scorecard_key(bins, logreg, x_train.columns)
	if (not force_compute and Path(SCORECARD_PATH).exists() and Path(SCORES_PATH).exists() and Path(SCORECARD_KEY_PATH).exists() and Path(SCORECARD_KEY_PATH).read_text() == key):
		print("[INFO] Loading cached scorecard + scores")
  
		with open(SCORECARD_PATH, "rb") as f:
			card = pickle.load(f)
		with open(SCORES_PATH, "rb") as f:
			scores_df = pickle.load(f)
		return

	print("[INFO] Computing scorecard + scores")
	card = sc.scorecard(bins, logreg, x_train.columns)
	card_df = pd.concat(card.values())
	card_df.to_csv(OUTPUTS_DIR / "scorecard_table.csv", index=False)

	scores_df = sc.scorecard_ply(test, card)
	scores_df.to_csv(OUTPUTS_DIR / "individual_scores.csv", index=False)

	with open(SCORECARD_PATH, "wb") as f:
		pickle.dump(card, f)

	with open(SCORES_PATH, "wb") as f:
		pickle.dump(scores_df, f)
	
	Path(SCORECARD_KEY_PATH).write_text(key)
	print("[INFO] Saved scorecard cache")

def plot_feature_importance(model, x_train, top_n=20, importance_type="gain"):
	importances = np.asarray(model.feature_importances_, dtype=float)
	if x_train is not None and len(x_train.columns) == len(importances):
		feature_names = [str(col).replace("_woe", "") for col in x_train.columns]
	else:
		feature_names = [f"feature_{i}" for i in range(len(importances))]

	order = np.argsort(importances)[::-1][:top_n]
	sorted_names = [feature_names[i] for i in order]
	sorted_importances = importances[order]

	fig, ax = plt.subplots(figsize=(8, max(4, top_n * 0.3)))
	y_pos = np.arange(len(sorted_names))
	bars = ax.barh(y_pos, sorted_importances, color="steelblue")
	ax.set_yticks(y_pos, sorted_names)
	ax.invert_yaxis()
	ax.set_xlabel("Importance")
	ax.set_title(f"XGBoost Feature Importance ({importance_type})")

	for bar, value in zip(bars, sorted_importances):
		ax.text(value + 0.001, bar.get_y() + bar.get_height() / 2, f"{value:.4f}", va="center", ha="left", fontsize=8)

	plt.tight_layout()
	fig.savefig(OUTPUTS_DIR / "xgboost_feature_importance.png", dpi=150)
	plt.close(fig)

def compare_models(log_train_metrics, log_test_metrics, xgb_train_metrics, xgb_test_metrics):
	def to_series(eval_table):
		# eval_table is a 1-row DataFrame like Dataset | AUC | Gini | KS
		return eval_table.drop(columns="Dataset").iloc[0]

	comparison = pd.DataFrame({
		"Logistic Regression (Train)": to_series(log_train_metrics),
		"Logistic Regression (Test)": to_series(log_test_metrics),
		"XGBoost (Train)": to_series(xgb_train_metrics),
		"XGBoost (Test)": to_series(xgb_test_metrics),
	}).round(4)

	comparison.index.name = "Metric"
	output_path = OUTPUTS_DIR / "model_comparison.csv"
	comparison.to_csv(output_path)
	print(f"Saved comparison to {output_path}")
	return comparison

def main():
	#Initialize dataset first
	pipeline_start, train, test, cfg = dataset_init()

	#Logistic regression call
	step_start = perf_counter()
	bins, logreg, x_train, y_train, x_test, y_test, log_train_metrics, log_test_metrics = log_regression(train, test)
	print(f"[TIMING] log_regression (total): {perf_counter() - step_start:.2f}s")

	#Creating scorecard
	step_start = perf_counter()
	creating_scorecard_and_scores(bins, logreg, x_train, test, cfg['force_recompute'])
	print(f"[TIMING] creating scorecards (total): {perf_counter() - step_start:.2f}s")

	#Implementing xgboost for train and test data
	step_start = perf_counter()
	xgb_model, xgb_train_metrics, xgb_test_metrics = train_xgboost(x_train, y_train, x_test, y_test, cfg)
	plot_feature_importance(xgb_model, x_train)
	print(f"[TIMING] xgboost (total): {perf_counter() - step_start:.2f}s")

	# Compare logistic regressions and xgboost model
	step_start = perf_counter()
	compare_models(log_train_metrics, log_test_metrics, xgb_train_metrics, xgb_test_metrics)
	print(f"[TIMING] logistic regression and xgboost model comparison (total): {perf_counter() - step_start:.2f}s")

	step_start = perf_counter()
	plot_roc_curve(logreg, xgb_model, x_test, y_test)
	print(f"[TIMING] ROC curve: {perf_counter() - step_start:.2f}s")

	step_start = perf_counter()
	plot_decile_ks(logreg, x_test, y_test, "logreg")
	plot_decile_ks(xgb_model, x_test, y_test, "xgboost")
	print(f"[TIMING] decile_ks: {perf_counter() - step_start:.2f}s")

	step_start = perf_counter()
	plot_calibration(logreg, xgb_model, x_test, y_test, "logreg", "xgboost")
	print(f"[TIMING] plot calibration for model logreg and xgboost: {perf_counter() - step_start:.2f}s")
	print(f"[TIMING] total_pipeline: {perf_counter() - pipeline_start:.2f}s")

if __name__ == "__main__":
	main()
