-- Structured evidence only; policy retrieval and citations come in a later step.
WITH params AS (
    SELECT TIMESTAMPTZ '2026-10-01 00:00:00+08' AS as_of,
           'C003'::text AS customer_id
), activity AS (
    SELECT a.customer_id, COUNT(*) AS transaction_count,
           SUM(t.amount) AS total_sgd,
           SUM(t.amount) FILTER (WHERE t.direction = 'inbound') AS inbound_sgd,
           SUM(t.amount) FILTER (WHERE t.direction = 'outbound') AS outbound_sgd,
           COUNT(*) FILTER (WHERE t.is_cross_border) AS cross_border_count
    FROM accounts a JOIN transactions t ON t.account_id = a.account_id
    CROSS JOIN params p
    WHERE a.customer_id = p.customer_id AND t.currency = 'SGD'
      AND t.transaction_time >= p.as_of - INTERVAL '30 days'
      AND t.transaction_time < p.as_of
    GROUP BY a.customer_id
)
SELECT c.customer_id, c.name, c.kyc_status, c.kyc_last_review_date,
       c.due_diligence_level, r.aml_risk_score, r.score_date,
       COALESCE(a.transaction_count, 0) AS transaction_count,
       COALESCE(a.total_sgd, 0) AS total_sgd,
       COALESCE(a.inbound_sgd, 0) AS inbound_sgd,
       COALESCE(a.outbound_sgd, 0) AS outbound_sgd,
       COALESCE(a.cross_border_count, 0) AS cross_border_count,
       (SELECT COUNT(*) FROM alerts al
        WHERE al.customer_id = c.customer_id AND al.created_at < p.as_of
          AND (al.resolved_at IS NULL OR al.resolved_at >= p.as_of)) AS unresolved_alert_count
FROM customers c CROSS JOIN params p
LEFT JOIN activity a ON a.customer_id = c.customer_id
LEFT JOIN LATERAL (
    SELECT rs.aml_risk_score, rs.score_date FROM risk_scores rs
    WHERE rs.customer_id = c.customer_id
      AND rs.score_date < (p.as_of AT TIME ZONE 'Asia/Singapore')::date
    ORDER BY rs.score_date DESC LIMIT 1
) r ON TRUE
WHERE c.customer_id = p.customer_id;
