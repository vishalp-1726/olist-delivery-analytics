-- 03_views.sql
-- Shared definitions, so notebooks, reports and Tableau all use the same logic.

-- Wilson 95% confidence interval for a rate (successes out of n). Better than the simple formula for small rates.
create or replace function wilson_low(successes numeric, n numeric) returns numeric as $$
    select round(((successes / n + 1.96^2 / (2 * n))
                  - 1.96 * sqrt((successes / n) * (1 - successes / n) / n + 1.96^2 / (4 * n^2)))
                 / (1 + 1.96^2 / n), 4)
$$ language sql immutable;

create or replace function wilson_high(successes numeric, n numeric) returns numeric as $$
    select round(((successes / n + 1.96^2 / (2 * n))
                  + 1.96 * sqrt((successes / n) * (1 - successes / n) / n + 1.96^2 / (4 * n^2)))
                 / (1 + 1.96^2 / n), 4)
$$ language sql immutable;

-- one review per order: 547 orders have more than one review, keep the latest answer
create or replace view v_order_review as
select distinct on (order_id) order_id, review_score
from order_reviews
order by order_id, review_answer_timestamp desc;

-- one row per order from the items: value, freight, number of sellers, the seller's handover deadline.
-- 1.3% of orders have items from 2+ sellers: the seller of item 1 is used.
create or replace view v_order_value as
select order_id,
       count(*)                                         as items,
       count(distinct seller_id)                        as sellers,
       min(seller_id) filter (where order_item_id = 1)  as seller_id,
       sum(price)                                       as order_value,
       sum(freight_value)                               as freight,
       max(shipping_limit_date)                         as handover_deadline
from order_items
group by order_id;

-- v_delivered: every delivered order with the columns almost every analysis needs.
-- All day counts are whole calendar days.
create or replace view v_delivered as
select o.order_id,
       o.order_purchase_timestamp                                            as purchased_at,
       to_char(o.order_purchase_timestamp, 'YYYY-MM')                        as purchase_month,
       c.customer_unique_id,
       c.customer_state,
       v.seller_id,
       s.seller_state,
       s.seller_state || ' > ' || c.customer_state                            as route,
       s.seller_state = c.customer_state                                     as same_state,
       v.order_value,
       v.freight,
       o.order_delivered_customer_date::date - o.order_purchase_timestamp::date        as delivery_days,
       o.order_estimated_delivery_date::date - o.order_purchase_timestamp::date        as promised_days,
       o.order_delivered_customer_date::date - o.order_estimated_delivery_date::date   as days_late,   -- below 0 = early
       o.order_delivered_customer_date::date > o.order_estimated_delivery_date::date   as is_late,
       -- seller side: did the seller hand over to the carrier after the deadline?
       case when not o.bad_timestamps then o.order_delivered_carrier_date > v.handover_deadline end as seller_late,
       case when not o.bad_timestamps
            then o.order_delivered_carrier_date::date - o.order_purchase_timestamp::date end         as days_to_handover,
       case when not o.bad_timestamps
            then o.order_delivered_customer_date::date - o.order_delivered_carrier_date::date end    as days_with_carrier,
       r.review_score
from orders o
join customers c using (customer_id)
join v_order_value v using (order_id)
join sellers s on s.seller_id = v.seller_id
left join v_order_review r using (order_id)
where o.order_status = 'delivered'
  and o.order_delivered_customer_date is not null;     -- 8 "delivered" orders have no delivery date
