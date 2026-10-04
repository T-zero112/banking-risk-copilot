-- Dedicated local project database only; roles are provisioned by the setup script.
REVOKE ALL ON DATABASE banking_risk FROM PUBLIC, banking_reader, banking_audit;
GRANT CONNECT ON DATABASE banking_risk TO banking_reader, banking_audit;
REVOKE ALL ON SCHEMA public FROM PUBLIC, banking_reader, banking_audit;
GRANT USAGE ON SCHEMA public TO banking_reader, banking_audit;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC, banking_reader, banking_audit;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC, banking_reader, banking_audit;

-- Table-level REVOKE does not remove older column-level grants.
DO $$
DECLARE t RECORD; cols TEXT;
BEGIN
    FOR t IN SELECT tablename FROM pg_tables WHERE schemaname='public' LOOP
        SELECT string_agg(format('%I', column_name), ', ') INTO cols
        FROM information_schema.columns WHERE table_schema='public' AND table_name=t.tablename;
        EXECUTE format('REVOKE SELECT (%s), INSERT (%s), UPDATE (%s), REFERENCES (%s) ON public.%I FROM PUBLIC, banking_reader, banking_audit',
                       cols, cols, cols, cols, t.tablename);
    END LOOP;
END $$;

GRANT SELECT ON customers, accounts, transactions, risk_scores, alerts,
    policy_documents, policy_corpora, policy_chunks, policy_retrieval_state,
    policy_embedding_indexes, policy_chunk_embeddings TO banking_reader;

GRANT SELECT ON audit_logs TO banking_audit;
GRANT INSERT (audit_id, request_id, user_role, user_question, sql_execution_status,
              customer_id, review_mode, review_status, review_metadata) ON audit_logs TO banking_audit;
GRANT UPDATE (review_status, sql_execution_status, finished_at, elapsed_ms,
              review_metadata, retrieved_policy_refs, final_answer, error_message) ON audit_logs TO banking_audit;

CREATE OR REPLACE FUNCTION public.guard_review_audit_transition() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog, public AS $$
BEGIN
    IF current_user <> 'banking_audit' THEN RETURN NEW; END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.review_status IS DISTINCT FROM 'started' OR NEW.review_mode IS NULL
           OR NEW.sql_execution_status IS DISTINCT FROM 'not_requested'
           OR NEW.finished_at IS NOT NULL OR NEW.elapsed_ms IS NOT NULL
           OR NEW.final_answer IS NOT NULL OR NEW.error_message IS NOT NULL THEN
            RAISE EXCEPTION 'Audit writer must insert an initial started record' USING ERRCODE='42501';
        END IF;
    ELSE
        IF OLD.review_status IS DISTINCT FROM 'started'
           OR NEW.review_status IS NULL OR NEW.review_status NOT IN ('succeeded','partial_success','failed')
           OR NEW.finished_at IS NULL OR NEW.elapsed_ms IS NULL
           OR NOT (NEW.review_metadata @> OLD.review_metadata) THEN
            RAISE EXCEPTION 'Only one completion of a started review is permitted' USING ERRCODE='42501';
        END IF;
    END IF;
    RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION public.guard_review_audit_transition() FROM PUBLIC;
DROP TRIGGER IF EXISTS review_audit_transition ON public.audit_logs;
CREATE TRIGGER review_audit_transition BEFORE INSERT OR UPDATE ON public.audit_logs
FOR EACH ROW EXECUTE FUNCTION public.guard_review_audit_transition();

ALTER DEFAULT PRIVILEGES FOR ROLE banking_owner IN SCHEMA public
    REVOKE ALL ON TABLES FROM PUBLIC, banking_reader, banking_audit;
ALTER DEFAULT PRIVILEGES FOR ROLE banking_owner IN SCHEMA public
    REVOKE ALL ON SEQUENCES FROM PUBLIC, banking_reader, banking_audit;
