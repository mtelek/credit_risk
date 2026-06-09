from sqlalchemy import create_engine, text

engine = create_engine("postgresql+psycopg2://admin:password@postgres:5432/credit_risk")

with engine.connect() as connection:
    result = connection.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
    tables = result.fetchall()
    print("Connected to the database. Tables in the public schema:", tables)