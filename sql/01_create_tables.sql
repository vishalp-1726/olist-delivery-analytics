-- 01_create_tables.sql
-- One table per Kaggle file used, plus 2 small log tables.
-- Column names as in the files, including the source's own spelling ("lenght"). Safe to re-run.

create table if not exists customers (
    customer_id               text primary key,   -- one per order (a new id every time)
    customer_unique_id        text,               -- one per person: used for repeat buying
    customer_zip_code_prefix  text,               -- text: keeps the leading zeros
    customer_city             text,
    customer_state            text
);

create table if not exists sellers (
    seller_id                 text primary key,
    seller_zip_code_prefix    text,
    seller_city               text,               -- messy spellings ("sao paulo / sao paulo"); only the state is used
    seller_state              text
);

create table if not exists products (
    product_id                  text primary key,
    product_category_name       text,             -- Portuguese; 610 products have none
    product_name_lenght         int,
    product_description_lenght  int,
    product_photos_qty          int,
    product_weight_g            int,
    product_length_cm           int,
    product_height_cm           int,
    product_width_cm            int
);

create table if not exists category_translation (
    product_category_name          text primary key,
    product_category_name_english  text
);

create table if not exists orders (
    order_id                       text primary key,
    customer_id                    text references customers (customer_id),
    order_status                   text,          -- delivered, shipped, canceled, ...
    order_purchase_timestamp       timestamp,
    order_approved_at              timestamp,     -- payment approved
    order_delivered_carrier_date   timestamp,     -- seller handed the parcel to the carrier
    order_delivered_customer_date  timestamp,     -- customer received it
    order_estimated_delivery_date  timestamp      -- the date promised at checkout (always midnight)
);

-- one row per product in an order
create table if not exists order_items (
    order_id             text references orders (order_id),
    order_item_id        int,                     -- 1, 2, 3 ... within the order
    product_id           text,
    seller_id            text,
    shipping_limit_date  timestamp,               -- the seller must hand over to the carrier by this time
    price                numeric,                 -- R$
    freight_value        numeric,                 -- R$
    primary key (order_id, order_item_id)
);

create table if not exists order_reviews (
    review_id                text,                -- not unique: the same review id can cover several orders
    order_id                 text,
    review_score             int,                 -- 1 to 5 stars
    review_comment_title     text,
    review_comment_message   text,                -- Portuguese free text (not used)
    review_creation_date     timestamp,
    review_answer_timestamp  timestamp
);

-- log tables
create table if not exists load_log (           -- which files are already loaded
    file_name    text primary key,
    rows_loaded  bigint,
    loaded_at    timestamptz default now()
);

create table if not exists dq_results (          -- results of the data-quality checks
    check_name   text,
    severity     text,
    failed_rows  bigint,
    checked_at   timestamptz default now()
);

create index if not exists ix_items_seller  on order_items (seller_id);
create index if not exists ix_orders_cust   on orders (customer_id);
create index if not exists ix_reviews_order on order_reviews (order_id);
