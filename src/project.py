from multiprocessing.dummy import connection
from pathlib import Path
from time import perf_counter
from generate_staging_sql import generate_staging_table_sql, read_column_names
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
import pandas as pd
from environment import load_db_config
import warnings
import pickle
import numpy as np
import statsmodels.api as sm
from log_regression import log_regression
from dataset_init import _cache_key

warnings.filterwarnings("ignore", category=FutureWarning, module="scorecardpy")
DEBUG_EDA = True

TRAIN_RAW = "/app/data/train_raw.pkl"
TEST_RAW = "/app/data/test_raw.pkl"

DTYPE_MAP = {
	"loan_status": "int8",
	"term": "int16",
	"grade": "category",
	"sub_grade": "category",
	"home_ownership": "category",
	"verification_status": "category",
	"purpose": "category",
	"addr_state": "category",
}

def run_init_sql(engine, init_sql_path, accepted_table_name):
	with engine.connect() as connection:
		accepted_exists = connection.execute(
			text(
				"""
				SELECT EXISTS (
					SELECT 1
					FROM information_schema.tables
					WHERE table_schema = 'public' AND table_name = :table_name
				)
				"""
			),
			{"table_name": accepted_table_name},
			).scalar_one()
		
		accepted_has_rows = False
		if accepted_exists:
			accepted_has_rows = connection.execute(
				text(f"SELECT EXISTS (SELECT 1 FROM {accepted_table_name} LIMIT 1)")
			).scalar_one()

	should_run_init = (not accepted_exists) or (not accepted_has_rows)
	
	if should_run_init:
		init_sql = Path(init_sql_path).read_text(encoding="utf-8")
		raw_connection = engine.raw_connection()
		try:
			with raw_connection.cursor() as cursor:
				cursor.execute(init_sql)
			raw_connection.commit()
		finally:
			raw_connection.close()
	else:
		return

def sql_table_to_pd(engine):
	#import accepted_loans table into pandas
	query = "SELECT * FROM accepted_loans"
	chunks = pd.read_sql_query(text(query), engine, chunksize=100_000)
	
	df = pd.concat(chunks, ignore_index=True)
	return (df)   

def staging_table_check(engine, staging_table_name):
	with engine.connect() as connection:
		table_exists = connection.execute(
			text(
				"""
				SELECT EXISTS (
					SELECT 1
				  FROM information_schema.tables
					WHERE table_schema = 'public' AND table_name = :table_name
				)
				"""
			),
			{"table_name": staging_table_name},
		).scalar_one()
		
		staging_row_count = 0
		if table_exists:
			staging_row_count = connection.execute(text(f"SELECT COUNT(*) FROM {staging_table_name}")
			).scalar_one()
	return table_exists and staging_row_count > 0, staging_row_count

def init_staging_table(csv_path, staging_table_name, engine):
	column_names = read_column_names(csv_path)

	#Generate CREATE TABLE SQL for a staging table with all TEXT columns
	staging_sql = generate_staging_table_sql(column_names, staging_table_name)

	#Save SQL to file so it can be executed in Postgres
	output_path = Path("/app/sql/staging_accepted_loans.sql")
	output_path.write_text(staging_sql + "\n", encoding="utf-8")
	print(f"Staging SQL written to: {output_path}")

	#create staging table in Postgres using SQLAlchemy
	with engine.begin() as connection:
		connection.execute(text(staging_sql))
		connection.execute(text(f"TRUNCATE TABLE {staging_table_name}"))
	print("Staging table created (or already exists).")

	#Bulk load CSV into staging table
	copy_sql = f"COPY {staging_table_name} FROM STDIN WITH (FORMAT CSV, HEADER TRUE)"
	raw_connection = engine.raw_connection()
	try:
		with raw_connection.cursor() as cursor:
			with open(csv_path, "r", encoding="utf-8") as csv_file:
				cursor.copy_expert(copy_sql, csv_file)
		raw_connection.commit()
	finally:
		raw_connection.close()

	with engine.connect() as connection:
		row_count = connection.execute(text(f"SELECT COUNT(*) FROM {staging_table_name}")).scalar_one()
	print(f"Loaded {row_count} rows into {staging_table_name}.")

def calc_cutoff_data(engine):
	return pd.read_sql(
		text("""
			SELECT issue_d
			FROM (
				SELECT issue_d,
					   ROW_NUMBER() OVER (ORDER BY issue_d) AS rn,
					   COUNT(*) OVER () AS total
				FROM accepted_loans
			) t
			WHERE rn = FLOOR(total * 0.8)
			LIMIT 1
		"""),
		engine
	).iloc[0, 0]

