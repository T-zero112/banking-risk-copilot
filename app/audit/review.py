"""Short, separately committed transactions for customer review audit records."""

import json

from psycopg.types.json import Jsonb

from app.graph.review_explanation import serialize
from app.sql.database import connect


class ReviewAuditStore:
    def start(self, request_id, customer_id, mode, metadata):
        with connect("audit") as connection:
            connection.execute("SET LOCAL statement_timeout = '5s'")
            connection.execute("SET LOCAL lock_timeout = '2s'")
            connection.execute("""
                INSERT INTO audit_logs(audit_id, request_id, user_role, user_question,
                    sql_execution_status, customer_id, review_mode, review_status, review_metadata)
                VALUES (%s,%s,'local_demo_operator','Customer review',
                        'not_requested',%s,%s,'started',%s)
            """, (request_id, request_id, customer_id, mode, Jsonb(metadata)))

    def finish(self, request_id, status, sql_status, elapsed_ms, metadata, report, error_code):
        refs = [{key: p[key] for key in ("citation_id", "document_id", "document_version",
                 "content_sha256", "chunk_id", "corpus_id", "citation_url") if key in p}
                for p in (report or {}).get("policy_evidence", [])]
        with connect("audit") as connection:
            connection.execute("SET LOCAL statement_timeout = '5s'")
            connection.execute("SET LOCAL lock_timeout = '2s'")
            cursor = connection.execute("""
                UPDATE audit_logs SET review_status=%s, sql_execution_status=%s,
                    finished_at=CURRENT_TIMESTAMP, elapsed_ms=%s,
                    review_metadata=review_metadata || %s, retrieved_policy_refs=%s,
                    final_answer=%s, error_message=%s
                WHERE request_id=%s AND review_mode IS NOT NULL AND review_status='started'
            """, (status, sql_status, elapsed_ms, Jsonb(metadata), Jsonb(refs),
                  json.dumps(report, ensure_ascii=False, default=serialize) if report is not None else None,
                  error_code, request_id))
            if cursor.rowcount != 1:
                raise RuntimeError("Audit completion did not update exactly one started record")

    def read(self, request_id):
        with connect("audit") as connection:
            connection.execute("SET TRANSACTION READ ONLY")
            connection.execute("SET LOCAL statement_timeout = '5s'")
            row = connection.execute("SELECT * FROM audit_logs WHERE request_id=%s AND review_mode IS NOT NULL",
                                     (request_id,)).fetchone()
        if row and row["final_answer"]:
            row["final_answer"] = json.loads(row["final_answer"])
        return row
