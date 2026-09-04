"""
Loads the REAL Olist CSVs (from Kaggle) into SQLite, matching the actual
column structure of the source files -- no forcing into the synthetic
schema. Geolocation is intentionally excluded (1M rows, out of scope for
this project). Category translation is kept as a small lookup table.
"""
import sqlite3
import pandas as pd
import os

UPLOAD_DIR = "/mnt/user-data/uploads"
DB_PATH = "/home/claude/olist_project/olist_real.db"

FILES = {
    "customers": "olist_customers_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "products": "olist_products_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "product_category_name_translation": "product_category_name_translation.csv",
}

if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

conn = sqlite3.connect(DB_PATH)

for table_name, filename in FILES.items():
    path = os.path.join(UPLOAD_DIR, filename)
    df = pd.read_csv(path)
    df.to_sql(table_name, conn, if_exists="replace", index=False)
    print(f"{table_name}: {len(df)} rows, columns = {list(df.columns)}")

# Indexes on FK columns -- real data is 100x bigger than synthetic, this matters now
cur = conn.cursor()
index_stmts = [
    "CREATE INDEX idx_orders_customer_id ON orders(customer_id)",
    "CREATE INDEX idx_order_items_order_id ON order_items(order_id)",
    "CREATE INDEX idx_order_items_product_id ON order_items(product_id)",
    "CREATE INDEX idx_order_items_seller_id ON order_items(seller_id)",
    "CREATE INDEX idx_order_payments_order_id ON order_payments(order_id)",
    "CREATE INDEX idx_order_reviews_order_id ON order_reviews(order_id)",
    "CREATE INDEX idx_customers_unique_id ON customers(customer_unique_id)",
]
for stmt in index_stmts:
    cur.execute(stmt)
conn.commit()
print("\nIndexes created on all FK columns.")

conn.close()
