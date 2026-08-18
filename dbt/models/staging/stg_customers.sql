select
  customer_id,
  trim(full_name) as full_name,
  lower(trim(email)) as email,
  phone,
  upper(state) as state,
  customer_since,
  lower(segment) as segment,
  batch_id,
  source_sha256,
  loaded_at
from {{ source('governai_raw', 'customers') }}
