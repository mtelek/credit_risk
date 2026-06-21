from pathlib import Path
from generate_staging_sql import generate_staging_table_sql, read_column_names
from sqlalchemy import create_engine, text
import pandas as pd

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
	print(df.shape)
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

def main():
	staging_table_name = "stg_accepted_loans"
	accepted_table_name = "accepted_loans"
	init_sql_path = "/app/sql/init.sql"
	csv_path = "/app/data/raw/accepted_2007_to_2018q4.csv/accepted_2007_to_2018Q4.csv"

	engine = create_engine("postgresql+psycopg2://admin:password@postgres:5432/credit_risk")

	staging_ready, staging_row_count = staging_table_check(engine, staging_table_name)
	if staging_ready:
		print(f"{staging_table_name} already exists. Skipping create/load. Current rows: {staging_row_count}")

	#Initialize staging table if not exists
	else:
		init_staging_table(csv_path, staging_table_name, engine)

	# Initialize or refresh accepted_loans transformations before loading to pandas.
	run_init_sql(engine, init_sql_path, accepted_table_name)
	
	#import accepted_loans table into pandas
	df = sql_table_to_pd(engine)
	print(f"{accepted_table_name} loaded into pandas: {df.shape}")

if __name__ == "__main__":
	main()
