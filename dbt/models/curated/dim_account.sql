select
  accounts.account_id,
  customers.customer_token,
  accounts.opened_date,
  accounts.account_status,
  accounts.credit_limit
from {{ ref('stg_accounts') }} as accounts
inner join {{ ref('dim_customer') }} as customers
  on accounts.customer_id = customers.customer_id
