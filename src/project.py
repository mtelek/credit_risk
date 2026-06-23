from multiprocessing.dummy import connection
from pathlib import Path
from time import perf_counter
from generate_staging_sql import generate_staging_table_sql, read_column_names
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
import pandas as pd
from environment import load_db_config
import scorecardpy as sc

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
	cutoff_date = engine.connect().execute(
		text("""
		WITH cutoff AS (
			SELECT issue_d AS cutoff_date
			FROM accepted_loans
			ORDER BY issue_d
			OFFSET(
				SELECT FLOOR(COUNT(*) * 0.8)
				FROM accepted_loans
			)
			LIMIT 1
		)
		SELECT cutoff_date FROM cutoff;
		""")
	).scalar_one()
	return cutoff_date

def create_train_data(engine, cutoff_date):
	with engine.begin() as connection:
		connection.execute(
			text("""
			CREATE TABLE IF NOT EXISTS train_data AS
			SELECT *
			FROM accepted_loans
			WHERE issue_d <= :cutoff_date;
			"""),
			{"cutoff_date": cutoff_date}
		)
	print("train_data table created.")
 
def create_test_data(engine, cutoff_date):
	with engine.begin() as connection:
		connection.execute(
			text("""
			CREATE TABLE IF NOT EXISTS test_data AS
			SELECT *
			FROM accepted_loans
			WHERE issue_d > :cutoff_date;
			"""),
			{"cutoff_date": cutoff_date}
		)
	print("test_data table created.")

def load_train_and_test_data_in_pd(engine):
	train = pd.read_sql("SELECT * FROM train_data", engine)
	test = pd.read_sql("SELECT * FROM test_data", engine)
	return train, test

def apply_woe(train, test, y):
    bins = sc.woebin(train, y=y)
    train_woe = sc.woebin_ply(train, bins)
    test_woe = sc.woebin_ply(test, bins)
    
    y_train = train_woe[y]
    y_test = test_woe[y]
    
    x_train = train_woe.drop(columns=[y])
    y_train = test_woe.drop(columns=[y])
    
    return y_train, x_train, y_test, x_test, bins

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
	print(f"[timing] total_pipeline: {perf_counter() - pipeline_start:.2f}s")

	#Create train_data and test_data tables based on cutoff date
	cutoff_date = calc_cutoff_data(engine)
	print(f"Cutoff date: {cutoff_date}")
	create_train_data(engine, cutoff_date)
	create_test_data(engine, cutoff_date)

	#Load train and test data into pandas
	train, test = load_train_and_test_data_in_pd(engine)
	
	#Apply WoE to train and test data
	y = "loan_status"
	y_train, x_train, y_test, x_test, bins = apply_woe(train, test, y)
 
if __name__ == "__main__":
	main()
