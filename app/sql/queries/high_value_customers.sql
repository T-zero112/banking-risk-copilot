-- Demo threshold, SGD only; window is [as_of - 30 days, as_of).
WITH params AS (
    SELECT TIMESTAMPTZ '2026-10-01 00:00:00+08' AS as_of,
           10000::numeric AS threshold
)
SELECT c.customer_id, c.name, COUNT(*) AS high_value_count,
       SUM(t.amount) AS high_value_total_sgd
FROM customers c
JOIN accounts a ON a.customer_id = c.customer_id
JOIN transactions t ON t.account_id = a.account_id
CROSS JOIN params p
WHERE t.transaction_time >= p.as_of - INTERVAL '30 days'
  AND t.transaction_time < p.as_of
  AND t.currency = 'SGD' AND t.amount >= p.threshold
GROUP BY c.customer_id, c.name
ORDER BY c.customer_id;