def load_train_and_test_data_in_pd(engine, cutoff_date, force_recompute=False):
	feature_cols = ["loan_status", "loan_amnt", "term", "int_rate", "installment", "grade", "sub_grade",
		"emp_length", "home_ownership", "annual_inc", "verification_status", "purpose",
		"addr_state", "dti", "fico_range_low", "fico_range_high", "delinq_2yrs",
		"inq_last_6mths", "open_acc", "pub_rec", "revol_bal", "total_rev_hi_lim",
		"revol_util", "total_acc", "mort_acc", "pub_rec_bankruptcies", "tax_liens",
		"credit_utilization", "months_since_earliest_credit_line"]
	key_path = Path("/app/data/raw_cache.key")
	cache_key = _cache_key(feature_cols, cutoff_date)
	
	if (not force_recompute and Path(TRAIN_RAW).exists() and Path(TEST_RAW).exists() and key_path.exists() and key_path.read_text() == cache_key):
		train = pd.read_pickle(TRAIN_RAW)
		test = pd.read_pickle(TEST_RAW)
		print("Loaded cached train/test data.")
		return train, test

	cols =", ".join(feature_cols)

	train = pd.read_sql(
		text(f"""
			SELECT {cols}
			FROM accepted_loans
			WHERE issue_d <= :cutoff
		"""),
		engine,
		params={"cutoff": cutoff_date}
	)
	test = pd.read_sql(
		text(f"""
			SELECT {cols}
			FROM accepted_loans
			WHERE issue_d > :cutoff
		"""),
		engine,
		params={"cutoff": cutoff_date}
	)
	
	# Apply DTYPE optimization
	train = train.astype({k: v for k, v in DTYPE_MAP.items() if k in train.columns})
	test = test.astype({k: v for k, v in DTYPE_MAP.items() if k in test.columns})
 
	train.to_pickle(TRAIN_RAW)
	test.to_pickle(TEST_RAW)
	key_path.write_text(cache_key)
	print("Saved train/test cache.")
	return train, test

def check_class_balance(df, y, label="dataset"):
	counts = df[y].value_counts()
	proportions = df[y].value_counts(normalize=True)
	print(f"\nClass balance for {label}:")
	print(counts)
	print(proportions.round(4))

def main():
	staging_table_name = "stg_accepted_loans"
	accepted_table_name = "accepted_loans"
	init_sql_path = "/app/sql/init.sql"
	csv_path = "/app/data/raw/accepted_2007_to_2018q4.csv/accepted_2007_to_2018Q4.csv"
	pipeline_start = perf_counter()

	cfg = load_db_config()
	engine = create_engine(
		f"postgresql+psycopg2://{cfg['user']}:{cfg['password']}@{cfg['host']}:{cfg['port']}/{cfg['database']}",
		poolclass=NullPool,
	)

	step_start = perf_counter()
	staging_ready, staging_row_count = staging_table_check(engine, staging_table_name)
	print(f"[timing] staging_table_check: {perf_counter() - step_start:.2f}s")
	if staging_ready:
		print(f"{staging_table_name} already exists. Skipping create/load. Current rows: {staging_row_count}")

	#Initialize staging table if not exists
	else:
		step_start = perf_counter()
		init_staging_table(csv_path, staging_table_name, engine)
		print(f"[timing] init_staging_table: {perf_counter() - step_start:.2f}s")

	# Initialize or refresh accepted_loans transformations before loading to pandas.
	step_start = perf_counter()
	run_init_sql(engine, init_sql_path, accepted_table_name)
	print(f"[timing] run_init_sql: {perf_counter() - step_start:.2f}s")

	#Create train_data and test_data tables based on cutoff date
	step_start = perf_counter()
	cutoff_date = calc_cutoff_data(engine)
	print(f"Cutoff date: {cutoff_date}")
	print(f"[timing] calc_cutoff_data: {perf_counter() - step_start:.2f}s")

	#Load train and test data into pandas
	step_start = perf_counter()
	train, test = load_train_and_test_data_in_pd(engine, cutoff_date)
	print(f"[timing] load_train_and_test_data_in_pd: {perf_counter() - step_start:.2f}s")

	if DEBUG_EDA:
		print(train.isna().mean().sort_values(ascending=False))
		print(train.nunique().sort_values())

	#Check imbalance in the datasets
	check_class_balance(train, "loan_status", label="train")
	check_class_balance(test, "loan_status", label="test")

	#Logistic regression call
	step_start = perf_counter()
	logreg, bins, train_metrics, test_metrics = log_regression(train, test)
	print(f"[timing] log_regression (total): {perf_counter() - step_start:.2f}s")

	print(f"[timing] total_pipeline: {perf_counter() - pipeline_start:.2f}s")

if __name__ == "__main__":
	main()
