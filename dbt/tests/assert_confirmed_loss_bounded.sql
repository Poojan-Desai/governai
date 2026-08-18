select transaction_id
from {{ ref('stg_transactions') }}
where confirmed_loss < 0 or confirmed_loss > amount
