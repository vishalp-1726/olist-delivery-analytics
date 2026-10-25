# %% [markdown]
# # 01 - Know the data: size, period, the problems in the raw files, and what I did about each one

# %% setup
import sys
from pathlib import Path

# "from src ..." works from VS Code (notebooks folder) and from the terminal (project folder)
project = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(project))

import pandas as pd

from src.config import RAW
from src.db import query
from src.dq_checks import run_checks, show

pd.set_option("display.width", 150)
pd.set_option("display.max_columns", 20)

# %% 1. Rows in each table
for table in ["customers", "sellers", "products", "category_translation", "orders", "order_items", "order_reviews"]:
    n = query(f"select count(*) as n from {table}").n[0]
    print(f"{table:<22} {n:>10,}")

# %% 2. Period covered and order status
print(query("""select min(order_purchase_timestamp) as first_order, max(order_purchase_timestamp) as last_order
               from orders"""))
print(query("select order_status, count(*) as orders from orders group by 1 order by 2 desc").to_string(index=False))
print(query("select count(*) as delivered_orders_used from v_delivered"))

# %% 3. Orders per month: the first and last months are too thin to compare
monthly = query("""select to_char(order_purchase_timestamp, 'YYYY-MM') as month, count(*) as orders
                   from orders group by 1 order by 1""")
print(monthly.to_string(index=False))

# %% 4. Customers: customer_id is one per order, customer_unique_id one per person
print(query("""select count(*) as customer_ids, count(distinct customer_unique_id) as people
               from customers"""))

# %% 5. Problems found in the raw files, and the decision for each
print(query("""select count(*) filter (where order_status = 'delivered' and order_delivered_customer_date is null) as delivered_no_date,
                      count(*) filter (where order_status = 'canceled' and order_delivered_customer_date is not null) as canceled_with_date,
                      count(*) filter (where order_delivered_carrier_date < order_purchase_timestamp) as handover_before_purchase,
                      count(*) filter (where order_delivered_customer_date < order_delivered_carrier_date) as delivered_before_handover
               from orders"""))
print(query("""select count(*) - count(distinct review_id) as reused_review_ids,
                      (select count(*) from (select order_id from order_reviews group by 1 having count(*) > 1) t)
                          as orders_with_2plus_reviews
               from order_reviews"""))

# the products table now says 'sem_categoria' for these (02_clean.sql); count them in the raw file
raw_products = pd.read_csv(RAW / "olist_products_dataset.csv")
print("products without a category in the file:", raw_products.product_category_name.isna().sum())

# seller city names are typed by hand; only the state is used, so they are left as they are
print(query("""select seller_city, seller_state from sellers
               where seller_city ~ '[0-9/\\-]' or seller_city like '%  %' limit 10"""))

# %% 6. Data-quality checks: every ERROR check must be 0 before any number is used
show(run_checks())
