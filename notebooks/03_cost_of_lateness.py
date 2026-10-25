# %% [markdown]
# # 03 - Q2: What does a late delivery cost us?
# 1) reviews: what customers say after a late order   2) repeat buying: do they come back less?

# %% setup
import sys
from pathlib import Path

project = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(project))

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd
from statsmodels.stats.proportion import confint_proportions_2indep, proportions_ztest

from src.config import SETTINGS
from src.db import query, write_table
from src.style import apply_style, save, SERIES, INK_2

apply_style()
pd.set_option("display.width", 150)
pd.set_option("display.max_columns", 20)
first, last = SETTINGS["analysis"]["first_month"], SETTINGS["analysis"]["last_month"]

# %% 1. Reviews: on time vs late (bad review = 1 or 2 stars)
reviews = query(f"""select case when is_late then 'Late' else 'On time' end as delivery,
                           count(*) as orders,
                           round(avg(review_score), 2) as avg_review,
                           round(avg((review_score <= 2)::int), 4) as bad_review_share
                    from v_delivered
                    where review_score is not null and purchase_month between '{first}' and '{last}'
                    group by 1 order by 1 desc""")
print(reviews.to_string(index=False))
write_table(reviews, "report_review_summary")

# %% 2. The later the order, the worse the review (95% confidence intervals from 04_reports.sql)
bands = query("select * from report_late_bands")
print(bands.to_string(index=False))

fig, ax = plt.subplots(figsize=(9, 4.2))
labels = [band[2:] for band in bands.late_band]                   # drop the "0 " sort prefix
ax.bar(labels, bands.bad_review_share, color=[SERIES[0]] + [SERIES[1]] * 4, width=0.6)
ax.errorbar(labels, bands.bad_review_share,
            yerr=[bands.bad_review_share - bands.ci_low, bands.ci_high - bands.bad_review_share],
            fmt="none", color=INK_2, capsize=4)
ax.bar_label(ax.containers[0], fmt="{:.0%}", padding=6, fontsize=9)
ax.yaxis.set_major_formatter(mtick.PercentFormatter(1, decimals=0))
ax.set_ylabel("Share of 1-2 star reviews")
ax.set_title("One late delivery turns a 9% bad-review rate into 32-80%")
fig.tight_layout()
save(fig, "03_reviews_by_days_late")

# %% 3. Repeat buying: does a late first order make a customer less likely to buy again?
# Fair comparison: first orders up to Mar-2018 only, so every customer has 180 days of follow-up in the data.
# "Came back" = a new order at least 1 day after the first: orders minutes apart are one shopping trip split in two.
window = SETTINGS["repeat"]["window_days"]
customers = query(f"""
    with orders_by_person as (
        select c.customer_unique_id, o.order_id, o.order_purchase_timestamp as purchased_at,
               row_number() over (partition by c.customer_unique_id
                                  order by o.order_purchase_timestamp, o.order_id) as order_no
        from orders o
        join customers c using (customer_id)
        where o.order_status <> 'canceled'
    ),
    first_orders as (
        select p.customer_unique_id, p.purchased_at, d.purchase_month, d.is_late
        from orders_by_person p
        join v_delivered d using (order_id)
        where p.order_no = 1
          and d.purchase_month between '{first}' and '{SETTINGS["repeat"]["last_first_order"]}'
    ),
    next_orders as (
        select distinct on (f.customer_unique_id)
               f.customer_unique_id, p.purchased_at as next_at, v.order_value as next_value
        from first_orders f
        join orders_by_person p using (customer_unique_id)
        left join v_order_value v on v.order_id = p.order_id
        where p.purchased_at >= f.purchased_at + interval '1 day'
        order by f.customer_unique_id, p.purchased_at, p.order_id
    )
    select f.*, n.next_value,
           n.next_at is not null and n.next_at <= f.purchased_at + interval '{window} days' as came_back
    from first_orders f
    left join next_orders n using (customer_unique_id)
""")
late, on_time = customers[customers.is_late], customers[~customers.is_late]
print(f"customers: {len(customers):,}; came back within {window} days: {customers.came_back.mean():.2%}")
print(f"after a late first order {late.came_back.mean():.2%} vs on time {on_time.came_back.mean():.2%}")

z, p = proportions_ztest([late.came_back.sum(), on_time.came_back.sum()], [len(late), len(on_time)])
low, high = confint_proportions_2indep(late.came_back.sum(), len(late), on_time.came_back.sum(), len(on_time),
                                       compare="diff", method="newcomb")
print(f"difference {(late.came_back.mean() - on_time.came_back.mean()) * 100:+.2f} points, "
      f"95% CI {low * 100:+.2f} to {high * 100:+.2f}, p = {p:.3f}")

# late orders bunch up in Nov-2017 and Feb-Mar 2018, so also compare with on-time customers of the same month
same_month_rate = on_time.groupby("purchase_month").came_back.mean()
expected = late.purchase_month.map(same_month_rate).mean()
print(f"late customers if they behaved like on-time customers of the same month: {expected:.2%} "
      f"(actual {late.came_back.mean():.2%})")

repeat = pd.DataFrame({
    "first_order": ["Late", "On time"],
    "customers": [len(late), len(on_time)],
    "came_back": [int(late.came_back.sum()), int(on_time.came_back.sum())],
    "rate": [late.came_back.mean(), on_time.came_back.mean()],
})
repeat["diff_ci_low"], repeat["diff_ci_high"], repeat["p_value"] = low, high, p
write_table(repeat.round(4), "report_repeat")

# %% 4. The most it could be worth: lost repeat revenue at the edge of the 95% interval
# if the true effect is the worst end of the interval: how many return orders are lost, and what are they worth?
next_value = customers[customers.came_back].next_value.mean()
worst_case_lost = -low * len(late)                     # low = the most negative difference in the interval
months = customers.purchase_month.nunique()
per_year = worst_case_lost * next_value * 12 / months
print(f"average return order R$ {next_value:,.0f}; worst case {worst_case_lost:.0f} lost return orders "
      f"in {months} months = R$ {worst_case_lost * next_value:,.0f} (about R$ {per_year:,.0f} a year)")
value = pd.DataFrame([{"late_first_orders": len(late),
                       "months": months,
                       "worst_case_lost_orders": round(worst_case_lost, 1),
                       "avg_return_order": round(float(next_value), 2),
                       "worst_case_value_per_year": round(float(per_year), 0)}])
write_table(value, "report_repeat_value")
