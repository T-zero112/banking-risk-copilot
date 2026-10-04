from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from threading import Event, Lock
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.api.auth import AuthStore
from app.audit.customer_review import AuditedReviewError


class APITests(unittest.TestCase):
    def setUp(self):
        self.request_id = str(uuid4())
        self.runner = MagicMock(return_value=dict(request_id=self.request_id, facts={"amount": Decimal("100.10")},
                                                audit={"status": "succeeded", "persistence": "confirmed"}))
        self.store = MagicMock()
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.auth = AuthStore(Path(temporary.name) / "auth.sqlite3")
        self.auth.initialize()
        self.auth.set_user("testadmin", "test-password-123", "admin", [])
        self.client = TestClient(create_app(self.runner, self.store, self.auth))
        self.client.post("/auth/login", json={"username":"testadmin", "password":"test-password-123"})

    def test_health_does_not_call_database_or_model(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["scope"], "process_liveness_only")
        self.runner.assert_not_called()
        self.store.read.assert_not_called()

    def test_ready_checks_dependencies_without_model_call(self):
        with patch("app.sql.database.connect") as connect:
            connect.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = {"ok":1}
            response = self.client.get("/ready")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provider"], "not_checked_optional")
        self.runner.assert_not_called()

    def test_ready_error_is_sanitized(self):
        with patch("app.sql.database.connect", side_effect=RuntimeError("password=private-test")):
            response = self.client.get("/ready")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private-test", response.text)

    def test_workbench_assets_are_local_and_do_not_run_review(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("客户审查", response.text)
        self.assertIn("script-src 'self'", response.headers["content-security-policy"])
        for path in ("/assets/workbench.css", "/assets/workbench.js", "/assets/vendor/lucide.js"):
            self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(self.client.get("/assets/../../.env").status_code, 404)
        self.runner.assert_not_called()
        self.store.read.assert_not_called()

    def test_default_review_is_audited_and_precision_preserved(self):
        response = self.client.post("/reviews", json={"customer_id": "C003"})
        self.assertEqual(response.status_code, 201)
        self.runner.assert_called_once_with("C003", "deterministic", actor={"username":"testadmin", "role":"admin"})
        self.assertEqual(response.json()["report"]["facts"]["amount"], "100.10")
        self.assertEqual(response.json()["request_id"], self.request_id)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_validation_does_not_echo_secret_or_execute_review(self):
        for payload in ({"customer_id": "C003'--"}, {"customer_id": "C003", "mode": "invalid"},
                        {"customer_id": "C003", "api_key": "secret-test"}, {}):
            response = self.client.post("/reviews", json=payload)
            self.assertEqual(response.status_code, 422)
            self.assertNotIn("secret-test", response.text)
        self.runner.assert_not_called()

    def test_partial_success_is_explicit(self):
        self.runner.return_value["audit"]["status"] = "partial_success"
        self.runner.return_value["ai_generation"] = {"status": "failed"}
        response = self.client.post("/reviews", json={"customer_id": "C003", "mode": "deepseek", "paid_consent":True})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "partial_success")
        self.runner.assert_called_once_with("C003", "deepseek", actor={"username":"testadmin", "role":"admin"})

    def test_audited_failures_return_correlated_codes(self):
        for code, status in (("customer_not_found", 404), ("audit_start_unconfirmed", 503),
                             ("audit_completion_unconfirmed", 503), ("review_capacity_exceeded", 422),
                             ("workflow_failed", 500)):
            self.runner.side_effect = AuditedReviewError(self.request_id, code)
            response = self.client.post("/reviews", json={"customer_id": "C003"})
            self.assertEqual(response.status_code, status)
            self.assertEqual(response.json()["detail"]["request_id"], self.request_id)

    def test_unexpected_error_is_sanitized(self):
        self.runner.side_effect = RuntimeError("password=secret")
        response = self.client.post("/reviews", json={"customer_id": "C003"})
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("secret", response.text)

    def test_read_audit(self):
        self.store.read.return_value = dict(request_id=self.request_id, customer_id="C003", review_mode="deterministic",
                    review_status="succeeded", created_at=datetime.now(timezone.utc), finished_at=None,
                    elapsed_ms=10, sql_execution_status="succeeded", error_message=None, review_metadata={},
                    retrieved_policy_refs=[], final_answer={"request_id": self.request_id})
        response = self.client.get(f"/reviews/{self.request_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["report"]["request_id"], self.request_id)
        self.store.read.assert_called_once_with(self.request_id)

    def test_audit_lookup_errors(self):
        self.store.read.return_value = None
        self.assertEqual(self.client.get(f"/reviews/{self.request_id}").status_code, 404)
        self.store.read.side_effect = RuntimeError("secret")
        response = self.client.get(f"/reviews/{self.request_id}")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("secret", response.text)

    def test_invalid_uuid_does_not_query_store(self):
        self.assertEqual(self.client.get("/reviews/not-a-uuid").status_code, 422)
        self.store.read.assert_not_called()

    def test_cross_origin_and_untrusted_host_rejected(self):
        response = self.client.post("/reviews", json={"customer_id": "C003"}, headers={"Origin": "https://untrusted.example"})
        self.assertEqual(response.status_code, 403)
        self.runner.assert_not_called()
        self.assertEqual(self.client.get("/health", headers={"Host": "untrusted.example"}).status_code, 400)
        self.assertEqual(self.client.post("/reviews", json={"customer_id": "C003"}, headers={"Origin": "http://testserver"}).status_code, 201)

    def test_openapi_exposes_request_schema(self):
        schema = self.client.get("/openapi.json").json()
        self.assertIn("/reviews", schema["paths"])
        self.assertEqual(schema["components"]["schemas"]["ReviewRequest"]["properties"]["mode"]["default"], "deterministic")

    def test_review_concurrency_limit(self):
        both_started, release = Event(), Event()
        lock = Lock()
        count = 0

        def slow_runner(customer, mode, *, actor):
            nonlocal count
            with lock:
                count += 1
                if count == 2:
                    both_started.set()
            if not release.wait(10):
                raise RuntimeError("Test timeout")
            return self.runner.return_value

        client = TestClient(create_app(slow_runner, self.store, self.auth))
        client.post("/auth/login", json={"username":"testadmin", "password":"test-password-123"})
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(client.post, "/reviews", json={"customer_id": "C003"}) for _ in range(2)]
            try:
                self.assertTrue(both_started.wait(10))
                response = client.post("/reviews", json={"customer_id": "C003"})
                self.assertEqual(response.status_code, 429)
                self.assertEqual(response.headers["retry-after"], "5")
            finally:
                release.set()
            self.assertTrue(all(f.result(timeout=10).status_code == 201 for f in futures))
