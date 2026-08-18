with anchor as (
  select max(transaction_date) as as_of_date
  from {{ ref('fct_card_transactions') }}
)

select
  transactions.account_id,
  anchor.as_of_date,
  count(*) as transaction_count_30d,
  round(avg(transactions.amount), 2) as average_amount_30d,
  round(avg(iff(transactions.is_cross_border, 1, 0)), 4) as cross_border_rate_30d,
  round(sum(transactions.confirmed_loss), 2) as confirmed_loss_30d
from {{ ref('fct_card_transactions') }} as transactions
cross join anchor
where transactions.transaction_date between dateadd(day, -29, anchor.as_of_date) and anchor.as_of_date
group by transactions.account_id, anchor.as_of_date
