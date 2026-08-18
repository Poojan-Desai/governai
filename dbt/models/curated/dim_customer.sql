select
  sha2('governai-snowflake-v1:' || customer_id, 256) as customer_token,
  customer_id,
  regexp_replace(email, '(^.).*(@.*$)', '\\1***\\2') as masked_email,
  state,
  segment,
  customer_since
from {{ ref('stg_customers') }}
