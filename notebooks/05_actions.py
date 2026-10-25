# %% [markdown]
# # 05 - Q4: What should Operations change, and what is each change worth?
# Each action is chosen on 2017 orders and checked on 2018 orders, so no fix is tested on the data used to pick it.
#   A. Seller watchlist: sellers who often hand over late -> Seller Ops works with them first
#   B. Extra promise days for the states that are late every year

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
from src.style import apply_style, save, SERIES

apply_style()
pd.set_option("display.width", 150)
pd.set_option("display.max_columns", 20)
first, last = SETTINGS["analysis"]["first_month"], SETTINGS["analysis"]["last_month"]
build, test = SETTINGS["promise"]["build_year"], SETTINGS["promise"]["test_year"]

orders = query(f"""select order_id, substr(purchase_month, 1, 4) as year, purchase_month, seller_id,
                          customer_state, delivery_days, promised_days, is_late, seller_late, review_score
                   from v_delivered
                   where purchase_month between '{first}' and '{last}'""")
build_orders = orders[orders.year == build]
test_orders = orders[orders.year == test]
print(f"{build} orders: {len(build_orders):,}   {test} orders (Jan-Aug): {len(test_orders):,}")

# how much one late order costs in reviews: bad-review share late minus on time (from notebook 03)
reviews = query("select * from report_review_summary").set_index("delivery")
extra_bad = reviews.loc["Late", "bad_review_share"] - reviews.loc["On time", "bad_review_share"]
print(f"a late order adds {extra_bad:.1%} chance of a 1-2 star review")

# %% A1. The watchlist, chosen on 2017: enough orders, and 20%+ of them handed over late
min_orders = SETTINGS["sellers"]["min_orders"]
cutoff = SETTINGS["sellers"]["watchlist_late_handover"]


def seller_table(df):
    has_handover = df[df.seller_late.notna()].astype({"seller_late": bool})
    t = has_handover.groupby("seller_id").agg(orders=("order_id", "size"),
                                              late_handover_rate=("seller_late", "mean"),
                                              late_orders=("is_late", "sum"))
    return t[t.orders >= min_orders]


sellers_2017 = seller_table(build_orders)
watchlist = sellers_2017[sellers_2017.late_handover_rate >= cutoff].index
print(f"sellers with {min_orders}+ orders in {build}: {len(sellers_2017)}; on the watchlist: {len(watchlist)}")

# %% A2. Did the same sellers keep handing over late in 2018? (if not, a watchlist is useless)
t = test_orders[test_orders.seller_late.notna()].astype({"seller_late": bool})
t["on_watchlist"] = t.seller_id.isin(watchlist)
check = t.groupby("on_watchlist").agg(orders=("order_id", "size"), late_handover_rate=("seller_late", "mean"),
                                      late_rate=("is_late", "mean"), late_orders=("is_late", "sum"))
print(check.round(4))

# what if watchlist sellers handed over on time in 2018?
# late rate of orders handed over late vs on time, all sellers, 2018
late_if_late_handover = t[t.seller_late].is_late.mean()
late_if_on_time = t[~t.seller_late].is_late.mean()
w_late_handovers = (t.on_watchlist & t.seller_late).sum()
seller_avoided = w_late_handovers * (late_if_late_handover - late_if_on_time)
print(f"{test}: {w_late_handovers} late handovers by watchlist sellers; late rate {late_if_late_handover:.1%} "
      f"when handed over late vs {late_if_on_time:.1%} on time -> about {seller_avoided:.0f} late orders avoided")

# %% A3. The list for Seller Ops: built on all months (the latest picture), worst first
sellers_now = seller_table(orders)
sellers_now = sellers_now[sellers_now.late_handover_rate >= cutoff].sort_values("late_orders", ascending=False)
seller_states = query("select seller_id, seller_state from sellers").set_index("seller_id")
sellers_now = sellers_now.join(seller_states).reset_index()
sellers_now["late_handover_rate"] = sellers_now.late_handover_rate.round(4)
print(f"current watchlist: {len(sellers_now)} sellers, {sellers_now.orders.sum():,} orders, "
      f"{sellers_now.late_orders.sum():,} late orders "
      f"({sellers_now.late_orders.sum() / orders.is_late.sum():.1%} of all late orders)")
print(sellers_now.head(10).to_string(index=False))
write_table(sellers_now, "report_seller_watchlist")

