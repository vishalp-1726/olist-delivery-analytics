"""Exports the results in the format each team uses:
  - CSV copies of the report tables for the Tableau Public dashboard (totals only, no customer or seller IDs)
  - one Excel file for Operations: the seller watchlist, the promise-day options and the impact table

Usage (after notebooks 01-05):  uv run python -m src.export
"""
import pandas as pd

from src.config import PROCESSED
from src.db import query

# the tables the dashboard uses: totals per month, band, state, route or action
TABLES = [
    "report_monthly", "report_late_bands", "report_review_summary", "report_repeat", "report_repeat_value",
    "report_handover", "report_time_split", "report_states", "report_routes", "report_spikes",
    "report_promise_buffer", "report_impact",
]


def export_csv():
    out = PROCESSED / "dashboard"
    out.mkdir(parents=True, exist_ok=True)
    for t in TABLES:
        query(f"select * from {t}").to_csv(out / f"{t}.csv", index=False)
    print(f"  wrote {len(TABLES)} CSV files to {out}")


def export_excel():
    # the watchlist has seller IDs, so it goes only to this file (kept out of git), never to Tableau Public
    path = PROCESSED / "handoff_operations.xlsx"
    with pd.ExcelWriter(path) as xl:
        query("select * from report_seller_watchlist order by late_orders desc").to_excel(
            xl, sheet_name="seller_watchlist", index=False)
        query("select * from report_promise_buffer order by extra_days").to_excel(
            xl, sheet_name="promise_day_options", index=False)
        query("select * from report_impact").to_excel(xl, sheet_name="impact", index=False)
    print(f"  wrote {path}")


if __name__ == "__main__":
    export_csv()
    export_excel()
