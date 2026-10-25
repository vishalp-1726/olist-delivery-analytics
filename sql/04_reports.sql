-- 04_reports.sql
-- Small summary tables for the charts and the Tableau dashboard (totals only, no customer IDs).
-- Each table is dropped and built again, so it always matches the data.
-- All tables use the analysis window Jan-2017 to Aug-2018 (the same months as in settings.yaml).

-- 1. Month by month: how many orders were late, and what customers said
drop table if exists report_monthly;
create table report_monthly as
select purchase_month,
       count(*)                                                       as delivered_orders,
       count(*) filter (where is_late)                                as late_orders,
       round(avg(is_late::int), 4)                                    as late_rate,
       round(avg(review_score), 2)                                    as avg_review,
       round(avg((review_score <= 2)::int), 4)                        as bad_review_share,
       round(avg(delivery_days), 1)                                   as avg_delivery_days,
       round(avg(promised_days), 1)                                   as avg_promised_days
from v_delivered
where purchase_month between '2017-01' and '2018-08'
group by purchase_month
order by purchase_month;

-- 2. Reviews by how late the order was (1-2 stars = a bad review)
drop table if exists report_late_bands;
create table report_late_bands as
with banded as (
    select case when days_late <= 0  then '0 on time or early'
                when days_late <= 3  then '1 1-3 days late'
                when days_late <= 7  then '2 4-7 days late'
                when days_late <= 14 then '3 8-14 days late'
                else '4 15+ days late' end            as late_band,
           review_score
    from v_delivered
    where review_score is not null and purchase_month between '2017-01' and '2018-08'
)
select late_band,
       count(*)                                        as orders,
       round(avg(review_score), 2)                     as avg_review,
       count(*) filter (where review_score <= 2)       as bad_reviews,
       round(avg((review_score <= 2)::int), 4)         as bad_review_share,
       wilson_low(count(*) filter (where review_score <= 2), count(*))  as ci_low,
       wilson_high(count(*) filter (where review_score <= 2), count(*)) as ci_high
from banded
group by late_band
order by late_band;

-- 3. Late rate by customer state, with a 95% confidence interval
drop table if exists report_states;
create table report_states as
select customer_state,
       count(*)                                        as orders,
       count(*) filter (where is_late)                 as late_orders,
       round(avg(is_late::int), 4)                     as late_rate,
       wilson_low(count(*) filter (where is_late), count(*))  as ci_low,
       wilson_high(count(*) filter (where is_late), count(*)) as ci_high,
       round(avg(delivery_days), 1)                    as avg_delivery_days,
       round(avg(promised_days), 1)                    as avg_promised_days
from v_delivered
where purchase_month between '2017-01' and '2018-08'
group by customer_state
order by orders desc;

-- 4. Late rate by route (seller state > customer state), routes with at least 300 orders
drop table if exists report_routes;
create table report_routes as
select route, seller_state, customer_state, same_state,
       count(*)                                        as orders,
       count(*) filter (where is_late)                 as late_orders,
       round(avg(is_late::int), 4)                     as late_rate,
       wilson_low(count(*) filter (where is_late), count(*))  as ci_low,
       wilson_high(count(*) filter (where is_late), count(*)) as ci_high
from v_delivered
where purchase_month between '2017-01' and '2018-08'
group by route, seller_state, customer_state, same_state
having count(*) >= 300
order by late_orders desc;

-- 5. Seller side vs carrier side: is the order late more often when the seller handed over late?
drop table if exists report_handover;
create table report_handover as
select case when seller_late then 'Seller handed over late' else 'Seller handed over on time' end as handover,
       count(*)                                        as orders,
       count(*) filter (where is_late)                 as late_orders,
       round(avg(is_late::int), 4)                     as late_rate,
       percentile_cont(0.5) within group (order by days_to_handover)  as median_days_to_handover,
       percentile_cont(0.5) within group (order by days_with_carrier) as median_days_with_carrier
from v_delivered
where seller_late is not null and purchase_month between '2017-01' and '2018-08'
group by 1
order by 1;
