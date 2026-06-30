from time import perf_counter
import warnings
from log_regression import log_regression
from dataset_init import dataset_init

warnings.filterwarnings("ignore", category=FutureWarning, module="scorecardpy")

def main():
	#Initialize dataset first
	pipeline_start, train, test = dataset_init()

	#Logistic regression call
	step_start = perf_counter()
	log_regression(train, test)
	print(f"[timing] log_regression (total): {perf_counter() - step_start:.2f}s")

	print(f"[timing] total_pipeline: {perf_counter() - pipeline_start:.2f}s")

if __name__ == "__main__":
	main()
