select
  transactions.transaction_id,
  transactions.account_id,
  transactions.transaction_ts,
  transactions.transaction_date,
  transactions.transaction_month,
  transactions.amount,
  transactions.merchant_category,
  transactions.channel,
  iff(transactions.country_code <> 'US', true, false) as is_cross_border,
  transactions.is_fraud,
  transactions.confirmed_loss,
  transactions.batch_id,
  transactions.source_sha256
from {{ ref('stg_transactions') }} as transactions
inner join {{ ref('dim_account') }} as accounts
  on transactions.account_id = accounts.account_id
