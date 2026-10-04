WITH params AS (
    SELECT TIMESTAMPTZ '2026-10-01 00:00:00+08' AS as_of,
           20 AS minimum_transactions
)
SELECT c.customer_id, c.name, c.kyc_status, COUNT(*) AS transaction_count,
       SUM(t.amount) AS transaction_total_sgd
FROM customers c
JOIN accounts a ON a.customer_id = c.customer_id
JOIN transactions t ON t.account_id = a.account_id
CROSS JOIN params p
WHERE c.kyc_status = 'incomplete'
  AND t.transaction_time >= p.as_of - INTERVAL '30 days'
  AND t.transaction_time < p.as_of AND t.currency = 'SGD'
GROUP BY c.customer_id, c.name, c.kyc_status, p.minimum_transactions
HAVING COUNT(*) >= p.minimum_transactions
ORDER BY c.customer_id;
