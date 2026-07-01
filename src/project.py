from time import perf_counter
import warnings
from log_regression import log_regression, OUTPUTS_DIR
from dataset_init import dataset_init
import scorecardpy as sc
from xgboost_model import train_xgboost
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning, module="scorecardpy")

def creating_scorecard_and_scores(bins, logreg, x_train, test):
	card = sc.scorecard(bins, logreg, x_train.columns)
	card_df = pd.concat(card.values())
	card_df.to_csv(OUTPUTS_DIR / "scorecard_table.csv", index=False)

	scores_df = sc.scorecard_ply(test, card)
	scores_df.to_csv(OUTPUTS_DIR / "individual_scores.csv", index=False)

def main():
	#Initialize dataset first
	pipeline_start, train, test = dataset_init()

	#Logistic regression call
	step_start = perf_counter()
	bins, logreg, x_train, y_train, x_test, y_test = log_regression(train, test)
	print(f"[TIMING] log_regression (total): {perf_counter() - step_start:.2f}s")

	#Creating scorecard
	step_start = perf_counter()
	creating_scorecard_and_scores(bins, logreg, x_train, test)
	print(f"[TIMING] creating scorecards (total): {perf_counter() - step_start:.2f}s")

	#Implementing xgboost for train and test data
	step_start = perf_counter()
	xgboost_metrics = train_xgboost(x_train, y_train, x_test, y_test)
	print(f"[TIMING] xgboost (total): {perf_counter() - step_start:.2f}s")

	print(f"[TIMING] total_pipeline: {perf_counter() - pipeline_start:.2f}s")

if __name__ == "__main__":
	main()
