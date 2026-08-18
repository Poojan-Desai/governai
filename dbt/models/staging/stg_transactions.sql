select
  transaction_id,
  account_id,
  transaction_ts,
  to_date(transaction_ts) as transaction_date,
  date_trunc('month', transaction_ts)::date as transaction_month,
  amount,
  lower(merchant_category) as merchant_category,
  lower(channel) as channel,
  upper(country_code) as country_code,
  is_fraud,
  confirmed_loss,
  batch_id,
  source_sha256,
  loaded_at
from {{ source('governai_raw', 'transactions') }}
