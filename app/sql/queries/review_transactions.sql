SELECT t.transaction_id, t.account_id, t.transaction_time, t.amount,
       t.currency, t.transaction_type, t.direction, t.is_cross_border
FROM transactions t JOIN accounts a ON a.account_id=t.account_id
WHERE a.customer_id=%(customer_id)s
  AND t.currency='SGD'
  AND t.transaction_time >= %(as_of)s::timestamptz - INTERVAL '30 days'
  AND t.transaction_time < %(as_of)s::timestamptz
ORDER BY t.transaction_time, t.transaction_id
LIMIT 201;
