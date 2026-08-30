-- NOTE: This model now de-duplicates active customers before joining to prevent
-- revenue inflation when a customer dimension has more than one active row
-- (e.g. an SCD Type-2 fan-out bug where both old and new rows are marked active).
-- The original model's LEFT JOIN could silently multiply order rows — now fixed
-- with a CTE that keeps only one row per customer_id.

with completed_orders as (
    select *
    from {{ ref('stg_orders') }}
    where status = 'completed'
),

-- De-duplicate: if the dimension has multiple active rows for the same customer
-- (SCD fanout bug), pick only one to prevent revenue inflation.
active_customers as (
    select
        customer_id,
        country,
        tier,
        is_active,
        valid_from,
        valid_to,
        row_number() over (
            partition by customer_id
            order by valid_from desc nulls last
        ) as rn
    from {{ ref('stg_customers') }}
    where is_active = true
),

deduplicated_customers as (
    select * from active_customers where rn = 1
)

select
    o.order_date,
    count(*) as completed_order_rows,
    sum(o.amount_usd) as daily_revenue
from completed_orders o
left join deduplicated_customers c
    on o.customer_id = c.customer_id
group by 1
order by 1
