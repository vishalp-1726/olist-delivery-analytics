# %% [markdown]
# # 02 - Q1: How big is the late-delivery problem, and when does it spike?
# Late = delivered after the date promised at checkout (order_estimated_delivery_date).

# %% setup
import sys
from pathlib import Path

project = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(project))

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

from src.config import SETTINGS
from src.db import query
from src.style import apply_style, save, SERIES

apply_style()
pd.set_option("display.width", 150)
pd.set_option("display.max_columns", 20)
first, last = SETTINGS["analysis"]["first_month"], SETTINGS["analysis"]["last_month"]

# %% 1. The headline: how many delivered orders were late?
total = query(f"""select count(*) as delivered, count(*) filter (where is_late) as late,
                         round(avg(is_late::int), 4) as late_rate
                  from v_delivered where purchase_month between '{first}' and '{last}'""")
print(total)

# %% 2. Month by month
monthly = query(f"select * from report_monthly where purchase_month between '{first}' and '{last}'")
print(monthly[["purchase_month", "delivered_orders", "late_orders", "late_rate", "avg_review"]].to_string(index=False))
print("worst months:")
print(monthly.nlargest(3, "late_rate")[["purchase_month", "late_rate", "late_orders"]].to_string(index=False))

fig, (top, bottom) = plt.subplots(2, 1, figsize=(10, 6.5), sharex=True, gridspec_kw={"height_ratios": [3, 2]})
top.plot(monthly.purchase_month, monthly.late_rate, marker="o", markersize=3, color=SERIES[1])
for _, row in monthly.nlargest(3, "late_rate").iterrows():
    top.annotate(f"{row.late_rate:.1%}", (row.purchase_month, row.late_rate), xytext=(0, 6),
                 textcoords="offset points", ha="center", fontsize=9)
top.yaxis.set_major_locator(mtick.MultipleLocator(0.04))
top.yaxis.set_major_formatter(mtick.PercentFormatter(1, decimals=0))
top.set_title("Share of delivered orders that arrived after the promised date")
bottom.bar(monthly.purchase_month, monthly.delivered_orders, color=SERIES[0], width=0.7)
bottom.set_title("Delivered orders (by purchase month)")
bottom.tick_params(axis="x", rotation=90)
fig.tight_layout()
save(fig, "02_late_rate_by_month")

# %% 3. How late are the late orders?
bands = query(f"""select case when days_late <= 3  then '1-3 days'
                              when days_late <= 7  then '4-7 days'
                              when days_late <= 14 then '8-14 days'
                              else '15+ days' end as how_late,
                         count(*) as late_orders
                  from v_delivered
                  where is_late and purchase_month between '{first}' and '{last}'
                  group by 1 order by min(days_late)""")
bands["share"] = (bands.late_orders / bands.late_orders.sum()).round(3)
print(bands.to_string(index=False))

# %% 4. Promised vs actual delivery time: long promises, still missed
days = query(f"""select percentile_cont(0.5) within group (order by delivery_days) as median_delivery_days,
                        percentile_cont(0.5) within group (order by promised_days) as median_promised_days,
                        round(avg(delivery_days), 1) as avg_delivery_days,
                        round(avg(promised_days), 1) as avg_promised_days
                 from v_delivered where purchase_month between '{first}' and '{last}'""")
print(days)

fig, ax = plt.subplots(figsize=(10, 4))
ax.plot(monthly.purchase_month, monthly.avg_promised_days, color=SERIES[0], label="Promised days (average)")
ax.plot(monthly.purchase_month, monthly.avg_delivery_days, color=SERIES[1], label="Actual delivery days (average)")
ax.set_ylabel("Days from purchase")
ax.set_title("We promise about 24 days and deliver in about 12, yet the late spikes still happen")
ax.tick_params(axis="x", rotation=90)
ax.legend()
fig.tight_layout()
save(fig, "02_promised_vs_actual")
