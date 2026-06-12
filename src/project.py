from pathlib import Path
from generate_staging_sql import generate_staging_table_sql, read_column_names
from sqlalchemy import create_engine, text

def main():
    table_name = "stg_accepted_loans"
    csv_path = "/app/data/raw/accepted_2007_to_2018q4.csv/accepted_2007_to_2018Q4.csv"

    engine = create_engine("postgresql+psycopg2://admin:password@postgres:5432/credit_risk")
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
            {"table_name": table_name},
        ).scalar_one()

    if table_exists:
        with engine.connect() as connection:
            row_count = connection.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one()
        print(f"{table_name} already exists. Skipping create/load. Current rows: {row_count}")
        return

    #Read CSV header into a Python list
    column_names = read_column_names(csv_path)

    #Generate CREATE TABLE SQL for a staging table with all TEXT columns
    staging_sql = generate_staging_table_sql(column_names, table_name)

    #Save SQL to file so it can be executed in Postgres
    output_path = Path("/app/sql/staging_accepted_loans.sql")
    output_path.write_text(staging_sql + "\n", encoding="utf-8")
    print(f"Staging SQL written to: {output_path}")
    #print(staging_sql)

    #create staging table in Postgres using SQLAlchemy
    with engine.begin() as connection:
        connection.execute(text(staging_sql))
        connection.execute(text(f"TRUNCATE TABLE {table_name}"))
    print("Staging table created (or already exists).")

    #Bulk load CSV into staging table
    copy_sql = f"COPY {table_name} FROM STDIN WITH (FORMAT CSV, HEADER TRUE)"
    raw_connection = engine.raw_connection()
    try:
        with raw_connection.cursor() as cursor:
            with open(csv_path, "r", encoding="utf-8") as csv_file:
                cursor.copy_expert(copy_sql, csv_file)
        raw_connection.commit()
    finally:
        raw_connection.close()

    with engine.connect() as connection:
        row_count = connection.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one()
    print(f"Loaded {row_count} rows into {table_name}.")

if __name__ == "__main__":
    main()
