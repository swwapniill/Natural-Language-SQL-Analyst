"""
schema_loader.py

Reads the actual table and column names directly from the SQLite database
via PRAGMA table_info. This is used by the validator to check that
LLM-generated SQL only references real tables/columns -- built from the
live DB, not retyped by hand, so it can't drift out of sync with reality.
"""
import sqlite3


def load_schema(db_path: str) -> dict:
    """Returns {table_name: set(column_names)} for every table in the DB."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    tables = [
        row[0]
        for row in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    ]

    schema = {}
    for table in tables:
        columns = {row[1] for row in cur.execute(f"PRAGMA table_info({table})")}
        schema[table] = columns

    conn.close()
    return schema


if __name__ == "__main__":
    schema = load_schema("olist_real.db")
    for table, cols in schema.items():
        print(f"{table}: {sorted(cols)}")
