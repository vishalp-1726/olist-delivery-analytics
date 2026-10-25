-- 02_clean.sql
-- Fixes for the data problems that matter for this analysis (found in DBeaver, listed in notebook 01).
-- Problems are fixed or flagged, never hidden. Safe to re-run: each step only touches rows that still need it.

-- 1. Two product categories are missing from the translation file
insert into category_translation (product_category_name, product_category_name_english) values
    ('pc_gamer', 'pc_gamer'),
    ('portateis_cozinha_e_preparadores_de_alimentos', 'portable_kitchen_food_preparers')
on conflict (product_category_name) do nothing;

-- 2. 610 products have no category: give them one name, so they show up as one group in reports
update products set product_category_name = 'sem_categoria' where product_category_name is null;
insert into category_translation values ('sem_categoria', 'unknown')
on conflict (product_category_name) do nothing;

-- 3. Impossible timestamps: handed to the carrier before the order was placed, or delivered before
--    the carrier picked it up. These orders stay (their delivered and promised dates are fine),
--    but their handover and carrier times are not used.
alter table orders add column if not exists bad_timestamps boolean;
update orders
set bad_timestamps = coalesce(order_delivered_carrier_date < order_purchase_timestamp
                              or order_delivered_customer_date < order_delivered_carrier_date, false)
where bad_timestamps is null;          -- a missing date is not a problem

-- 4. Fresh table statistics: without this the first run of 04_reports.sql took minutes instead of seconds
analyze;