# %% B1. Problem states, chosen on 2017: 500+ orders and late on more than 8% of them
s2017 = build_orders.groupby("customer_state").agg(orders=("order_id", "size"), late_rate=("is_late", "mean"))
problem = s2017[(s2017.orders >= SETTINGS["promise"]["problem_state_min_orders"])
                & (s2017.late_rate > SETTINGS["promise"]["problem_state_late_rate"])]
problem_states = list(problem.index)
print("problem states:", problem_states)
print(problem.round(4))

in_problem = test_orders.customer_state.isin(problem_states)
print(f"{test}: problem states have {in_problem.mean():.1%} of orders and "
      f"{test_orders[test_orders.is_late].customer_state.isin(problem_states).mean():.1%} of late orders")

# %% B2. Add 2, 3, 5 or 7 days to the promise in those states only, and re-check every 2018 order
rows = []
for extra in [0] + SETTINGS["promise"]["buffer_days"]:
    promise = test_orders.promised_days + in_problem * extra
    late = test_orders.delivery_days > promise
    rows.append({"extra_days": extra,
                 "late_rate_problem_states": late[in_problem].mean(),
                 "late_rate_all": late.mean(),
                 "avg_promise_problem_states": promise[in_problem].mean(),
                 "avg_promise_all": promise.mean(),
                 "late_orders": int(late.sum()),
                 "late_orders_avoided": int(test_orders.is_late.sum() - late.sum())})
buffer = pd.DataFrame(rows)
buffer["bad_reviews_avoided"] = (buffer.late_orders_avoided * extra_bad).round(0)
print(buffer.round(4).to_string(index=False))
write_table(buffer.round(4), "report_promise_buffer")

fig, ax = plt.subplots(figsize=(8, 4.5))
ax.plot(buffer.avg_promise_problem_states, buffer.late_rate_problem_states, marker="o", color=SERIES[1])
for _, row in buffer.iterrows():
    ax.annotate(f"+{int(row.extra_days)} days", (row.avg_promise_problem_states, row.late_rate_problem_states),
                xytext=(6, 4), textcoords="offset points", fontsize=9)
ax.yaxis.set_major_formatter(mtick.PercentFormatter(1, decimals=0))
ax.set_xlabel(f"Average promised days in {', '.join(problem_states)} ({test} orders)")
ax.set_ylabel("Late rate in those states")
ax.set_title("More promise days in the problem states: fewer late orders, longer wait")
fig.tight_layout()
save(fig, "05_promise_buffer")

# %% C. The carrier: the biggest lever, but one we can only size, not test
# 72% of late orders were handed over on time (notebook 04), and the data has no carrier name.
# Size of the prize: if the problem states were late as often as the rest of the country.
rest_rate = test_orders[~in_problem].is_late.mean()
problem_rate = test_orders[in_problem].is_late.mean()
carrier_prize = in_problem.sum() * (problem_rate - rest_rate)
print(f"{test}: problem states {problem_rate:.1%} late vs rest of the country {rest_rate:.1%} -> "
      f"up to {carrier_prize:.0f} fewer late orders in Jan-Aug if the carrier matched the rest")

# %% D. The impact table (Jan-Aug 2018 orders). Bad reviews avoided assumes an avoided late order
# gets the on-time review rate: an assumption, and labelled as one.
state_list = ", ".join(problem_states)
pick = buffer[buffer.extra_days == 3].iloc[0]
promise_today = buffer.avg_promise_problem_states[0]
impact = pd.DataFrame([
    {"action": "A. Watchlist sellers hand over on time",
     "late_orders_avoided": round(seller_avoided),
     "bad_reviews_avoided": round(seller_avoided * extra_bad),
     "trade_off": f"Seller Ops time with {len(watchlist)} sellers"},
    {"action": f"B. +3 promise days in {state_list}",
     "late_orders_avoided": int(pick.late_orders_avoided),
     "bad_reviews_avoided": int(pick.bad_reviews_avoided),
     "trade_off": f"promise {pick.avg_promise_problem_states:.1f} days instead of {promise_today:.1f} in those states"},
    {"action": f"C. Carrier brings {state_list} to the rest-of-country late rate",
     "late_orders_avoided": round(carrier_prize),
     "bad_reviews_avoided": round(carrier_prize * extra_bad),
     "trade_off": "size of the prize, not a tested change: needs the carrier's data and agreement"},
])
impact["share_of_2018_late"] = (impact.late_orders_avoided / test_orders.is_late.sum()).round(3)
print(impact.to_string(index=False))
write_table(impact, "report_impact")
