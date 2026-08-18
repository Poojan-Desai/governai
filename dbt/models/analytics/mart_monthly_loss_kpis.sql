select
  transaction_month as month,
  count(*) as transaction_count,
  round(sum(amount), 2) as transaction_value,
  round(sum(confirmed_loss), 2) as confirmed_loss,
  round(div0(sum(confirmed_loss) * 10000, sum(amount)), 2) as loss_rate_bps,
  count_if(confirmed_loss > 0) as affected_transactions,
  max(transaction_ts) as data_through,
  max(loaded_at) as source_loaded_at
from {{ ref('stg_transactions') }}
group by transaction_month
