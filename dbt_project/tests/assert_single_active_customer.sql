-- Singular test: assert that no customer_id has more than one active row
-- in the stg_customers staging model.
--
-- If this test returns any rows, it means we have a SCD fan-out bug that will
-- inflate revenue in fct_daily_revenue whenever those customers have orders.
-- The test FAILS (non-zero rows returned) if duplicates exist.

select
    customer_id,
    count(*) as active_row_count
from {{ ref('stg_customers') }}
where is_active = true
group by customer_id
having count(*) > 1
