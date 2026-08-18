select
  account_id,
  customer_id,
  opened_date,
  lower(account_status) as account_status,
  credit_limit,
  batch_id,
  source_sha256,
  loaded_at
from {{ source('governai_raw', 'accounts') }}
