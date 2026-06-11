from pathlib import Path
from generate_staging_sql import generate_staging_table_sql, read_column_names

def main():
    csv_path = "/app/data/raw/accepted_2007_to_2018q4.csv/accepted_2007_to_2018Q4.csv"

    # 1) Read CSV header into a Python list
    column_names = read_column_names(csv_path)

    # 2) Generate CREATE TABLE SQL for a staging table with all TEXT columns
    staging_sql = generate_staging_table_sql(column_names, "stg_accepted_loans")

    # 3) Save SQL to file so it can be executed in Postgres
    output_path = Path("/app/sql/staging_accepted_loans.sql")
    output_path.write_text(staging_sql + "\n", encoding="utf-8")

    print(f"Staging SQL written to: {output_path}")
    print(staging_sql)

if __name__ == "__main__":
    main()
