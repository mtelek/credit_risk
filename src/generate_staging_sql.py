import csv
import re
from pathlib import Path

SQL_RESERVED_WORDS = {
	"all",
	"analyze",
	"and",
	"as",
	"asc",
	"between",
	"by",
	"case",
	"check",
	"column",
	"constraint",
	"create",
	"desc",
	"distinct",
	"else",
	"end",
	"exists",
	"false",
	"for",
	"from",
	"group",
	"having",
	"in",
	"insert",
	"into",
	"is",
	"join",
	"like",
	"limit",
	"not",
	"null",
	"on",
	"or",
	"order",
	"select",
	"table",
	"then",
	"true",
	"union",
	"update",
	"values",
	"where",
	"with",
}

def read_column_names(csv_path):
	path = Path(csv_path)
	with path.open(newline="", encoding="utf-8") as f:
		reader = csv.reader(f)
		return next(reader, None)


def _normalize_identifier(name):
	# Lowercase and replace invalid identifier characters with underscores
	normalized = re.sub(r"[^a-zA-Z0-9_]", "_", name.strip().lower())
	normalized = re.sub(r"_+", "_", normalized).strip("_")
	if not normalized:
		normalized = "col"
	if normalized[0].isdigit():
		normalized = f"col_{normalized}"
	if normalized in SQL_RESERVED_WORDS:
		normalized = f"{normalized}_"
	return normalized


def generate_staging_table_sql(column_names, table_name):
	if not column_names:
		raise ValueError("column_names is empty. Could not generate staging table SQL.")

	seen = {}
	column_defs = []
	for raw_name in column_names:
		base_name = _normalize_identifier(raw_name)
		count = seen.get(base_name, 0)
		seen[base_name] = count + 1
		col_name = base_name if count == 0 else f"{base_name}_{count + 1}"
		column_defs.append(f"    {col_name} TEXT")

	columns_sql = ",\n".join(column_defs)
	return f"CREATE UNLOGGED TABLE IF NOT EXISTS {table_name} (\n{columns_sql}\n);"
