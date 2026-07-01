from time import perf_counter
import warnings
from log_regression import log_regression, OUTPUTS_DIR
from dataset_init import dataset_init
import scorecardpy as sc
from xgboost_model import train_xgboost
import pandas as pd
import matplotlib.pyplot as plt
from xgboost import plot_importance

warnings.filterwarnings("ignore", category=FutureWarning, module="scorecardpy")

def creating_scorecard_and_scores(bins, logreg, x_train, test):
	card = sc.scorecard(bins, logreg, x_train.columns)
	card_df = pd.concat(card.values())
	card_df.to_csv(OUTPUTS_DIR / "scorecard_table.csv", index=False)

	scores_df = sc.scorecard_ply(test, card)
	scores_df.to_csv(OUTPUTS_DIR / "individual_scores.csv", index=False)

def plot_feature_importance(model, x_train, top_n=20, importance_type="gain"):
	fig, ax = plt.subplots(figsize=(8, max(4, top_n * 0.3)))
	plot_importance(model, max_num_features=top_n, importance_type=importance_type,
		ax=ax, height=0.5,)

	plt.title(f"XGBoost Feature Importance ({importance_type})")
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
	pipeline_start, train, test = dataset_init()

	#Logistic regression call
	step_start = perf_counter()
	bins, logreg, x_train, y_train, x_test, y_test, log_train_metrics, log_test_metrics = log_regression(train, test)
	print(f"[TIMING] log_regression (total): {perf_counter() - step_start:.2f}s")

	#Creating scorecard
	step_start = perf_counter()
	creating_scorecard_and_scores(bins, logreg, x_train, test)
	print(f"[TIMING] creating scorecards (total): {perf_counter() - step_start:.2f}s")

	#Implementing xgboost for train and test data
	step_start = perf_counter()
	xgb_model, xgb_train_metrics, xgb_test_metrics = train_xgboost(x_train, y_train, x_test, y_test)
	plot_feature_importance(xgb_model, x_train)
	print(f"[TIMING] xgboost (total): {perf_counter() - step_start:.2f}s")

	# Compare logistic regressions and xgboost model
	step_start = perf_counter()
	compare_models(log_train_metrics, log_test_metrics, xgb_train_metrics, xgb_test_metrics)
	print(f"[TIMING] logistic regression and xgboost model comparison (total): {perf_counter() - step_start:.2f}s")

	print(f"[TIMING] total_pipeline: {perf_counter() - pipeline_start:.2f}s")

if __name__ == "__main__":
	main()
