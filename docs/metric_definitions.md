# Metric definitions

Every number in this project uses one of these definitions: what is counted, out of what, and where
the logic lives. Analysis window: orders purchased Jan-2017 to Aug-2018 (`config/settings.yaml`).

## Orders and delivery

| Metric | Definition | Where |
|---|---|---|
| Delivered order | `order_status = 'delivered'` with a delivery date (8 delivered orders have none and are left out) | `v_delivered` |
| Promised date | `order_estimated_delivery_date`: the date shown to the customer at checkout | `orders` |
| **Late** | Delivered on a calendar day after the promised date | `v_delivered.is_late` |
| **Late rate** | Late delivered orders ÷ all delivered orders, by purchase month | `report_monthly.late_rate` |
| Days late | Delivered date − promised date (below 0 = early) | `v_delivered.days_late` |
| Delivery days / promised days | Days from the purchase date to the delivered date / to the promised date | `v_delivered` |
| Seller handed over late | The parcel reached the carrier after the seller's `shipping_limit_date` | `v_delivered.seller_late` |
| Days to hand over / with the carrier | Purchase → carrier pickup / carrier pickup → delivery. Not used for 189 orders with impossible timestamps | `v_delivered` |
| Route | Seller state > customer state, using the seller of item 1 (1.3% of orders have 2+ sellers) | `v_delivered.route` |

## Customers and reviews

| Metric | Definition | Where |
|---|---|---|
| Review score | 1-5 stars. 547 orders have 2+ reviews: the latest answer is used | `v_order_review` |
| **Bad review** | 1 or 2 stars | `report_late_bands` |
| Customer | `customer_unique_id` (one per person). `customer_id` is new for every order | `customers` |
| Came back | A new, not canceled order placed at least 1 day and at most 180 days after the first order. Orders minutes apart are one shopping trip | notebook 03 |
| 95% confidence interval | Wilson interval for rates (SQL functions `wilson_low` / `wilson_high`); Newcombe interval for a difference of two rates | `03_views.sql`, notebook 03 |

## Actions

| Metric | Definition | Where |
|---|---|---|
| Watchlist seller | 30+ delivered orders and 20%+ of them handed over late | notebook 05 |
| Problem state | 500+ orders in 2017 and late on more than 8% of them (chosen on 2017, checked on 2018) | notebook 05 |
| Late orders avoided | 2018 late orders under today's rules − 2018 late orders under the change | `report_promise_buffer`, `report_impact` |
| Bad reviews avoided | Late orders avoided × (bad-review share late − on time). An assumption: an avoided late order gets the on-time review rate | `report_impact` |
