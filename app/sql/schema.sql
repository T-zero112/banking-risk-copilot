-- Initial PostgreSQL schema for synthetic data, not an upgrade migration.
BEGIN;

CREATE TABLE customers (
    customer_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    customer_type TEXT NOT NULL CHECK (customer_type IN ('individual', 'corporate')),
    nationality TEXT CHECK (nationality ~ '^[A-Z]{2}$'),
    occupation TEXT,
    risk_level TEXT NOT NULL CHECK (risk_level IN ('low', 'medium', 'high')),
    kyc_status TEXT NOT NULL CHECK (kyc_status IN ('complete', 'incomplete', 'expired')),
    onboarding_date DATE NOT NULL,
    kyc_last_review_date DATE,
    due_diligence_level TEXT NOT NULL CHECK (due_diligence_level IN ('standard', 'enhanced')),
    CHECK (customer_type <> 'individual' OR nationality IS NOT NULL),
    CHECK (kyc_status <> 'complete' OR kyc_last_review_date IS NOT NULL),
    CHECK (kyc_last_review_date IS NULL OR kyc_last_review_date >= onboarding_date)
);

CREATE TABLE accounts (
    account_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    account_type TEXT NOT NULL CHECK (account_type IN ('savings', 'current', 'business')),
    balance NUMERIC(14, 2) NOT NULL,
    currency TEXT NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
    status TEXT NOT NULL CHECK (status IN ('active', 'frozen', 'closed')),
    opened_date DATE NOT NULL
);

CREATE TABLE transactions (
    transaction_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(account_id),
    transaction_time TIMESTAMPTZ NOT NULL,
    amount NUMERIC(14, 2) NOT NULL CHECK (amount > 0),
    currency TEXT NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('deposit', 'withdrawal', 'transfer_in', 'transfer_out', 'card_payment')),
    direction TEXT GENERATED ALWAYS AS (
        CASE WHEN transaction_type IN ('deposit', 'transfer_in')
            THEN 'inbound' ELSE 'outbound' END
    ) STORED,
    counterparty_name TEXT,
    counterparty_account TEXT,
    counterparty_country TEXT CHECK (counterparty_country ~ '^[A-Z]{2}$'),
    -- MVP accounts are domiciled in Singapore; unknown country gives NULL.
    is_cross_border BOOLEAN GENERATED ALWAYS AS (counterparty_country <> 'SG') STORED,
    is_high_risk_country BOOLEAN,
    high_risk_country_list_version TEXT,
    channel TEXT NOT NULL CHECK (channel IN ('branch', 'atm', 'online', 'mobile', 'api')),
    merchant_category TEXT,
    CHECK ((is_high_risk_country IS NULL AND high_risk_country_list_version IS NULL)
        OR (is_high_risk_country IS NOT NULL AND high_risk_country_list_version IS NOT NULL
            AND counterparty_country IS NOT NULL))
);

CREATE TABLE risk_scores (
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    aml_risk_score INTEGER NOT NULL CHECK (aml_risk_score BETWEEN 0 AND 100),
    fraud_risk_score INTEGER NOT NULL CHECK (fraud_risk_score BETWEEN 0 AND 100),
    credit_risk_score INTEGER NOT NULL CHECK (credit_risk_score BETWEEN 0 AND 100),
    score_date DATE NOT NULL,
    PRIMARY KEY (customer_id, score_date)
);

CREATE TABLE alerts (
    alert_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    status TEXT NOT NULL CHECK (status IN ('open', 'in_review', 'closed')),
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    related_transaction_id TEXT REFERENCES transactions(transaction_id),
    assigned_to TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMPTZ,
    CHECK (resolved_at IS NULL OR resolved_at >= created_at),
    CHECK ((status = 'closed' AND resolved_at IS NOT NULL)
        OR (status <> 'closed' AND resolved_at IS NULL))
);

CREATE TABLE policy_documents (
    document_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    document_type TEXT NOT NULL,
    published_date DATE,
    url TEXT NOT NULL CHECK (url ~ '^https?://'),
    document_version TEXT NOT NULL,
    content_sha256 TEXT NOT NULL CHECK (content_sha256 ~ '^[a-f0-9]{64}$'),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (url, content_sha256)
);

CREATE TABLE audit_logs (
    audit_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    user_role TEXT NOT NULL,
    user_question TEXT NOT NULL,
    generated_sql TEXT,
    sql_execution_status TEXT NOT NULL CHECK (
        sql_execution_status IN ('not_requested', 'blocked', 'succeeded', 'failed')
    ),
    retrieved_policy_refs JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(retrieved_policy_refs) = 'array'),
    final_answer TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_transactions_account_time ON transactions (account_id, transaction_time);
CREATE INDEX idx_transactions_amount ON transactions (amount);
CREATE INDEX idx_customers_kyc_status ON customers (kyc_status);
CREATE INDEX idx_alerts_customer_status ON alerts (customer_id, status);
CREATE INDEX idx_audit_logs_request ON audit_logs (request_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs (created_at);

COMMIT;
