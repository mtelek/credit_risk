from multiprocessing.dummy import connection
from pathlib import Path
from time import perf_counter
from generate_staging_sql import generate_staging_table_sql, read_column_names
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
import pandas as pd
from environment import load_db_config
import scorecardpy as sc
import warnings
from sklearn.linear_model import LogisticRegression
import re
from sklearn.metrics import roc_auc_score
from scipy.stats import ks_2samp
import pickle
import numpy as np
import hashlib

warnings.filterwarnings("ignore", category=FutureWarning, module="scorecardpy")
BINS_CACHE_PATH = "/app/data/bins_cache.pkl"
TRAIN_WOE = "/app/data/train_woe.pkl"
TEST_WOE = "/app/data/test_woe.pkl"
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

def _cache_key(*parts):
	raw = "||".join(str(p) for p in parts)
	return hashlib.md5(raw.encode()).hexdigest()

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

def apply_woe(train, test, y, force_recompute=False):
	woe_key_path = Path("/app/data/woe_cache.key")
	woe_key = _cache_key(sorted(train.columns.tolist()), y)

	if (not force_recompute and Path(BINS_CACHE_PATH).exists() and Path(TRAIN_WOE).exists() and Path(TEST_WOE).exists() and woe_key_path.exists() and woe_key_path.read_text() == woe_key):
		with open(BINS_CACHE_PATH, "rb") as f:
			bins = pickle.load(f)

		train_woe = pd.read_pickle(TRAIN_WOE)
		test_woe = pd.read_pickle(TEST_WOE)

		print("Loaded cached WOE + bins.")
	else:
		print("Recomputing WOE...")
		bins = sc.woebin(train, y=y, check_cate_num=False)
		train_woe = sc.woebin_ply(train, bins)
		test_woe = sc.woebin_ply(test, bins)

		with open(BINS_CACHE_PATH, "wb") as f:
			pickle.dump(bins, f)

		train_woe.to_pickle(TRAIN_WOE)
		test_woe.to_pickle(TEST_WOE)
		woe_key_path.write_text(woe_key)
		print("Saved WOE + bins cache.")

	y_train = train_woe[y].astype(int)
	y_test = test_woe[y].astype(int)

	x_train = train_woe.drop(columns=[y])
	x_test = test_woe.drop(columns=[y])

	return y_train, x_train, y_test, x_test, bins

def evaluate_model(model, x, y, label="dataset"):
	y_pred_proba = model.predict_proba(x)[:, 1]

	auc = roc_auc_score(y, y_pred_proba)
	gini = 2 * auc - 1

	y_arr = np.asarray(y)
	pos = y_pred_proba[y_arr == 1]
	neg = y_pred_proba[y_arr == 0]
	ks = ks_2samp(pos, neg).statistic

	print(f"\n{label} performance:")
	print(f"  AUC:  {auc:.4f}")
	print(f"  Gini: {gini:.4f}")
	print(f"  KS:   {ks:.4f}")
	return {"auc": auc, "gini": gini, "ks": ks}

def log_regression(train, test):
	#Apply WoE to train and test data
	step_start = perf_counter()
	y = "loan_status"
	y_train, x_train, y_test, x_test, bins = apply_woe(train, test, y)
	print(f"[timing] apply_woe: {perf_counter() - step_start:.2f}s")
 
	#Model with Logistic Regression
	step_start = perf_counter()
	logreg = LogisticRegression(class_weight='balanced', max_iter=1000, random_state=42)
	logreg.fit(x_train, y_train)
	print(f"[timing] logreg.fit: {perf_counter() - step_start:.2f}s")
 
	#Check coefficients make business sense
	coef_df = pd.DataFrame({
		'variable': [re.sub('_woe$', '', col) for col in x_train.columns],
		'coefficient': logreg.coef_[0]
	}).sort_values('coefficient', ascending=False)

	print(coef_df.to_string(index=False))

	negative_coefs = coef_df[coef_df['coefficient'] < 0]
	if not negative_coefs.empty:
		print("\nUnexpected negative coefficients — investigate:")
		print(negative_coefs.to_string(index=False))
	else:
		print("\nAll coefficients positive — consistent with WOE convention.")


	key_vars = ['dti', 'annual_inc', 'int_rate']
	for var in key_vars:
		if var in bins:
			print(f"\n{var}:")
			print(bins[var][['bin', 'count_distr', 'badprob', 'woe']])
 
	#Evaluate model
	step_start = perf_counter()
	train_metrics = evaluate_model(logreg, x_train, y_train, label="Train")
	test_metrics = evaluate_model(logreg, x_test,  y_test,  label="Test")
	print(f"[timing] evaluate_model (train+test): {perf_counter() - step_start:.2f}s")
 
	auc_gap = train_metrics['auc'] - test_metrics['auc']
	print(f"\nTrain-Test AUC gap: {auc_gap:.4f}")
	if auc_gap > 0.05:
		print("Meaningful gap — investigate possible overfitting.")
	return logreg, bins, train_metrics, test_metrics

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
