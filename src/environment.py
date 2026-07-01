import os

def get_env(name, default=None):
	value = os.getenv(name, default)
	if value is None:
		raise ValueError(f"Missing required environment variable: {name}")
	return value

def load_db_config():
	db_user = get_env("POSTGRES_USER")
	db_password = get_env("POSTGRES_PASSWORD")
	db_name = get_env("POSTGRES_DB")
	db_host = get_env("POSTGRES_HOST", "postgres")
	db_port = int(get_env("POSTGRES_PORT", "5432"))
	debug_eda = get_env("DEBUG_EDA", "False").lower() == "true"

	return {
		"user": db_user,
		"password": db_password,
		"database": db_name,
		"host": db_host,
		"port": db_port,
		"debug_eda": debug_eda,
	}
