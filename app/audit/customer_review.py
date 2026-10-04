"""Audited entry point; graph failures are logged with sanitized error codes."""

import hashlib
import json
import os
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from dotenv import load_dotenv
import psycopg

from app.audit.review import ReviewAuditStore
from app.graph.customer_review import build_review_graph
from app.graph.review_explanation import explanation_messages, review_payload, serialize
from app.sql.review import AS_OF, CustomerNotFound, ReviewCapacityExceeded

ROOT = Path(__file__).resolve().parents[2]


class AuditedReviewError(RuntimeError):
    def __init__(self, request_id, code):
        self.request_id = request_id
        self.code = code
        super().__init__(f"Request {request_id}: {code}")


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    default=serialize).encode("utf-8")).hexdigest()


def provenance(mode):
    load_dotenv(ROOT / ".env", override=False)
    files = ("app/sql/queries/review_customer.sql", "app/sql/queries/review_transactions.sql",
             "app/sql/review.py", "app/graph/customer_review.py", "app/graph/review_explanation.py",
             "app/rag/providers.py", "app/rag/retrieval.py")
    return dict(data_as_of=AS_OF.isoformat(), workflow_version="customer-review-v1",
                prompt_version="review-explanation-v4" if mode == "deepseek" else None,
                provider="deepseek" if mode == "deepseek" else None,
                model=os.getenv("DEEPSEEK_MODEL", "deepseek-flash") if mode == "deepseek" else None,
                model_settings=dict(temperature=0, max_tokens=4096, timeout_seconds=60,
                                    max_retries=0, thinking="disabled") if mode == "deepseek" else None,
                code_sha256={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files})


def run_customer_review(customer_id, mode="deterministic", *, store=None, graph_factory=None, actor=None):
    request_id = str(uuid4())
    injected_graph = graph_factory is not None
    store = store or ReviewAuditStore()
    graph_factory = graph_factory or build_review_graph
    metadata = provenance(mode)
    metadata["actor"] = actor or {"username": "local_cli_operator", "role": "local_maintenance"}
    metadata["execution_adapter"] = "injected" if injected_graph else "default"
    started = perf_counter()
    try:
        store.start(request_id, customer_id, mode, metadata)
    except Exception:
        # Fail closed: do not query customer data or call a model without a start record.
        raise AuditedReviewError(request_id, "audit_start_unconfirmed") from None
    state = {}
    stage = "configure"
    sql_status = "not_requested"
    status = "failed"
    error_code = None
    report = None
    try:
        graph = graph_factory(mode=mode)
        stage = "load_sql"
        sql_status = "failed"
        for event in graph.stream({"customer_id": customer_id}, stream_mode="updates"):
            for node, update in event.items():
                state.update(update)
                if node == "load_sql":
                    sql_status = "succeeded"
                if node == "compose" and mode == "deepseek":
                    payload = review_payload(state["report"])
                    metadata["model_input_sha256"] = digest(payload)
                    metadata["prompt_sha256"] = digest(explanation_messages(payload))
                stage = {"load_sql": "assess", "assess": "retrieve_policy", "retrieve_policy": "compose",
                         "compose": "generate_explanation" if mode == "deepseek" else "complete",
                         "generate_explanation": "validate_explanation", "validate_explanation": "complete"}[node]
        report = dict(state["report"], request_id=request_id)
        generation = report.get("ai_generation", {})
        status = "partial_success" if generation.get("status") == "failed" else "succeeded"
        error_code = generation.get("error_code")
    except Exception as error:
        report = state.get("report")
        if report is not None:
            report = dict(report, request_id=request_id)
        if isinstance(error, CustomerNotFound):
            error_code = "customer_not_found"
        elif isinstance(error, ReviewCapacityExceeded):
            error_code = "review_capacity_exceeded"
        elif isinstance(error, psycopg.Error):
            error_code = "database_error"
        elif isinstance(error, ValueError):
            error_code = "invalid_request_or_configuration" if stage in {"configure", "load_sql"} else "workflow_validation_failed"
        else:
            error_code = "workflow_failed"
    metadata["last_stage"] = stage
    # Retain the completed SQL snapshot even when retrieval fails before report composition.
    if "evidence" in state:
        metadata["sql_evidence_snapshot"] = json.loads(json.dumps(state["evidence"], default=serialize))
    metadata["outcome"] = status
    if state.get("candidates"):
        metadata["retrieval_query"] = "matching payments credits"
        metadata["retrieval_source_filter"] = "spf-bank-red-flags"
    try:
        store.finish(request_id, status, sql_status, int((perf_counter() - started) * 1000),
                     metadata, report, error_code)
    except Exception:
        raise AuditedReviewError(request_id, "audit_completion_unconfirmed") from None
    if status == "failed":
        raise AuditedReviewError(request_id, error_code) from None
    return dict(report, audit=dict(status=status, persistence="confirmed"))
