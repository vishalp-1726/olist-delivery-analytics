# %% [markdown]
# # 04 - Q3: Where do late deliveries come from? Seller or carrier, which states and routes, and why the spikes?

# %% setup
import sys
from pathlib import Path

project = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(project))

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

from src.config import SETTINGS
from src.db import query, write_table
from src.style import apply_style, save, SERIES, INK_2

apply_style()
pd.set_option("display.width", 150)
pd.set_option("display.max_columns", 20)
first, last = SETTINGS["analysis"]["first_month"], SETTINGS["analysis"]["last_month"]

# %% 1. Seller side or carrier side?
# The seller must hand the parcel to the carrier by the shipping limit date (from order_items)
handover = query("select * from report_handover")
print(handover.to_string(index=False))

late = query(f"""select seller_late, count(*) as late_orders
                 from v_delivered
                 where is_late and seller_late is not null and purchase_month between '{first}' and '{last}'
                 group by 1""")
seller_share = late.loc[late.seller_late, "late_orders"].sum() / late.late_orders.sum()
print(f"late orders where the seller handed over late: {seller_share:.1%}; the rest ({1 - seller_share:.1%}) "
      "were handed over on time and got delayed with the carrier")

# %% 2. Where does the time go? Days to hand over vs days with the carrier, late vs on-time orders
split = query(f"""select case when is_late then 'Late' else 'On time' end as delivery,
                         round(avg(days_to_handover), 1) as avg_days_to_handover,
                         round(avg(days_with_carrier), 1) as avg_days_with_carrier
                  from v_delivered
                  where days_with_carrier is not null and purchase_month between '{first}' and '{last}'
                  group by 1 order by 1 desc""")
print(split.to_string(index=False))
write_table(split, "report_time_split")

fig, ax = plt.subplots(figsize=(8, 3.2))
ax.barh(split.delivery, split.avg_days_to_handover, color=SERIES[3], label="Seller: days to hand over")
ax.barh(split.delivery, split.avg_days_with_carrier, left=split.avg_days_to_handover, color=SERIES[0],
        label="Carrier: days in transit")
for i, row in split.iterrows():
    total = row.avg_days_to_handover + row.avg_days_with_carrier
    ax.annotate(f"{total:.0f} days", (total, i), xytext=(5, 0), textcoords="offset points", va="center", fontsize=9)
ax.set_xlabel("Average days from purchase to delivery")
ax.set_title("Late orders lose most of their time with the carrier, not the seller")
ax.margins(x=0.12)
ax.legend(loc="lower right", fontsize=8)
fig.tight_layout()
save(fig, "04_seller_vs_carrier")

# %% 3. Which customer states? The same states are late in both years
states = query("select * from report_states")
print(states.head(15).to_string(index=False))

by_year = query(f"""select customer_state, substr(purchase_month, 1, 4) as year,
                           count(*) as orders, round(avg(is_late::int), 4) as late_rate
                    from v_delivered where purchase_month between '{first}' and '{last}'
                    group by 1, 2""")
by_year = by_year.pivot(index="customer_state", columns="year", values=["orders", "late_rate"])
print(by_year[by_year[("orders", "2017")] >= 500].sort_values(("late_rate", "2017"), ascending=False))

top = states.head(15).sort_values("late_rate")
fig, ax = plt.subplots(figsize=(8, 5))
ax.errorbar(top.late_rate, top.customer_state, xerr=[top.late_rate - top.ci_low, top.ci_high - top.late_rate],
            fmt="o", color=SERIES[1], capsize=3)
overall = states.late_orders.sum() / states.orders.sum()
ax.axvline(overall, color=INK_2, linestyle="--", linewidth=1)
ax.set_yticks(range(len(top)), [f"{s} (n={n:,})" for s, n in zip(top.customer_state, top.orders)], fontsize=8)
ax.xaxis.set_major_formatter(mtick.PercentFormatter(1, decimals=0))
ax.set_title("Late rate by customer state, 15 biggest states (95% CI); dashed = all orders")
fig.tight_layout()
save(fig, "04_late_by_state")

# %% 4. Which routes create the most late orders?
routes = query("select * from report_routes")
print(routes.head(12).to_string(index=False))
print("same state vs different state:")
print(query(f"""select same_state, count(*) as orders, round(avg(is_late::int), 4) as late_rate
                from v_delivered where purchase_month between '{first}' and '{last}' group by 1"""))

# %% 5. The spikes (Nov-2017, Feb-Mar 2018): seller or carrier?
spikes = query(f"""select purchase_month,
                          round(avg(is_late::int), 4)           as late_rate,
                          round(avg(seller_late::int), 4)       as seller_late_rate,
                          round(avg(days_to_handover), 1)       as avg_days_to_handover,
                          round(avg(days_with_carrier), 1)      as avg_days_with_carrier
                   from v_delivered
                   where purchase_month between '{first}' and '{last}'
                   group by 1 order by 1""")
print(spikes.to_string(index=False))
write_table(spikes, "report_spikes")

fig, ax = plt.subplots(figsize=(10, 4))
ax.plot(spikes.purchase_month, spikes.avg_days_with_carrier, color=SERIES[0], marker="o", markersize=3,
        label="Days with the carrier")
ax.plot(spikes.purchase_month, spikes.avg_days_to_handover, color=SERIES[3], marker="o", markersize=3,
        label="Days to hand over (seller)")
ax.set_ylabel("Average days")
ax.set_title("In the spike months the carrier slowed down; sellers did not")
ax.tick_params(axis="x", rotation=90)
ax.legend()
fig.tight_layout()
save(fig, "04_spikes_carrier_vs_seller")

# which states were hit hardest in Feb-Mar 2018?
print(query("""select customer_state, count(*) as orders, round(avg(is_late::int), 4) as late_rate
               from v_delivered where purchase_month in ('2018-02', '2018-03')
               group by 1 order by orders desc limit 8""").to_string(index=False))
