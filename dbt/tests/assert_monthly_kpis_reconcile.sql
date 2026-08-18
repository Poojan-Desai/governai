with source_totals as (
  select
    count(*) as transaction_count,
    round(sum(amount), 2) as transaction_value,
    round(sum(confirmed_loss), 2) as confirmed_loss
  from {{ ref('stg_transactions') }}
),
mart_totals as (
  select
    sum(transaction_count) as transaction_count,
    round(sum(transaction_value), 2) as transaction_value,
    round(sum(confirmed_loss), 2) as confirmed_loss
  from {{ ref('mart_monthly_loss_kpis') }}
)
select source_totals.*
from source_totals
cross join mart_totals
where source_totals.transaction_count <> mart_totals.transaction_count
   or source_totals.transaction_value <> mart_totals.transaction_value
   or source_totals.confirmed_loss <> mart_totals.confirmed_loss
