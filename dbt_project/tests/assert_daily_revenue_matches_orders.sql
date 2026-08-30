-- Singular test: assert that daily_revenue in fct_daily_revenue matches
-- the raw sum of completed order amounts from stg_orders.
--
-- Any discrepancy here indicates a JOIN issue (fan-out inflation) or a
-- filter bug in the mart model. The test FAILS if max_abs_diff > 0.01.

with expected_revenue as (
    select
        order_date,
        sum(amount_usd) as expected_daily_revenue
    from {{ ref('stg_orders') }}
    where status = 'completed'
    group by order_date
),
actual_revenue as (
    select
        order_date,
        daily_revenue as actual_daily_revenue
    from {{ ref('fct_daily_revenue') }}
),
diff as (
    select
        e.order_date,
        e.expected_daily_revenue,
        a.actual_daily_revenue,
        abs(e.expected_daily_revenue - a.actual_daily_revenue) as abs_diff
    from expected_revenue e
    left join actual_revenue a using (order_date)
)
select *
from diff
where abs_diff > 0.01
   or actual_daily_revenue is null
