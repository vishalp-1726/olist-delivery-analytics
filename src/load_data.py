"""Load the Kaggle CSV files into PostgreSQL, then run the cleaning, views and report SQL files.

Usage:  uv run python -m src.load_data

Each loaded file is logged in load_log, so a file is never loaded twice.
"""
import csv
import time

import psycopg

from src.config import RAW, SQL
from src.db import PG_URL, copy_csv, run_sql_file

# table -> file. Customers, sellers and products first: orders and items point to them.
# Not loaded: payments (order value comes from the items) and geolocation (states are enough, no distances)
FILES = {
    "customers": "olist_customers_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
}


def already_loaded(file_name):
    with psycopg.connect(PG_URL) as con:
        row = con.execute("select 1 from load_log where file_name = %s", (file_name,)).fetchone()
    return row is not None


def load_file(table, file_name):
    if already_loaded(file_name):
        print("  skip (already loaded)", file_name)
        return
    path = RAW / file_name
    # utf-8-sig: the translation file starts with a BOM, which would end up in the first column name
    with open(path, encoding="utf-8-sig") as f:
        columns = next(csv.reader(f))
    start = time.time()
    rows = copy_csv(path, table, columns)
    with psycopg.connect(PG_URL, autocommit=True) as con:
        con.execute("insert into load_log (file_name, rows_loaded) values (%s, %s)", (file_name, rows))
    print(f"  loaded {rows:>9,} rows into {table:<21} ({time.time() - start:.0f}s)")


if __name__ == "__main__":
    run_sql_file(SQL / "01_create_tables.sql")
    for table, file_name in FILES.items():
        load_file(table, file_name)
    for name in ["02_clean.sql", "03_views.sql", "04_reports.sql"]:
        start = time.time()
        run_sql_file(SQL / name)
        print(f"  ran {name} ({time.time() - start:.0f}s)")
