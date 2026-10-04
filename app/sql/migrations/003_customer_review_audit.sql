ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS customer_id TEXT;
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS review_mode TEXT
    CHECK (review_mode IN ('deterministic', 'deepseek'));
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS review_status TEXT
    CHECK (review_status IN ('started', 'succeeded', 'partial_success', 'failed'));
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS finished_at TIMESTAMPTZ;
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS elapsed_ms BIGINT CHECK (elapsed_ms >= 0);
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS review_metadata JSONB NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(review_metadata) = 'object');
CREATE UNIQUE INDEX IF NOT EXISTS idx_audit_review_request
    ON audit_logs(request_id) WHERE review_mode IS NOT NULL;
