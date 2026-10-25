"""Data-quality checks. Each check counts the bad rows, so 0 = pass.
ERROR = must be 0 before any number is used. WARN = a known issue, only reported.

Usage:  uv run python -m src.dq_checks
"""
import psycopg

from src.db import PG_URL

CHECKS = [
    # (name, level, query that counts bad rows)
    ("orders: delivered but no estimated (promised) date", "ERROR",
     "select count(*) from orders where order_status = 'delivered' and order_estimated_delivery_date is null"),
    ("orders: delivered order without items", "ERROR",
     "select count(*) from orders o where order_status = 'delivered' and not exists "
     "(select 1 from order_items i where i.order_id = o.order_id)"),
    ("items: price is 0 or below", "ERROR",
     "select count(*) from order_items where price <= 0"),
    ("reviews: score not between 1 and 5", "ERROR",
     "select count(*) from order_reviews where review_score not between 1 and 5"),
    ("products: category without an English name", "ERROR",
     "select count(*) from products p left join category_translation t using (product_category_name) "
     "where t.product_category_name is null"),
    ("v_delivered: one row per order", "ERROR",
     "select count(*) - count(distinct order_id) from v_delivered"),
    ("orders: delivered but no delivery date (left out)", "WARN",
     "select count(*) from orders where order_status = 'delivered' and order_delivered_customer_date is null"),
    ("orders: canceled but has a delivery date (left out)", "WARN",
     "select count(*) from orders where order_status = 'canceled' and order_delivered_customer_date is not null"),
    ("orders: impossible timestamps (handover times not used)", "WARN",
     "select count(*) from orders where bad_timestamps"),
    ("reviews: order has more than one review (latest kept)", "WARN",
     "select count(*) from (select order_id from order_reviews group by order_id having count(*) > 1) t"),
    ("delivered orders without a review", "WARN",
     "select count(*) from v_delivered where review_score is null"),
]


def run_checks():
    """Run every check, save the results in dq_results, and return them."""
    results = []
    with psycopg.connect(PG_URL, autocommit=True) as con:
        for name, level, sql in CHECKS:
            bad_rows = con.execute(sql).fetchone()[0]
            con.execute("insert into dq_results (check_name, severity, failed_rows) values (%s, %s, %s)",
                        (name, level, bad_rows))
            results.append((name, level, bad_rows))
    return results


def show(results):
    for name, level, bad_rows in results:
        if bad_rows == 0:
            status = "PASS"
        elif level == "ERROR":
            status = "FAIL"
        else:
            status = "WARN"
        print(f"  [{status}] {name:<58} {bad_rows:>7,}")


if __name__ == "__main__":
    results = run_checks()
    show(results)
    if any(level == "ERROR" and bad_rows > 0 for name, level, bad_rows in results):
        raise SystemExit("data-quality ERROR: fix it before going on")
