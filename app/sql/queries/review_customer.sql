-- Fixed, parameterized snapshot query; no user-provided SQL is executed.
WITH params AS (SELECT %(customer_id)s::text AS customer_id, %(as_of)s::timestamptz AS as_of)
SELECT c.customer_id, c.kyc_status, c.kyc_last_review_date,
       c.due_diligence_level, r.aml_risk_score, r.score_date,
       (SELECT COUNT(*) FROM alerts al WHERE al.customer_id=c.customer_id
        AND al.created_at < p.as_of
        AND (al.resolved_at IS NULL OR al.resolved_at >= p.as_of)) AS unresolved_alert_count
FROM customers c CROSS JOIN params p
LEFT JOIN LATERAL (
    SELECT aml_risk_score, score_date FROM risk_scores
    WHERE customer_id=c.customer_id
      AND score_date < (p.as_of AT TIME ZONE 'Asia/Singapore')::date
    ORDER BY score_date DESC LIMIT 1
) r ON TRUE
WHERE c.customer_id=p.customer_id;
